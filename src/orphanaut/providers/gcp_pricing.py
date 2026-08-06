"""Rough monthly cost estimates for GCP resources."""

from __future__ import annotations

import re

from orphanaut.models import CloudResource

_HOURS_PER_MONTH = 730
_DISK_GB_MONTH = 0.08
_STATIC_IP_IDLE = 0.004
_STORAGE_GB_MONTH = 0.02

_TYPE_RE = re.compile(r"Type:\s*(\S+)")
_DISK_SIZE_RE = re.compile(r"([\d.]+)\s*GiB")


def estimate_gcp_monthly_cost(resource: CloudResource) -> float | None:
    if resource.resource_type == "Instance":
        if resource.status in {"terminated", "stopping"}:
            return 0.0
        match = _TYPE_RE.search(resource.details)
        machine = match.group(1).lower() if match else ""
        if "e2-micro" in machine:
            return round(0.008 * _HOURS_PER_MONTH, 2)
        if "e2-small" in machine:
            return round(0.017 * _HOURS_PER_MONTH, 2)
        if "e2-medium" in machine:
            return round(0.034 * _HOURS_PER_MONTH, 2)
        return round(0.05 * _HOURS_PER_MONTH, 2)

    if resource.resource_type == "Disk":
        match = _DISK_SIZE_RE.search(resource.details)
        size = float(match.group(1)) if match else None
        return round(size * _DISK_GB_MONTH, 2) if size is not None else None

    if resource.resource_type == "Static IP" and resource.status == "reserved":
        return round(_STATIC_IP_IDLE * _HOURS_PER_MONTH, 2)

    if resource.resource_type == "Bucket":
        return 2.0

    return None
