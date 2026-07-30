"""Route 53 hosted zone scanner (global)."""

from __future__ import annotations

from botocore.exceptions import ClientError

from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner


class Route53Scanner(BaseScanner):
    service_name = "Route53"

    def scan(self) -> list[AwsResource]:
        resources: list[AwsResource] = []
        try:
            client = self.session.client("route53", region_name="us-east-1")
            paginator = client.get_paginator("list_hosted_zones")
            for page in paginator.paginate():
                for zone in page.get("HostedZones", []):
                    zone_id = zone["Id"].replace("/hostedzone/", "")
                    resources.append(
                        AwsResource(
                            resource_id=zone_id,
                            name=zone.get("Name", ""),
                            service="Route53",
                            resource_type="Hosted Zone",
                            region="global",
                            status="active" if not zone.get("Config", {}).get("PrivateZone") else "private",
                            details=f"Records: {zone.get('ResourceRecordSetCount', 0)}",
                            extra={"hosted_zone_id": zone_id},
                        )
                    )
        except ClientError:
            pass
        return resources
