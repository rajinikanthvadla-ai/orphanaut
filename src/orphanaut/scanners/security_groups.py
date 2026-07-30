"""EC2 security group scanner."""

from __future__ import annotations

from typing import Any

from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner


class SecurityGroupScanner(BaseScanner):
    service_name = "VPC"

    def scan(self) -> list[AwsResource]:
        ec2 = self.client("ec2")
        groups = ec2.describe_security_groups().get("SecurityGroups", [])

        attached_group_ids = self._attached_group_ids(ec2)
        referenced_group_ids = self._referenced_group_ids(groups)

        resources: list[AwsResource] = []
        for group in groups:
            group_id = group["GroupId"]
            group_name = group.get("GroupName", "")
            is_default = group_name == "default"
            is_attached = group_id in attached_group_ids
            is_referenced = group_id in referenced_group_ids

            if is_default:
                status = "default"
            elif is_attached:
                status = "in use"
            elif is_referenced:
                status = "referenced"
            else:
                status = "unused"

            inbound_rules = len(group.get("IpPermissions", []))
            outbound_rules = len(group.get("IpPermissionsEgress", []))
            details = (
                f"VPC: {group.get('VpcId', 'EC2-Classic')}, "
                f"Rules: {inbound_rules} inbound / {outbound_rules} outbound"
            )
            if is_referenced and not is_attached and not is_default:
                details += " — referenced by another security group's rules"

            resources.append(
                AwsResource(
                    resource_id=group_id,
                    name=group_name,
                    service="VPC",
                    resource_type="Security Group",
                    region=self.region,
                    status=status,
                    details=details,
                    deletable=not is_default and not is_attached and not is_referenced,
                    extra={
                        "group_id": group_id,
                        "vpc_id": group.get("VpcId", ""),
                    },
                )
            )

        return resources

    def _attached_group_ids(self, ec2: Any) -> set[str]:
        """Security groups currently attached to a network interface (EC2,
        RDS, Lambda-in-VPC, ELB, EFS, etc. all attach via an ENI)."""
        attached: set[str] = set()
        paginator = ec2.get_paginator("describe_network_interfaces")
        for page in paginator.paginate():
            for interface in page.get("NetworkInterfaces", []):
                attached.update(group["GroupId"] for group in interface.get("Groups", []))
        return attached

    def _referenced_group_ids(self, groups: list[dict]) -> set[str]:
        """Security groups referenced as an allowed source/destination in
        another security group's rules. AWS refuses to delete a group while
        another group's rule still points at it, even if it has no ENI of
        its own — this is the "depends on" case that otherwise looks safe
        to delete but fails with a DependencyViolation."""
        referenced: set[str] = set()
        for group in groups:
            rule_sets = (group.get("IpPermissions", []), group.get("IpPermissionsEgress", []))
            for rule_set in rule_sets:
                for permission in rule_set:
                    for pair in permission.get("UserIdGroupPairs", []):
                        referenced_id = pair.get("GroupId")
                        if referenced_id:
                            referenced.add(referenced_id)
        return referenced
