"""Tests for cloud resource models."""

from orphanaut.models import AuthConfig, AuthMethod, CloudProvider, CloudResource


def test_cloud_resource_display_key():
    resource = CloudResource(
        resource_id="i-abc123",
        name="test",
        service="EC2",
        resource_type="Instance",
        region="us-east-1",
        status="running",
        details="Type: t2.micro",
        provider=CloudProvider.AWS,
    )
    assert resource.display_key == "aws:us-east-1:EC2:i-abc123"


def test_cloud_resource_to_row():
    resource = CloudResource(
        resource_id="vol-123",
        name="data",
        service="EBS",
        resource_type="Volume",
        region="eu-west-1",
        status="available",
        details="8 GiB",
        provider=CloudProvider.AWS,
    )
    row = resource.to_row()
    assert row[0] == "AWS"
    assert row[1] == "eu-west-1"
    assert row[4] == "vol-123"


def test_auth_config_defaults():
    config = AuthConfig(method=AuthMethod.ACCESS_KEYS)
    assert config.provider == CloudProvider.AWS
    assert config.region == "us-east-1"
    assert config.profile_name == ""
