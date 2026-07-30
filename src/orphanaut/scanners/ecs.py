"""ECS cluster scanner."""

from __future__ import annotations

from botocore.exceptions import ClientError

from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner


class EcsScanner(BaseScanner):
    service_name = "ECS"

    def scan(self) -> list[AwsResource]:
        resources: list[AwsResource] = []
        try:
            ecs = self.session.client("ecs", region_name=self.region)
            paginator = ecs.get_paginator("list_clusters")
            for page in paginator.paginate():
                cluster_arns = page.get("clusterArns", [])
                if not cluster_arns:
                    continue
                described = ecs.describe_clusters(clusters=cluster_arns, include=["STATISTICS"])
                for cluster in described.get("clusters", []):
                    resources.append(
                        AwsResource(
                            resource_id=cluster["clusterArn"],
                            name=cluster["clusterName"],
                            service="ECS",
                            resource_type="Cluster",
                            region=self.region,
                            status=cluster.get("status", "ACTIVE"),
                            details=f"Tasks: {cluster.get('runningTasksCount', 0)} running, "
                            f"{cluster.get('activeServicesCount', 0)} services",
                            extra={"cluster_arn": cluster["clusterArn"]},
                        )
                    )
        except ClientError:
            pass
        return resources
