"""EC2 instance scanner."""

from __future__ import annotations

from botocore.exceptions import ClientError

from orphanaut.dependencies import Action, dep
from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner


class Ec2InstanceScanner(BaseScanner):
    service_name = "EC2"

    def scan(self) -> list[AwsResource]:
        resources: list[AwsResource] = []
        try:
            ec2 = self.client("ec2")
            paginator = ec2.get_paginator("describe_instances")
            for page in paginator.paginate():
                for reservation in page.get("Reservations", []):
                    for instance in reservation.get("Instances", []):
                        state = instance.get("State", {}).get("Name", "unknown")
                        if state in {"terminated", "shutting-down"}:
                            continue
                        instance_id = instance["InstanceId"]
                        instance_type = instance.get("InstanceType", "")
                        dependents = []
                        for mapping in instance.get("BlockDeviceMappings", []):
                            ebs = mapping.get("Ebs", {})
                            if not ebs.get("VolumeId"):
                                continue
                            if ebs.get("DeleteOnTermination"):
                                dependents.append(dep("EBS volume", ebs["VolumeId"],
                                                      note=mapping.get("DeviceName", "")))
                            else:
                                dependents.append(dep(
                                    "EBS volume", ebs["VolumeId"], Action.KEEP,
                                    "set to survive termination — still billed, delete it "
                                    "from the Storage tab"))
                        for eni in instance.get("NetworkInterfaces", []):
                            assoc = eni.get("Association", {})
                            if assoc.get("IpOwnerId") not in (None, "amazon"):
                                dependents.append(dep(
                                    "Elastic IP", assoc.get("PublicIp", ""), Action.KEEP,
                                    "stays allocated and starts billing — release it too"))
                        resources.append(
                            AwsResource(
                                resource_id=instance_id,
                                name=self._tag_name(instance.get("Tags")),
                                service="EC2",
                                resource_type="Instance",
                                region=self.region,
                                status=state,
                                details=f"Type: {instance_type}",
                                extra={"instance_id": instance_id, "dependents": dependents},
                            )
                        )
        except ClientError:
            raise
        return resources
