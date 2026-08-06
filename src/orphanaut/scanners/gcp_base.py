"""GCP scanner base class."""

from __future__ import annotations

from abc import ABC, abstractmethod

from orphanaut.models import CloudProvider, CloudResource
from orphanaut.providers.session import GcpSession


class GcpBaseScanner(ABC):
    service_name: str = "Unknown"

    def __init__(self, session: GcpSession, regions: set[str]) -> None:
        self.session = session
        self.regions = regions

    @classmethod
    def supports_region(cls, region: str) -> bool:
        return True

    @abstractmethod
    def scan(self) -> list[CloudResource]:
        """Scan selected regions and return discovered resources."""

    def _resource(
        self,
        *,
        resource_id: str,
        name: str,
        service: str,
        resource_type: str,
        region: str,
        status: str,
        details: str,
        deletable: bool = True,
        extra: dict | None = None,
    ) -> CloudResource:
        return CloudResource(
            resource_id=resource_id,
            name=name,
            service=service,
            resource_type=resource_type,
            region=region,
            status=status,
            details=details,
            provider=CloudProvider.GCP,
            deletable=deletable,
            extra=extra or {},
        )

    def _zone_in_regions(self, zone: str) -> bool:
        return any(zone.startswith(region) for region in self.regions)

    def _location_in_regions(self, location: str) -> bool:
        location = location.lower()
        return any(
            location == region.lower() or location.startswith(region.lower())
            for region in self.regions
        )
