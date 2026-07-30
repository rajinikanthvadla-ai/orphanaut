"""Base scanner interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from threading import Lock

import boto3

from orphanaut.aws.config import AWS_CONFIG
from orphanaut.models import AwsResource

_CLIENT_CREATION_LOCK = Lock()


class BaseScanner(ABC):
    service_name: str = "Unknown"

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
        return True

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

    def _tag_name(self, tags: list[dict[str, str]] | None) -> str:
        if not tags:
            return ""
        for tag in tags:
            if tag.get("Key") == "Name":
                return tag.get("Value", "")
        return ""
