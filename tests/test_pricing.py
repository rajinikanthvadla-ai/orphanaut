"""Tests for rough monthly cost estimation."""

import pytest

from orphanaut.aws.pricing import estimate_monthly_cost, format_monthly_cost
from orphanaut.models import AwsResource


def _resource(**overrides) -> AwsResource:
    defaults = dict(
        resource_id="id-1",
        name="test",
        service="EC2",
        resource_type="Instance",
        region="us-east-1",
        status="running",
        details="",
    )
    defaults.update(overrides)
    return AwsResource(**defaults)


def test_running_ec2_instance_prices_by_size():
    resource = _resource(details="Type: t3.micro", status="running")
    assert estimate_monthly_cost(resource) == pytest.approx(0.0125 * 730, rel=1e-3)


def test_stopped_ec2_instance_has_no_compute_cost():
    resource = _resource(details="Type: t3.micro", status="stopped")
    assert estimate_monthly_cost(resource) == 0.0


def test_ebs_volume_prices_by_size():
    resource = _resource(
        service="EBS",
        resource_type="Volume",
        details="20 GiB, gp3",
        status="available (unattached)",
    )
    assert estimate_monthly_cost(resource) == pytest.approx(20 * 0.08)


def test_ebs_snapshot_prices_by_size():
    resource = _resource(
        service="EBS", resource_type="Snapshot", details="50 GiB", status="completed"
    )
    assert estimate_monthly_cost(resource) == pytest.approx(50 * 0.05)


def test_unassociated_elastic_ip_is_billed():
    resource = _resource(
        service="EC2", resource_type="Elastic IP", details="IP: 1.2.3.4", status="unassociated"
    )
    assert estimate_monthly_cost(resource) == pytest.approx(0.005 * 730)


def test_associated_elastic_ip_is_free():
    resource = _resource(
        service="EC2", resource_type="Elastic IP", details="IP: 1.2.3.4", status="associated"
    )
    assert estimate_monthly_cost(resource) == 0.0


def test_nat_gateway_flat_rate():
    resource = _resource(
        service="VPC", resource_type="NAT Gateway", details="VPC: vpc-1", status="available"
    )
    assert estimate_monthly_cost(resource) == pytest.approx(0.045 * 730)


def test_security_group_is_free():
    resource = _resource(service="VPC", resource_type="Security Group", status="unused")
    assert estimate_monthly_cost(resource) == 0.0


def test_gateway_endpoint_is_free_but_interface_endpoint_is_billed():
    gateway = _resource(service="VPC", resource_type="Gateway Endpoint", status="available")
    interface = _resource(service="VPC", resource_type="Interface Endpoint", status="available")
    assert estimate_monthly_cost(gateway) == 0.0
    assert estimate_monthly_cost(interface) == pytest.approx(0.01 * 730)


def test_rds_db_instance_prices_by_class():
    resource = _resource(
        service="RDS",
        resource_type="DB Instance",
        details="Engine: mysql db.t3.medium",
        status="available",
    )
    assert estimate_monthly_cost(resource) == pytest.approx(0.05 * 730)


def test_rds_db_cluster_is_not_double_counted():
    resource = _resource(
        service="RDS",
        resource_type="DB Cluster",
        details="Engine: aurora-mysql",
        status="available",
    )
    assert estimate_monthly_cost(resource) is None


def test_lightsail_prices_by_bundle():
    resource = _resource(
        service="Lightsail",
        resource_type="Instance",
        details="Bundle: micro_3_0, IP: 1.2.3.4",
        status="running",
    )
    assert estimate_monthly_cost(resource) == pytest.approx(5.0)


def test_usage_based_services_are_unknown():
    lambda_fn = _resource(service="Lambda", resource_type="Function", status="Active")
    s3_bucket = _resource(service="S3", resource_type="Bucket", status="active")
    dynamodb = _resource(service="DynamoDB", resource_type="Table", status="ACTIVE")
    assert estimate_monthly_cost(lambda_fn) is None
    assert estimate_monthly_cost(s3_bucket) is None
    assert estimate_monthly_cost(dynamodb) is None


def test_format_monthly_cost():
    assert format_monthly_cost(None) == "—"
    assert format_monthly_cost(0.0) == "$0.00"
    assert format_monthly_cost(32.85) == "$32.85/mo"
