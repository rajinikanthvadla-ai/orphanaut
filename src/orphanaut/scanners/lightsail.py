"""Lightsail instance scanner."""

from __future__ import annotations

from botocore.exceptions import ClientError

from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner

LIGHTSAIL_REGIONS = frozenset(
    {
        "us-east-1",
        "us-east-2",
        "us-west-2",
        "eu-west-1",
        "eu-west-2",
        "eu-west-3",
        "eu-central-1",
        "ap-south-1",
        "ap-southeast-1",
        "ap-southeast-2",
        "ap-northeast-1",
        "ap-northeast-2",
        "ca-central-1",
    }
)


class LightsailScanner(BaseScanner):
    service_name = "Lightsail"

    @classmethod
    def supports_region(cls, region: str) -> bool:
        return region in LIGHTSAIL_REGIONS

    def scan(self) -> list[AwsResource]:
        resources: list[AwsResource] = []
        try:
            client = self.client("lightsail")
            page_token: str | None = None
            while True:
                kwargs = {"pageToken": page_token} if page_token else {}
                response = client.get_instances(**kwargs)
                for instance in response.get("instances", []):
                    resources.append(
                        AwsResource(
                            resource_id=instance["arn"],
                            name=instance.get("name", ""),
                            service="Lightsail",
                            resource_type="Instance",
                            region=self.region,
                            status=instance.get("state", {}).get("name", "unknown"),
                            details=f"Bundle: {instance.get('bundleId', 'N/A')}, "
                            f"IP: {instance.get('publicIpAddress', 'N/A')}",
                            extra={"instance_name": instance.get("name", "")},
                        )
                    )
                page_token = response.get("nextPageToken")
                if not page_token:
                    break
        except ClientError:
            raise
        return resources
