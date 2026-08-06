"""Scanner registry and orchestration."""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Callable

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from orphanaut.aws.config import AWS_CONFIG
from orphanaut.aws.regions import get_all_regions
from orphanaut.models import CloudProvider, CloudResource
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
from orphanaut.scanners.security_groups import SecurityGroupScanner
from orphanaut.scanners.snapshots import EbsSnapshotScanner
from orphanaut.scanners.vpc_endpoints import VpcEndpointScanner

# Fast scanners — common billable resources students leave running.
FAST_REGIONAL_SCANNERS: list[type[BaseScanner]] = [
    Ec2InstanceScanner,
    EbsVolumeScanner,
    ElasticIpScanner,
    SecurityGroupScanner,
    NatGatewayScanner,
    LoadBalancerScanner,
    RdsScanner,
    LambdaScanner,
]

# Slower scanners — run after fast results are shown.
SLOW_REGIONAL_SCANNERS: list[type[BaseScanner]] = [
    EbsSnapshotScanner,
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

REGIONAL_SCANNERS: list[type[BaseScanner]] = FAST_REGIONAL_SCANNERS + SLOW_REGIONAL_SCANNERS

HEARTBEAT_SECONDS = 3


@dataclass
class ScanProgress:
    message: str
    completed: int
    total: int
    resources_found: int
    new_resources: list[CloudResource] = field(default_factory=list)
    phase: str = ""
    failed_checks: int = 0
    last_error: str = ""


def _get_account_id(session: boto3.Session) -> str:
    sts = session.client("sts", config=AWS_CONFIG)
    return sts.get_caller_identity()["Account"]


def _build_tasks(
    regions: list[str],
    scanner_classes: list[type[BaseScanner]],
    *,
    global_scanners: list[type[BaseScanner]] | None = None,
) -> list[tuple[str, type[BaseScanner]]]:
    tasks: list[tuple[str, type[BaseScanner]]] = []
    for region in regions:
        for scanner_cls in scanner_classes:
            if scanner_cls.supports_region(region):
                tasks.append((region, scanner_cls))
    for scanner_cls in global_scanners or []:
        tasks.append(("global", scanner_cls))
    return tasks


def _run_scan_batch(
    session: boto3.Session,
    tasks: list[tuple[str, type[BaseScanner]]],
    account_id: str,
    *,
    on_progress: Callable[[ScanProgress], None] | None,
    completed_offset: int,
    total: int,
    phase: str,
    resources_so_far: list[CloudResource],
    failures_so_far: list[str],
    max_workers: int = 10,
) -> tuple[list[CloudResource], list[str]]:
    if not tasks:
        return [], []

    batch_resources: list[CloudResource] = []
    batch_failures: list[str] = []
    completed = completed_offset

    def run_task(region: str, scanner_cls: type[BaseScanner]) -> list[CloudResource]:
        scanner = scanner_cls(session, region, account_id=account_id)
        return scanner.scan()

    def emit(
        message: str,
        *,
        new_items: list[CloudResource] | None = None,
        last_error: str = "",
    ) -> None:
        if not on_progress:
            return
        on_progress(
            ScanProgress(
                message=message,
                completed=completed,
                total=total,
                resources_found=len(resources_so_far) + len(batch_resources),
                new_resources=new_items or [],
                phase=phase,
                failed_checks=len(failures_so_far) + len(batch_failures),
                last_error=last_error,
            )
        )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(run_task, region, scanner_cls): (region, scanner_cls)
            for region, scanner_cls in tasks
        }
        pending = set(futures.keys())

        while pending:
            done, pending = wait(pending, timeout=HEARTBEAT_SECONDS, return_when=FIRST_COMPLETED)

            if not done:
                emit(
                    f"{phase}: still working ({completed}/{total}) — "
                    f"{len(resources_so_far) + len(batch_resources)} found so far"
                )
                continue

            for future in done:
                region, scanner_cls = futures[future]
                completed += 1
                new_items: list[CloudResource] = []
                error_message = ""
                try:
                    new_items = future.result()
                    batch_resources.extend(new_items)
                except ClientError as exc:
                    error = exc.response.get("Error", {})
                    code = error.get("Code", "AWS error")
                    error_message = (
                        f"{scanner_cls.service_name} in {region}: "
                        f"{code} — {error.get('Message', str(exc))}"
                    )
                    batch_failures.append(error_message)
                except BotoCoreError as exc:
                    error_message = f"{scanner_cls.service_name} in {region}: {exc}"
                    batch_failures.append(error_message)
                except Exception as exc:
                    error_message = f"{scanner_cls.service_name} in {region}: {exc}"
                    batch_failures.append(error_message)
                emit(
                    f"{phase}: {scanner_cls.service_name} in {region} "
                    f"({completed}/{total}) — "
                    f"{len(resources_so_far) + len(batch_resources)} found"
                    + (
                        f", {len(failures_so_far) + len(batch_failures)} unavailable"
                        if failures_so_far or batch_failures
                        else ""
                    ),
                    new_items=new_items,
                    last_error=error_message,
                )

    return batch_resources, batch_failures


def scan_aws(
    session: boto3.Session,
    on_progress: Callable[[ScanProgress], None] | None = None,
    max_workers: int = 10,
    regions: list[str] | None = None,
) -> list[CloudResource]:
    """Scan selected regions and global services for billable resources."""
    if on_progress:
        on_progress(
            ScanProgress(
                message="Preparing scan...",
                completed=0,
                total=1,
                resources_found=0,
                phase="Starting",
            )
        )

    if regions is None:
        regions = get_all_regions(session)
    else:
        regions = sorted(set(regions))

    if not regions:
        if on_progress:
            on_progress(
                ScanProgress(
                    message="No regions selected — choose at least one region",
                    completed=0,
                    total=0,
                    resources_found=0,
                    phase="Done",
                )
            )
        return []

    account_id = _get_account_id(session)

    fast_tasks = _build_tasks(regions, FAST_REGIONAL_SCANNERS, global_scanners=GLOBAL_SCANNERS)
    slow_tasks = _build_tasks(regions, SLOW_REGIONAL_SCANNERS)
    total = len(fast_tasks) + len(slow_tasks)

    if on_progress:
        on_progress(
            ScanProgress(
                message=(
                    f"Starting fast scan across {len(regions)} regions ({total} checks total)..."
                ),
                completed=0,
                total=total,
                resources_found=0,
                phase="Fast scan",
            )
        )

    all_resources: list[CloudResource] = []
    failures: list[str] = []

    fast_found, fast_failures = _run_scan_batch(
        session,
        fast_tasks,
        account_id,
        on_progress=on_progress,
        completed_offset=0,
        total=total,
        phase="Fast scan",
        resources_so_far=all_resources,
        failures_so_far=failures,
        max_workers=max_workers,
    )
    all_resources.extend(fast_found)
    failures.extend(fast_failures)

    if slow_tasks and on_progress:
        on_progress(
            ScanProgress(
                message=(
                    f"Fast scan done — {len(all_resources)} found. "
                    f"Checking snapshots, logs, and other services..."
                ),
                completed=len(fast_tasks),
                total=total,
                resources_found=len(all_resources),
                phase="Deep scan",
                failed_checks=len(failures),
            )
        )

    slow_found, slow_failures = _run_scan_batch(
        session,
        slow_tasks,
        account_id,
        on_progress=on_progress,
        completed_offset=len(fast_tasks),
        total=total,
        phase="Deep scan",
        resources_so_far=all_resources,
        failures_so_far=failures,
        max_workers=max_workers,
    )
    all_resources.extend(slow_found)
    failures.extend(slow_failures)

    if on_progress:
        on_progress(
            ScanProgress(
                message=(
                    f"Scan complete — {len(all_resources)} resources found"
                    + (f", {len(failures)} checks unavailable" if failures else "")
                ),
                completed=total,
                total=total,
                resources_found=len(all_resources),
                phase="Done",
                failed_checks=len(failures),
                last_error=failures[-1] if failures else "",
            )
        )

    return sorted(all_resources, key=lambda r: (r.region, r.service, r.resource_id))


def scan_all(
    provider_session: object,
    on_progress: Callable[[ScanProgress], None] | None = None,
    max_workers: int = 10,
    regions: list[str] | None = None,
) -> list[CloudResource]:
    """Dispatch scan to the correct cloud provider."""
    from orphanaut.providers.session import ProviderSession
    from orphanaut.scanners.azure_registry import scan_azure
    from orphanaut.scanners.gcp_registry import scan_gcp

    if not isinstance(provider_session, ProviderSession):
        return scan_aws(
            provider_session,  # type: ignore[arg-type]
            on_progress=on_progress,
            max_workers=max_workers,
            regions=regions,
        )

    match provider_session.provider:
        case CloudProvider.AWS:
            return scan_aws(
                provider_session.session,
                on_progress=on_progress,
                max_workers=max_workers,
                regions=regions,
            )
        case CloudProvider.AZURE:
            return scan_azure(
                provider_session.session,
                regions=regions or [],
                on_progress=on_progress,
                max_workers=max_workers,
            )
        case CloudProvider.GCP:
            return scan_gcp(
                provider_session.session,
                regions=regions or [],
                on_progress=on_progress,
                max_workers=max_workers,
            )
        case _:
            return []
