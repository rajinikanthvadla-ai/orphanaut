"""Azure region lists and display helpers."""

from __future__ import annotations

AZURE_COMMON_REGIONS = frozenset(
    {
        "eastus",
        "westus2",
        "centralus",
        "northeurope",
        "southeastasia",
    }
)

AZURE_ALL_REGIONS = [
    "australiaeast",
    "brazilsouth",
    "canadacentral",
    "centralindia",
    "centralus",
    "eastasia",
    "eastus",
    "eastus2",
    "francecentral",
    "germanywestcentral",
    "japaneast",
    "koreacentral",
    "northeurope",
    "southafricanorth",
    "southeastasia",
    "swedencentral",
    "switzerlandnorth",
    "uaenorth",
    "uksouth",
    "westeurope",
    "westus",
    "westus2",
    "westus3",
]

AZURE_REGION_LABELS: dict[str, str] = {
    "eastus": "East US",
    "eastus2": "East US 2",
    "westus": "West US",
    "westus2": "West US 2",
    "westus3": "West US 3",
    "centralus": "Central US",
    "northeurope": "North Europe",
    "westeurope": "West Europe",
    "southeastasia": "Southeast Asia",
    "eastasia": "East Asia",
    "uksouth": "UK South",
    "japaneast": "Japan East",
    "australiaeast": "Australia East",
    "canadacentral": "Canada Central",
    "centralindia": "Central India",
    "brazilsouth": "Brazil South",
    "francecentral": "France Central",
    "germanywestcentral": "Germany West Central",
    "koreacentral": "Korea Central",
    "southafricanorth": "South Africa North",
    "swedencentral": "Sweden Central",
    "switzerlandnorth": "Switzerland North",
    "uaenorth": "UAE North",
}


def azure_region_display_name(region: str) -> str:
    label = AZURE_REGION_LABELS.get(region)
    return f"{region} — {label}" if label else region
