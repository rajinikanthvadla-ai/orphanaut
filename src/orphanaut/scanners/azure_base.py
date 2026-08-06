"""Azure scanner base class."""

from __future__ import annotations

from abc import ABC, abstractmethod

from orphanaut.models import CloudProvider, CloudResource
from orphanaut.providers.session import AzureSession


class AzureBaseScanner(ABC):
    service_name: str = "Unknown"

    def __init__(self, session: AzureSession, regions: set[str]) -> None:
        self.session = session
        self.regions = regions

    @classmethod
    def supports_region(cls, region: str) -> bool:
        return True

    def _in_region(self, location: str) -> bool:
        return location in self.regions

    @abstractmethod
    def scan(self) -> list[CloudResource]:
        """Scan the region and return discovered resources."""

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
            provider=CloudProvider.AZURE,
            deletable=deletable,
            extra=extra or {},
        )
