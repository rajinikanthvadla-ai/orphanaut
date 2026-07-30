"""NAT Gateway scanner."""

from __future__ import annotations

from botocore.exceptions import ClientError

from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner


class NatGatewayScanner(BaseScanner):
    service_name = "VPC"

    def scan(self) -> list[AwsResource]:
        resources: list[AwsResource] = []
        try:
            ec2 = self.session.client("ec2", region_name=self.region)
            paginator = ec2.get_paginator("describe_nat_gateways")
            for page in paginator.paginate():
                for nat in page.get("NatGateways", []):
                    state = nat.get("State", "unknown")
                    if state == "deleted":
                        continue
                    resources.append(
                        AwsResource(
                            resource_id=nat["NatGatewayId"],
                            name=self._tag_name(nat.get("Tags")),
                            service="VPC",
                            resource_type="NAT Gateway",
                            region=self.region,
                            status=state,
                            details=f"VPC: {nat.get('VpcId', 'N/A')}",
                            extra={"nat_gateway_id": nat["NatGatewayId"]},
                        )
                    )
        except ClientError:
            pass
        return resources
