"""S3 bucket scanner (global)."""

from __future__ import annotations

from botocore.exceptions import ClientError

from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner


class S3Scanner(BaseScanner):
    service_name = "S3"

    def scan(self) -> list[AwsResource]:
        resources: list[AwsResource] = []
        try:
            s3 = self.session.client("s3", region_name="us-east-1")
            response = s3.list_buckets()
            for bucket in response.get("Buckets", []):
                name = bucket["Name"]
                region = self._bucket_region(s3, name)
                resources.append(
                    AwsResource(
                        resource_id=name,
                        name=name,
                        service="S3",
                        resource_type="Bucket",
                        region=region,
                        status="active",
                        details=f"Created: {bucket.get('CreationDate', 'N/A')}",
                        extra={"bucket_name": name},
                    )
                )
        except ClientError:
            pass
        return resources

    def _bucket_region(self, s3_client, bucket_name: str) -> str:
        try:
            loc = s3_client.get_bucket_location(Bucket=bucket_name)
            region = loc.get("LocationConstraint") or "us-east-1"
            return region
        except ClientError:
            return "global"
