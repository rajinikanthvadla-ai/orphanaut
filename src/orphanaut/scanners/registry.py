"""Scanner registry and orchestration."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

import boto3

from orphanaut.aws.regions import get_all_regions
from orphanaut.models import AwsResource
from orphanaut.scanners.base import BaseScanner
from orphanaut.scanners.cloudwatch import CloudWatchLogsScanner
from orphanaut.scanners.dynamodb import DynamoDbScanner
from orphanaut.scanners.ebs import EbsVolumeScanner
from orphanaut.scanners.ec2 import Ec2InstanceScanner
from orphanaut.scanners.ecs import EcsScanner
from orphanaut.scanners.eip import ElasticIpScanner
from orphanaut.scanners.eks import EksScanner
from orphanaut.scanners.elasticache import ElastiCacheScanner
from orphanaut.scanners.elb import LoadBalancerScanner
from orphanaut.scanners.lambda_fn import LambdaScanner
from orphanaut.scanners.lightsail import LightsailScanner
from orphanaut.scanners.nat import NatGatewayScanner
from orphanaut.scanners.rds import RdsScanner
from orphanaut.scanners.route53 import Route53Scanner
from orphanaut.scanners.s3 import S3Scanner
from orphanaut.scanners.snapshots import EbsSnapshotScanner
from orphanaut.scanners.vpc_endpoints import VpcEndpointScanner

REGIONAL_SCANNERS: list[type[BaseScanner]] = [
    Ec2InstanceScanner,
    EbsVolumeScanner,
    EbsSnapshotScanner,
    ElasticIpScanner,
    NatGatewayScanner,
    LoadBalancerScanner,
    RdsScanner,
    LambdaScanner,
    EcsScanner,
    EksScanner,
    ElastiCacheScanner,
    DynamoDbScanner,
    CloudWatchLogsScanner,
    VpcEndpointScanner,
    LightsailScanner,
]

GLOBAL_SCANNERS: list[type[BaseScanner]] = [
    S3Scanner,
    Route53Scanner,
]


def scan_all(
    session: boto3.Session,
    on_progress: Callable[[str], None] | None = None,
    max_workers: int = 8,
) -> list[AwsResource]:
    """Scan all regions and global services for billable resources."""
    regions = get_all_regions(session)
    all_resources: list[AwsResource] = []
    tasks: list[tuple[str, type[BaseScanner]]] = []

    for region in regions:
        for scanner_cls in REGIONAL_SCANNERS:
            tasks.append((region, scanner_cls))

    for scanner_cls in GLOBAL_SCANNERS:
        tasks.append(("global", scanner_cls))

    completed = 0
    total = len(tasks)

    def run_task(region: str, scanner_cls: type[BaseScanner]) -> list[AwsResource]:
        scanner = scanner_cls(session, region)
        return scanner.scan()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_task, region, scanner_cls): (region, scanner_cls)
            for region, scanner_cls in tasks
        }
        for future in as_completed(futures):
            region, scanner_cls = futures[future]
            completed += 1
            if on_progress:
                on_progress(
                    f"Scanning {scanner_cls.service_name} in {region} "
                    f"({completed}/{total})"
                )
            try:
                all_resources.extend(future.result())
            except Exception:
                pass

    return sorted(all_resources, key=lambda r: (r.region, r.service, r.resource_id))
