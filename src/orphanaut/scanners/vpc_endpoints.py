"""VPC endpoint scanner."""

from __future__ import annotations

from botocore.exceptions import ClientError

from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner


class VpcEndpointScanner(BaseScanner):
    service_name = "VPC"

    def scan(self) -> list[AwsResource]:
        resources: list[AwsResource] = []
        try:
            ec2 = self.session.client("ec2", region_name=self.region)
            paginator = ec2.get_paginator("describe_vpc_endpoints")
            for page in paginator.paginate():
                for endpoint in page.get("VpcEndpoints", []):
                    ep_type = endpoint.get("VpcEndpointType", "Gateway")
                    resources.append(
                        AwsResource(
                            resource_id=endpoint["VpcEndpointId"],
                            name=self._tag_name(endpoint.get("Tags")),
                            service="VPC",
                            resource_type=f"{ep_type} Endpoint",
                            region=self.region,
                            status=endpoint.get("State", "unknown"),
                            details=f"Service: {endpoint.get('ServiceName', 'N/A')}",
                            extra={"vpc_endpoint_id": endpoint["VpcEndpointId"]},
                        )
                    )
        except ClientError:
            pass
        return resources
