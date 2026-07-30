"""Lightsail instance scanner."""

from __future__ import annotations

from botocore.exceptions import ClientError

from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner


class LightsailScanner(BaseScanner):
    service_name = "Lightsail"

    def scan(self) -> list[AwsResource]:
        resources: list[AwsResource] = []
        try:
            client = self.session.client("lightsail", region_name=self.region)
            response = client.get_instances()
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
        except ClientError:
            pass
        return resources
