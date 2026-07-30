"""DynamoDB table scanner."""

from __future__ import annotations

from botocore.exceptions import ClientError

from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner


class DynamoDbScanner(BaseScanner):
    service_name = "DynamoDB"

    def scan(self) -> list[AwsResource]:
        resources: list[AwsResource] = []
        try:
            client = self.client("dynamodb")
            paginator = client.get_paginator("list_tables")
            for page in paginator.paginate():
                for table_name in page.get("TableNames", []):
                    table = client.describe_table(TableName=table_name)["Table"]
                    billing_mode = table.get("BillingModeSummary", {}).get(
                        "BillingMode", "PROVISIONED"
                    )
                    resources.append(
                        AwsResource(
                            resource_id=table_name,
                            name=table_name,
                            service="DynamoDB",
                            resource_type="Table",
                            region=self.region,
                            status=table.get("TableStatus", "ACTIVE"),
                            details=f"Billing: {billing_mode}",
                            extra={"table_name": table_name},
                        )
                    )
        except ClientError:
            raise
        return resources
