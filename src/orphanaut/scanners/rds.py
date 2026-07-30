"""RDS instance and cluster scanner."""

from __future__ import annotations

from botocore.exceptions import ClientError

from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner


class RdsScanner(BaseScanner):
    service_name = "RDS"

    def scan(self) -> list[AwsResource]:
        resources: list[AwsResource] = []
        try:
            rds = self.client("rds")

            paginator = rds.get_paginator("describe_db_instances")
            for page in paginator.paginate():
                for db in page.get("DBInstances", []):
                    resources.append(
                        AwsResource(
                            resource_id=db["DBInstanceIdentifier"],
                            name=db["DBInstanceIdentifier"],
                            service="RDS",
                            resource_type="DB Instance",
                            region=self.region,
                            status=db.get("DBInstanceStatus", "unknown"),
                            details=(
                                f"Engine: {db.get('Engine', '')} {db.get('DBInstanceClass', '')}"
                            ),
                            extra={"db_instance_identifier": db["DBInstanceIdentifier"]},
                        )
                    )

            cluster_paginator = rds.get_paginator("describe_db_clusters")
            for page in cluster_paginator.paginate():
                for cluster in page.get("DBClusters", []):
                    resources.append(
                        AwsResource(
                            resource_id=cluster["DBClusterIdentifier"],
                            name=cluster["DBClusterIdentifier"],
                            service="RDS",
                            resource_type="DB Cluster",
                            region=self.region,
                            status=cluster.get("Status", "unknown"),
                            details=f"Engine: {cluster.get('Engine', '')}",
                            extra={"db_cluster_identifier": cluster["DBClusterIdentifier"]},
                        )
                    )
        except ClientError:
            raise
        return resources
