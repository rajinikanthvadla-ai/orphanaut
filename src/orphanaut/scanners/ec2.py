"""EC2 instance scanner."""

from __future__ import annotations

from botocore.exceptions import ClientError

from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner


class Ec2InstanceScanner(BaseScanner):
    service_name = "EC2"

    def scan(self) -> list[AwsResource]:
        resources: list[AwsResource] = []
        try:
            ec2 = self.session.client("ec2", region_name=self.region)
            paginator = ec2.get_paginator("describe_instances")
            for page in paginator.paginate():
                for reservation in page.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        state = instance.get("State", {}).get("Name", "unknown")
                        if state in {"terminated", "shutting-down"}:
                            continue
                        instance_id = instance["InstanceId"]
                        instance_type = instance.get("InstanceType", "")
                        resources.append(
                            AwsResource(
                                resource_id=instance_id,
                                name=self._tag_name(instance.get("Tags")),
                                service="EC2",
                                resource_type="Instance",
                                region=self.region,
                                status=state,
                                details=f"Type: {instance_type}",
                                extra={"instance_id": instance_id},
                            )
                        )
        except ClientError:
            pass
        return resources
