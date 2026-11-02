"""EKS cluster scanner."""

from __future__ import annotations

from botocore.exceptions import ClientError

from orphanaut.dependencies import Action, dep
from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner


class EksScanner(BaseScanner):
    service_name = "EKS"

    def scan(self) -> list[AwsResource]:
        resources: list[AwsResource] = []
        try:
            eks = self.client("eks")
            paginator = eks.get_paginator("list_clusters")
            for page in paginator.paginate():
                for cluster_name in page.get("clusters", []):
                    cluster = eks.describe_cluster(name=cluster_name)["cluster"]
                    nodegroups = eks.list_nodegroups(clusterName=cluster_name).get(
                        "nodegroups", [])
                    fargate = eks.list_fargate_profiles(clusterName=cluster_name).get(
                        "fargateProfileNames", [])
                    resources.append(
                        AwsResource(
                            resource_id=cluster["arn"],
                            name=cluster["name"],
                            service="EKS",
                            resource_type="Cluster",
                            region=self.region,
                            status=cluster.get("status", "ACTIVE"),
                            details=f"Version: {cluster.get('version', 'N/A')}",
                            extra={
                                "cluster_name": cluster["name"],
                                "nodegroups": nodegroups,
                                "fargate_profiles": fargate,
                                "dependents": [
                                    dep("Managed node group", n, note="its EC2 nodes terminate")
                                    for n in nodegroups
                                ]
                                + [dep("Fargate profile", f) for f in fargate]
                                + [dep("Load balancers / volumes created by Kubernetes",
                                       "if any", Action.KEEP,
                                       "delete them from the Networking/Storage tabs")],
                            },
                        )
                    )
        except ClientError:
            raise
        return resources
