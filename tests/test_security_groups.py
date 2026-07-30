"""Tests for security group discovery and deletion safety."""

from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from orphanaut.actions.deleter import DeleteError, delete_resource
from orphanaut.models import AwsResource
from orphanaut.scanners.security_groups import SecurityGroupScanner


class FakePaginator:
    def paginate(self):
        return [
            {
                "NetworkInterfaces": [
                    {"Groups": [{"GroupId": "sg-in-use"}]},
                ]
            }
        ]


class FakeEc2Client:
    def describe_security_groups(self):
        return {
            "SecurityGroups": [
                {
                    "GroupId": "sg-default",
                    "GroupName": "default",
                    "VpcId": "vpc-1",
                    "IpPermissions": [],
                    "IpPermissionsEgress": [],
                },
                {
                    "GroupId": "sg-in-use",
                    "GroupName": "web",
                    "VpcId": "vpc-1",
                    "IpPermissions": [
                        {"UserIdGroupPairs": [{"GroupId": "sg-referenced"}]},
                    ],
                    "IpPermissionsEgress": [{}],
                },
                {
                    "GroupId": "sg-referenced",
                    "GroupName": "db",
                    "VpcId": "vpc-1",
                    "IpPermissions": [],
                    "IpPermissionsEgress": [{}],
                },
                {
                    "GroupId": "sg-unused",
                    "GroupName": "old-lab",
                    "VpcId": "vpc-1",
                    "IpPermissions": [],
                    "IpPermissionsEgress": [{}],
                },
            ]
        }

    def get_paginator(self, operation_name):
        assert operation_name == "describe_network_interfaces"
        return FakePaginator()


def test_security_group_scanner_marks_safe_deletion_states():
    scanner = SecurityGroupScanner(Mock(), "us-east-1")
    scanner.client = Mock(return_value=FakeEc2Client())

    resources = scanner.scan()
    by_id = {resource.resource_id: resource for resource in resources}

    assert by_id["sg-default"].status == "default"
    assert not by_id["sg-default"].deletable
    assert by_id["sg-in-use"].status == "in use"
    assert not by_id["sg-in-use"].deletable
    assert by_id["sg-referenced"].status == "referenced"
    assert not by_id["sg-referenced"].deletable
    assert "referenced by another security group" in by_id["sg-referenced"].details
    assert by_id["sg-unused"].status == "unused"
    assert by_id["sg-unused"].deletable


def test_delete_resource_rejects_protected_resource():
    resource = AwsResource(
        resource_id="sg-in-use",
        name="web",
        service="VPC",
        resource_type="Security Group",
        region="us-east-1",
        status="in use",
        details="",
        deletable=False,
    )

    with pytest.raises(DeleteError, match="in use or protected"):
        delete_resource(Mock(), resource)


def test_delete_resource_explains_dependency_violation():
    resource = AwsResource(
        resource_id="sg-referenced",
        name="db",
        service="VPC",
        resource_type="Security Group",
        region="us-east-1",
        status="referenced",
        details="",
        deletable=True,
        extra={"group_id": "sg-referenced"},
    )

    error = ClientError(
        {
            "Error": {
                "Code": "DependencyViolation",
                "Message": "resource sg-referenced has a dependent object",
            }
        },
        "DeleteSecurityGroup",
    )
    ec2_client = Mock()
    ec2_client.delete_security_group.side_effect = error
    session = Mock()
    session.client.return_value = ec2_client

    with pytest.raises(DeleteError, match="still referenced by another AWS resource"):
        delete_resource(session, resource)
