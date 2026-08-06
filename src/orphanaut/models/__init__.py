"""Cloud resource and authentication data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class CloudProvider(str, Enum):
    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"

    @property
    def label(self) -> str:
        match self:
            case CloudProvider.AWS:
                return "AWS"
            case CloudProvider.AZURE:
                return "Azure"
            case CloudProvider.GCP:
                return "GCP"
            case _:
                return self.value


class AuthMethod(str, Enum):
    ACCESS_KEYS = "access_keys"
    SSO_PROFILE = "sso_profile"
    SERVICE_PRINCIPAL = "service_principal"
    SERVICE_ACCOUNT = "service_account"


@dataclass
class AuthConfig:
    provider: CloudProvider = CloudProvider.AWS
    method: AuthMethod = AuthMethod.ACCESS_KEYS
    # AWS
    access_key_id: str = ""
    secret_access_key: str = ""
    session_token: str = ""
    profile_name: str = ""
    region: str = "us-east-1"
    # Azure
    tenant_id: str = ""
    client_id: str = ""
    client_secret: str = ""
    subscription_id: str = ""
    # GCP
    project_id: str = ""
    service_account_json: str = ""


@dataclass
class CloudResource:
    """A billable or leftover cloud resource discovered during a scan."""

    resource_id: str
    name: str
    service: str
    resource_type: str
    region: str
    status: str
    details: str
    provider: CloudProvider = CloudProvider.AWS
    deletable: bool = True
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def display_key(self) -> str:
        return f"{self.provider.value}:{self.region}:{self.service}:{self.resource_id}"

    def to_row(self) -> list[str]:
        return [
            self.provider.label,
            self.region,
            self.service,
            self.resource_type,
            self.resource_id,
            self.name,
            self.status,
            self.details,
        ]

    COLUMNS = [
        "Cloud",
        "Region",
        "Service",
        "Type",
        "ID",
        "Name",
        "Status",
        "Details",
    ]


# Backward-compatible alias used across existing AWS scanners.
AwsResource = CloudResource
