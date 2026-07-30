"""Rough monthly cost estimates for discovered AWS resources.

These are approximate on-demand list prices (roughly US East pricing) meant
to give students a sense of scale for cost-conscious cleanup — this is NOT a
substitute for AWS Cost Explorer or your actual bill. Real costs vary by
region, usage, discounts, savings plans, and data transfer, none of which
are visible from a resource listing alone.
"""

from __future__ import annotations

import re

from orphanaut.models import AwsResource

HOURS_PER_MONTH = 730

# Approximate on-demand hourly rate (USD) keyed by instance/node size tier.
# Shared across EC2, RDS, and ElastiCache since their sizing tiers roughly
# track each other in relative cost.
_HOURLY_RATE_BY_TIER: dict[str, float] = {
    "nano": 0.006,
    "micro": 0.0125,
    "small": 0.025,
    "medium": 0.05,
    "large": 0.10,
    "xlarge": 0.20,
    "2xlarge": 0.40,
    "4xlarge": 0.80,
    "8xlarge": 1.60,
    "12xlarge": 2.40,
    "16xlarge": 3.20,
    "24xlarge": 4.80,
}

_LIGHTSAIL_MONTHLY_BY_TIER: dict[str, float] = {
    "nano": 3.5,
    "micro": 5.0,
    "small": 10.0,
    "medium": 20.0,
    "large": 40.0,
    "xlarge": 80.0,
    "2xlarge": 160.0,
}

_EBS_GB_MONTH = 0.08
_SNAPSHOT_GB_MONTH = 0.05
_NAT_GATEWAY_HOURLY = 0.045
_LOAD_BALANCER_HOURLY = 0.0225
_INTERFACE_ENDPOINT_HOURLY = 0.01
_ELASTIC_IP_IDLE_HOURLY = 0.005
_EKS_CONTROL_PLANE_HOURLY = 0.10
_CLOUDWATCH_GB_MONTH = 0.03
_ROUTE53_ZONE_MONTHLY = 0.50

_RUNNING_EC2_STATES = {"running", "pending", "rebooting", "stopping"}

_INSTANCE_TYPE_RE = re.compile(r"Type:\s*([\w.]+)")
_ENGINE_CLASS_RE = re.compile(r"Engine:\s*\S+\s+(\S+)")
_SIZE_GIB_RE = re.compile(r"([\d.]+)\s*GiB")
_LOG_STORED_MB_RE = re.compile(r"Stored:\s*([\d.]+)\s*MB")
_LIGHTSAIL_BUNDLE_RE = re.compile(r"Bundle:\s*([\w-]+)")


def _tier_from_type(type_name: str) -> str | None:
    """Extract the size tier (e.g. "micro", "2xlarge") from an instance
    type string. Handles both bare EC2 types ("t3.micro") and prefixed
    RDS/ElastiCache types ("db.t3.micro", "cache.m5.large")."""
    parts = type_name.split(".")
    if len(parts) < 2:
        return None
    return parts[-1].lower()


def _hourly_rate_for_type(type_name: str) -> float | None:
    tier = _tier_from_type(type_name)
    if tier is None:
        return None
    return _HOURLY_RATE_BY_TIER.get(tier)


def estimate_monthly_cost(resource: AwsResource) -> float | None:
    """Return an approximate USD/month cost for a resource, or None if it
    can't be reasonably estimated from scan metadata alone (e.g. Lambda,
    S3, DynamoDB, which are billed on actual usage rather than existence)."""
    service = resource.service
    resource_type = resource.resource_type
    details = resource.details
    status = resource.status.lower()

    if service == "EC2" and resource_type == "Instance":
        if status not in _RUNNING_EC2_STATES:
            return 0.0
        match = _INSTANCE_TYPE_RE.search(details)
        rate = _hourly_rate_for_type(match.group(1)) if match else None
        return round(rate * HOURS_PER_MONTH, 2) if rate is not None else None

    if service == "EC2" and resource_type == "Elastic IP":
        if status == "unassociated":
            return round(_ELASTIC_IP_IDLE_HOURLY * HOURS_PER_MONTH, 2)
        return 0.0

    if service == "EBS" and resource_type == "Volume":
        match = _SIZE_GIB_RE.search(details)
        size = float(match.group(1)) if match else None
        return round(size * _EBS_GB_MONTH, 2) if size is not None else None

    if service == "EBS" and resource_type == "Snapshot":
        match = _SIZE_GIB_RE.search(details)
        size = float(match.group(1)) if match else None
        return round(size * _SNAPSHOT_GB_MONTH, 2) if size is not None else None

    if service == "VPC" and resource_type == "NAT Gateway":
        return round(_NAT_GATEWAY_HOURLY * HOURS_PER_MONTH, 2)

    if service == "VPC" and resource_type == "Security Group":
        return 0.0

    if service == "VPC" and "Endpoint" in resource_type:
        if "Interface" in resource_type or "GatewayLoadBalancer" in resource_type:
            return round(_INTERFACE_ENDPOINT_HOURLY * HOURS_PER_MONTH, 2)
        return 0.0

    if service == "ELB" and "Load Balancer" in resource_type:
        return round(_LOAD_BALANCER_HOURLY * HOURS_PER_MONTH, 2)

    if service == "RDS" and resource_type == "DB Instance":
        if "stopped" in status:
            return 0.0
        match = _ENGINE_CLASS_RE.search(details)
        rate = _hourly_rate_for_type(match.group(1)) if match else None
        return round(rate * HOURS_PER_MONTH, 2) if rate is not None else None

    if service == "RDS" and resource_type == "DB Cluster":
        # Aurora member instances are priced individually as their own
        # "DB Instance" entries; the cluster entry has no separate compute.
        return None

    if service == "ElastiCache" and resource_type == "Cache Cluster":
        match = _ENGINE_CLASS_RE.search(details)
        rate = _hourly_rate_for_type(match.group(1)) if match else None
        return round(rate * HOURS_PER_MONTH, 2) if rate is not None else None

    if service == "EKS" and resource_type == "Cluster":
        return round(_EKS_CONTROL_PLANE_HOURLY * HOURS_PER_MONTH, 2)

    if service == "CloudWatch" and resource_type == "Log Group":
        match = _LOG_STORED_MB_RE.search(details)
        size_mb = float(match.group(1)) if match else 0.0
        return round((size_mb / 1024) * _CLOUDWATCH_GB_MONTH, 2)

    if service == "Route53" and resource_type == "Hosted Zone":
        return _ROUTE53_ZONE_MONTHLY

    if service == "Lightsail" and resource_type == "Instance":
        match = _LIGHTSAIL_BUNDLE_RE.search(details)
        if not match:
            return None
        tier = match.group(1).split("_", 1)[0].lower()
        return _LIGHTSAIL_MONTHLY_BY_TIER.get(tier)

    # Lambda, S3, DynamoDB, ECS clusters: usage-based pricing that can't be
    # estimated from scan metadata alone.
    return None


def format_monthly_cost(cost: float | None) -> str:
    """Format an estimated monthly cost for display in the UI/CSV export."""
    if cost is None:
        return "—"
    if cost == 0:
        return "$0.00"
    return f"${cost:,.2f}/mo"
