"""Base scanner interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from threading import Lock

import boto3

from orphanaut.aws.config import AWS_CONFIG
from orphanaut.models import AwsResource

_CLIENT_CREATION_LOCK = Lock()
_REGION_CACHE: dict[str, frozenset[str]] = {}


def service_regions(service: str) -> frozenset[str]:
    """Regions where an AWS service has an endpoint (from botocore's bundled data)."""
    if service not in _REGION_CACHE:
        regions = boto3.Session().get_available_regions(service)
        _REGION_CACHE[service] = frozenset(regions)
    return _REGION_CACHE[service]


class BaseScanner(ABC):
    service_name: str = "Unknown"
    # When set, the scanner is skipped in regions where this AWS service doesn't exist.
    boto_service: str = ""

    def __init__(
        self,
        session: boto3.Session,
        region: str,
        account_id: str = "",
    ) -> None:
        self.session = session
        self.region = region
        self._account_id = account_id

    @classmethod
    def supports_region(cls, region: str) -> bool:
        if not cls.boto_service:
            return True
        regions = service_regions(cls.boto_service)
        return not regions or region in regions

    def client(self, service_name: str, *, region: str | None = None) -> object:
        # boto3 Session objects are not thread-safe while creating clients.
        # Scanners run concurrently, so serialize only client construction.
        with _CLIENT_CREATION_LOCK:
            return self.session.client(
                service_name,
                region_name=region or self.region,
                config=AWS_CONFIG,
            )

    @abstractmethod
    def scan(self) -> list[AwsResource]:
        """Scan the region and return discovered resources."""

    def paginate(self, client, operation: str, key: str, **kwargs):
        for page in client.get_paginator(operation).paginate(**kwargs):
            yield from page.get(key, [])

    def _tag_name(self, tags: list[dict[str, str]] | None) -> str:
        if not tags:
            return ""
        for tag in tags:
            if tag.get("Key") == "Name":
                return tag.get("Value", "")
        return ""
