"""EBS volume scanner."""

from __future__ import annotations

from botocore.exceptions import ClientError

from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner


class EbsVolumeScanner(BaseScanner):
    service_name = "EBS"

    def scan(self) -> list[AwsResource]:
        resources: list[AwsResource] = []
        try:
            ec2 = self.client("ec2")
            paginator = ec2.get_paginator("describe_volumes")
            for page in paginator.paginate():
                for volume in page.get("Volumes", []):
                    state = volume.get("State", "unknown")
                    attachments = volume.get("Attachments", [])
                    size = volume.get("Size", 0)
                    vol_type = volume.get("VolumeType", "")
                    attached = "attached" if attachments else "unattached"
                    resources.append(
                        AwsResource(
                            resource_id=volume["VolumeId"],
                            name=self._tag_name(volume.get("Tags")),
                            service="EBS",
                            resource_type="Volume",
                            region=self.region,
                            status=f"{state} ({attached})",
                            details=f"{size} GiB, {vol_type}",
                            extra={"volume_id": volume["VolumeId"]},
                        )
                    )
        except ClientError:
            raise
        return resources
