"""CloudWatch Logs scanner."""

from __future__ import annotations

from botocore.exceptions import ClientError

from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner


class CloudWatchLogsScanner(BaseScanner):
    service_name = "CloudWatch"

    def scan(self) -> list[AwsResource]:
        resources: list[AwsResource] = []
        try:
            client = self.session.client("logs", region_name=self.region)
            paginator = client.get_paginator("describe_log_groups")
            for page in paginator.paginate():
                for group in page.get("logGroups", []):
                    stored = group.get("storedBytes", 0)
                    size_mb = round(stored / (1024 * 1024), 2) if stored else 0
                    resources.append(
                        AwsResource(
                            resource_id=group["logGroupName"],
                            name=group["logGroupName"],
                            service="CloudWatch",
                            resource_type="Log Group",
                            region=self.region,
                            status="active",
                            details=f"Stored: {size_mb} MB, Retention: {group.get('retentionInDays', 'never')} days",
                            extra={"log_group_name": group["logGroupName"]},
                        )
                    )
        except ClientError:
            pass
        return resources
