"""EKS cluster scanner."""

from __future__ import annotations

from botocore.exceptions import ClientError

from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner


class EksScanner(BaseScanner):
    service_name = "EKS"

    def scan(self) -> list[AwsResource]:
        resources: list[AwsResource] = []
        try:
            eks = self.session.client("eks", region_name=self.region)
            paginator = eks.get_paginator("list_clusters")
            for page in paginator.paginate():
                for cluster_name in page.get("clusters", []):
                    cluster = eks.describe_cluster(name=cluster_name)["cluster"]
                    resources.append(
                        AwsResource(
                            resource_id=cluster["arn"],
                            name=cluster["name"],
                            service="EKS",
                            resource_type="Cluster",
                            region=self.region,
                            status=cluster.get("status", "ACTIVE"),
                            details=f"Version: {cluster.get('version', 'N/A')}",
                            extra={"cluster_name": cluster["name"]},
                        )
                    )
        except ClientError:
            pass
        return resources
