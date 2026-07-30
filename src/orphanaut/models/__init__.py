"""AWS resource data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AuthMethod(str, Enum):
    ACCESS_KEYS = "access_keys"
    SSO_PROFILE = "sso_profile"


@dataclass
class AuthConfig:
    method: AuthMethod
    access_key_id: str = ""
    secret_access_key: str = ""
    session_token: str = ""
    profile_name: str = ""
    region: str = "us-east-1"


@dataclass
class AwsResource:
    """A billable or leftover AWS resource discovered during a scan."""

    resource_id: str
    name: str
    service: str
    resource_type: str
    region: str
    status: str
    details: str
    deletable: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def display_key(self) -> str:
        return f"{self.region}:{self.service}:{self.resource_id}"

    def to_row(self) -> list[str]:
        return [
            self.region,
            self.service,
            self.resource_type,
            self.resource_id,
            self.name,
            self.status,
            self.details,
        ]

    COLUMNS = [
        "Region",
        "Service",
        "Type",
        "ID",
        "Name",
        "Status",
        "Details",
    ]
