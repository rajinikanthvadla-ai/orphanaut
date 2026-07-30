"""AWS region utilities."""

from __future__ import annotations

import boto3
from botocore.exceptions import ClientError


def get_all_regions(session: boto3.Session) -> list[str]:
    """Return all enabled AWS regions for the account."""
    try:
        ec2 = session.client("ec2", region_name="us-east-1")
        response = ec2.describe_regions(AllRegions=False)
        return sorted(r["RegionName"] for r in response["Regions"])
    except ClientError:
        return sorted(session.get_available_regions("ec2"))
