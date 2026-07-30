"""Elastic IP scanner."""

from __future__ import annotations

from botocore.exceptions import ClientError

from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner


class ElasticIpScanner(BaseScanner):
    service_name = "EC2"

    def scan(self) -> list[AwsResource]:
        resources: list[AwsResource] = []
        try:
            ec2 = self.client("ec2")
            response = ec2.describe_addresses()
            for addr in response.get("Addresses", []):
                allocation_id = addr.get("AllocationId", addr.get("PublicIp", ""))
                associated = "associated" if addr.get("InstanceId") else "unassociated"
                resources.append(
                    AwsResource(
                        resource_id=allocation_id,
                        name=addr.get("PublicIp", ""),
                        service="EC2",
                        resource_type="Elastic IP",
                        region=self.region,
                        status=associated,
                        details=f"IP: {addr.get('PublicIp', 'N/A')}",
                        extra={
                            "allocation_id": addr.get("AllocationId"),
                            "public_ip": addr.get("PublicIp"),
                        },
                    )
                )
        except ClientError:
            raise
        return resources
