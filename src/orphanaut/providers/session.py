"""Provider session wrappers returned after authentication."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from orphanaut.models import CloudProvider


@dataclass
class AzureSession:
    credential: Any
    subscription_id: str


@dataclass
class GcpSession:
    credentials: Any
    project_id: str


@dataclass
class ProviderSession:
    """Authenticated cloud session with display metadata."""

    provider: CloudProvider
    session: Any
    account_id: str
    account_label: str
