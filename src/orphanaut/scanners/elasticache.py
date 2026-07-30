"""ElastiCache cluster scanner."""

from __future__ import annotations

from botocore.exceptions import ClientError

from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner


class ElastiCacheScanner(BaseScanner):
    service_name = "ElastiCache"

    def scan(self) -> list[AwsResource]:
        resources: list[AwsResource] = []
        try:
            client = self.session.client("elasticache", region_name=self.region)
            paginator = client.get_paginator("describe_cache_clusters")
            for page in paginator.paginate(ShowCacheNodeInfo=True):
                for cluster in page.get("CacheClusters", []):
                    resources.append(
                        AwsResource(
                            resource_id=cluster["CacheClusterId"],
                            name=cluster.get("CacheClusterId", ""),
                            service="ElastiCache",
                            resource_type="Cache Cluster",
                            region=self.region,
                            status=cluster.get("CacheClusterStatus", "unknown"),
                            details=f"Engine: {cluster.get('Engine', '')} {cluster.get('CacheNodeType', '')}",
                            extra={"cache_cluster_id": cluster["CacheClusterId"]},
                        )
                    )
        except ClientError:
            pass
        return resources
