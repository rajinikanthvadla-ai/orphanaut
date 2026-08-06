"""Provider-aware cost estimation router."""

from __future__ import annotations

from orphanaut.aws.pricing import estimate_monthly_cost as estimate_aws_cost
from orphanaut.aws.pricing import format_monthly_cost
from orphanaut.models import CloudProvider, CloudResource
from orphanaut.providers.azure_pricing import estimate_azure_monthly_cost
from orphanaut.providers.gcp_pricing import estimate_gcp_monthly_cost

__all__ = ["estimate_monthly_cost", "format_monthly_cost"]


def estimate_monthly_cost(resource: CloudResource) -> float | None:
    match resource.provider:
        case CloudProvider.AWS:
            return estimate_aws_cost(resource)
        case CloudProvider.AZURE:
            return estimate_azure_monthly_cost(resource)
        case CloudProvider.GCP:
            return estimate_gcp_monthly_cost(resource)
        case _:
            return None
