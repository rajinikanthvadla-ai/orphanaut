"""Tests for AWS resource models."""

from orphanaut.models import AuthConfig, AuthMethod, AwsResource


def test_aws_resource_display_key():
    resource = AwsResource(
        resource_id="i-abc123",
        name="test",
        service="EC2",
        resource_type="Instance",
        region="us-east-1",
        status="running",
        details="Type: t2.micro",
    )
    assert resource.display_key == "us-east-1:EC2:i-abc123"


def test_aws_resource_to_row():
    resource = AwsResource(
        resource_id="vol-123",
        name="data",
        service="EBS",
        resource_type="Volume",
        region="eu-west-1",
        status="available",
        details="8 GiB",
    )
    row = resource.to_row()
    assert row[0] == "eu-west-1"
    assert row[3] == "vol-123"


def test_auth_config_defaults():
    config = AuthConfig(method=AuthMethod.ACCESS_KEYS)
    assert config.region == "us-east-1"
    assert config.profile_name == ""
