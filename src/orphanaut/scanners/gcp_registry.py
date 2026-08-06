"""GCP scanner registry."""

from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Callable

from orphanaut.models import CloudResource
from orphanaut.providers.session import GcpSession
from orphanaut.scanners.gcp_addresses import GcpAddressScanner
from orphanaut.scanners.gcp_base import GcpBaseScanner
from orphanaut.scanners.gcp_disks import GcpDiskScanner
from orphanaut.scanners.gcp_instances import GcpInstanceScanner
from orphanaut.scanners.gcp_storage import GcpStorageScanner
from orphanaut.scanners.registry import HEARTBEAT_SECONDS, ScanProgress

GCP_SCANNERS: list[type[GcpBaseScanner]] = [
    GcpInstanceScanner,
    GcpDiskScanner,
    GcpAddressScanner,
    GcpStorageScanner,
]


def scan_gcp(
    session: GcpSession,
    regions: list[str],
    on_progress: Callable[[ScanProgress], None] | None = None,
    max_workers: int = 4,
) -> list[CloudResource]:
    regions_set = set(regions)
    if not regions_set:
        return []

    tasks = GCP_SCANNERS
    total = len(tasks)
    all_resources: list[CloudResource] = []
    failures: list[str] = []
    completed = 0

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
                resources_found=len(all_resources),
                new_resources=new_items or [],
                phase="GCP scan",
                failed_checks=len(failures),
                last_error=last_error,
            )
        )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(scanner_cls(session, regions_set).scan): scanner_cls
            for scanner_cls in tasks
        }
        pending = set(futures.keys())
        while pending:
            done, pending = wait(pending, timeout=HEARTBEAT_SECONDS, return_when=FIRST_COMPLETED)
            if not done:
                emit(f"GCP scan: still working ({completed}/{total})")
                continue
            for future in done:
                scanner_cls = futures[future]
                completed += 1
                new_items: list[CloudResource] = []
                error_message = ""
                try:
                    new_items = future.result()
                    all_resources.extend(new_items)
                except Exception as exc:
                    error_message = f"{scanner_cls.service_name}: {exc}"
                    failures.append(error_message)
                emit(
                    f"GCP: {scanner_cls.service_name} ({completed}/{total})",
                    new_items=new_items,
                    last_error=error_message,
                )

    if on_progress:
        on_progress(
            ScanProgress(
                message=f"Scan complete — {len(all_resources)} resources found",
                completed=total,
                total=total,
                resources_found=len(all_resources),
                phase="Done",
                failed_checks=len(failures),
                last_error=failures[-1] if failures else "",
            )
        )

    return sorted(all_resources, key=lambda r: (r.region, r.service, r.resource_id))
