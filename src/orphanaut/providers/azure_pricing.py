"""Rough monthly cost estimates for Azure resources."""

from __future__ import annotations

import re

from orphanaut.models import CloudResource

_HOURS_PER_MONTH = 730
_DISK_GB_MONTH = 0.10
_PUBLIC_IP_IDLE = 0.004
_STORAGE_GB_MONTH = 0.02

_VM_SIZE_RE = re.compile(r"Size:\s*(\S+)")
_DISK_SIZE_RE = re.compile(r"([\d.]+)\s*GiB")


def estimate_azure_monthly_cost(resource: CloudResource) -> float | None:
    if resource.resource_type == "Virtual Machine":
        if resource.status.lower() in {"deallocated", "stopped", "deleting"}:
            return 0.0
        match = _VM_SIZE_RE.search(resource.details)
        if not match:
            return None
        size = match.group(1).lower()
        if "standard_b1s" in size:
            return round(0.0104 * _HOURS_PER_MONTH, 2)
        if "standard_b2s" in size:
            return round(0.0416 * _HOURS_PER_MONTH, 2)
        if "standard_d2" in size:
            return round(0.096 * _HOURS_PER_MONTH, 2)
        return round(0.05 * _HOURS_PER_MONTH, 2)

    if resource.resource_type == "Managed Disk":
        match = _DISK_SIZE_RE.search(resource.details)
        size = float(match.group(1)) if match else None
        return round(size * _DISK_GB_MONTH, 2) if size is not None else None

    if resource.resource_type == "Public IP" and resource.status == "unassociated":
        return round(_PUBLIC_IP_IDLE * _HOURS_PER_MONTH, 2)

    if resource.resource_type == "Storage Account":
        return 5.0

    return None
