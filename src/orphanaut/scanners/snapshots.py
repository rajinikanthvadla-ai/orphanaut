"""EBS snapshot scanner."""

from __future__ import annotations

from botocore.exceptions import ClientError

from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner


class EbsSnapshotScanner(BaseScanner):
    service_name = "EBS"

    def scan(self) -> list[AwsResource]:
        resources: list[AwsResource] = []
        if not self._account_id:
            return resources
        try:
            ec2 = self.client("ec2")
            paginator = ec2.get_paginator("describe_snapshots")
            for page in paginator.paginate(OwnerIds=[self._account_id]):
                for snap in page.get("Snapshots", []):
                    size = snap.get("VolumeSize", 0)
                    resources.append(
                        AwsResource(
                            resource_id=snap["SnapshotId"],
                            name=self._tag_name(snap.get("Tags")),
                            service="EBS",
                            resource_type="Snapshot",
                            region=self.region,
                            status=snap.get("State", "completed"),
                            details=f"{size} GiB",
                            extra={"snapshot_id": snap["SnapshotId"]},
                        )
                    )
        except ClientError:
            raise
        return resources
