"""Base scanner interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

import boto3

from orphanaut.models import AwsResource


class BaseScanner(ABC):
    service_name: str = "Unknown"

    def __init__(self, session: boto3.Session, region: str) -> None:
        self.session = session
        self.region = region

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
