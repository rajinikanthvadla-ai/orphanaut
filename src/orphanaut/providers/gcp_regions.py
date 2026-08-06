"""GCP region lists and display helpers."""

from __future__ import annotations

GCP_COMMON_REGIONS = frozenset(
    {
        "us-central1",
        "us-east1",
        "europe-west1",
        "asia-southeast1",
        "us-west1",
    }
)

GCP_ALL_REGIONS = [
    "us-central1",
    "us-east1",
    "us-east4",
    "us-west1",
    "us-west2",
    "us-west3",
    "us-west4",
    "europe-west1",
    "europe-west2",
    "europe-west3",
    "europe-west4",
    "europe-west6",
    "europe-north1",
    "asia-east1",
    "asia-east2",
    "asia-northeast1",
    "asia-northeast2",
    "asia-northeast3",
    "asia-south1",
    "asia-southeast1",
    "asia-southeast2",
    "australia-southeast1",
    "australia-southeast2",
    "northamerica-northeast1",
    "southamerica-east1",
]

GCP_REGION_LABELS: dict[str, str] = {
    "us-central1": "Iowa",
    "us-east1": "South Carolina",
    "us-east4": "Northern Virginia",
    "us-west1": "Oregon",
    "us-west2": "Los Angeles",
    "us-west3": "Salt Lake City",
    "us-west4": "Las Vegas",
    "europe-west1": "Belgium",
    "europe-west2": "London",
    "europe-west3": "Frankfurt",
    "europe-west4": "Netherlands",
    "europe-west6": "Zurich",
    "europe-north1": "Finland",
    "asia-east1": "Taiwan",
    "asia-east2": "Hong Kong",
    "asia-northeast1": "Tokyo",
    "asia-northeast2": "Osaka",
    "asia-northeast3": "Seoul",
    "asia-south1": "Mumbai",
    "asia-southeast1": "Singapore",
    "asia-southeast2": "Jakarta",
    "australia-southeast1": "Sydney",
    "australia-southeast2": "Melbourne",
    "northamerica-northeast1": "Montreal",
    "southamerica-east1": "São Paulo",
}


def gcp_region_display_name(region: str) -> str:
    label = GCP_REGION_LABELS.get(region)
    return f"{region} — {label}" if label else region
