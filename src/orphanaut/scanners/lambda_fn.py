"""Lambda function scanner."""

from __future__ import annotations

from botocore.exceptions import ClientError

from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner


class LambdaScanner(BaseScanner):
    service_name = "Lambda"

    def scan(self) -> list[AwsResource]:
        resources: list[AwsResource] = []
        try:
            client = self.session.client("lambda", region_name=self.region)
            paginator = client.get_paginator("list_functions")
            for page in paginator.paginate():
                for fn in page.get("Functions", []):
                    resources.append(
                        AwsResource(
                            resource_id=fn["FunctionArn"],
                            name=fn["FunctionName"],
                            service="Lambda",
                            resource_type="Function",
                            region=self.region,
                            status=fn.get("State", "Active"),
                            details=f"Runtime: {fn.get('Runtime', 'N/A')}, Memory: {fn.get('MemorySize', 0)} MB",
                            extra={"function_name": fn["FunctionName"]},
                        )
                    )
        except ClientError:
            pass
        return resources
