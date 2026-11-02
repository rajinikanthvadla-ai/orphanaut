"""Rough hourly prices for AI/ML instances and units (US East list prices).

Like the rest of Orphanaut's estimates these only show the scale of what a
forgotten resource costs — they are not a bill.
"""

from __future__ import annotations

HOURS_PER_MONTH = 730

# Size multiplier relative to a "large" instance.
_SIZE_UNITS = {
    "medium": 0.5,
    "large": 1,
    "xlarge": 2,
    "2xlarge": 4,
    "4xlarge": 8,
    "8xlarge": 16,
    "9xlarge": 18,
    "12xlarge": 24,
    "16xlarge": 32,
    "18xlarge": 36,
    "24xlarge": 48,
    "32xlarge": 64,
    "48xlarge": 96,
}

# Approximate SageMaker USD/hour for one "large" unit of each family.
_FAMILY_PER_LARGE = {
    "t2": 0.07,
    "t3": 0.10,
    "m4": 0.12,
    "m5": 0.115,
    "m6i": 0.115,
    "m7i": 0.12,
    "c4": 0.11,
    "c5": 0.102,
    "c6i": 0.102,
    "c7i": 0.107,
    "r5": 0.151,
    "r6i": 0.151,
    "g4dn": 0.368,
    "g5": 0.704,
    "g6": 0.503,
    "g6e": 0.934,
    "p3": 0.956,
    "p4d": 0.785,
    "p4de": 0.98,
    "p5": 1.18,
    "inf1": 0.15,
    "inf2": 0.49,
    "trn1": 0.37,
}


def ml_instance_hourly(instance_type: str) -> float | None:
    """``ml.g5.xlarge`` → ~1.41 USD/hour. Unknown types return None."""
    parts = instance_type.lower().removeprefix("ml.").split(".")
    if len(parts) != 2:
        return None
    family, size = parts
    per_large = _FAMILY_PER_LARGE.get(family)
    units = _SIZE_UNITS.get(size)
    if per_large is None or units is None:
        return None
    return per_large * units


def ml_monthly(instance_type: str, count: int = 1) -> float | None:
    hourly = ml_instance_hourly(instance_type)
    return None if hourly is None else round(hourly * max(count, 1) * HOURS_PER_MONTH, 2)


def hourly_to_monthly(hourly: float) -> float:
    return round(hourly * HOURS_PER_MONTH, 2)
