"""AWS region utilities."""

from __future__ import annotations

import boto3
from botocore.exceptions import ClientError

from orphanaut.aws.config import AWS_CONFIG

COMMON_REGIONS = [
    "us-east-1",
    "us-east-2",
    "us-west-2",
    "ap-south-1",
    "eu-west-1",
]

REGION_LABELS: dict[str, str] = {
    "us-east-1": "US East (N. Virginia)",
    "us-east-2": "US East (Ohio)",
    "us-west-1": "US West (N. California)",
    "us-west-2": "US West (Oregon)",
    "ap-south-1": "Asia Pacific (Mumbai)",
    "ap-southeast-1": "Asia Pacific (Singapore)",
    "ap-southeast-2": "Asia Pacific (Sydney)",
    "ap-northeast-1": "Asia Pacific (Tokyo)",
    "ap-northeast-2": "Asia Pacific (Seoul)",
    "eu-west-1": "Europe (Ireland)",
    "eu-west-2": "Europe (London)",
    "eu-central-1": "Europe (Frankfurt)",
    "ca-central-1": "Canada (Central)",
    "sa-east-1": "South America (São Paulo)",
}


def region_display_name(region: str) -> str:
    label = REGION_LABELS.get(region)
    if label:
        return f"{region} — {label}"
    return region


def get_all_regions(session: boto3.Session) -> list[str]:
    """Return all enabled AWS regions for the account."""
    try:
        ec2 = session.client("ec2", region_name="us-east-1", config=AWS_CONFIG)
        response = ec2.describe_regions(AllRegions=False)
        return sorted(r["RegionName"] for r in response["Regions"])
    except ClientError:
        return sorted(session.get_available_regions("ec2"))
