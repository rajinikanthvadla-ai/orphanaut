"""Azure authentication.

* Service principal (App Registration: tenant, client id, client secret).
* Browser sign-in with your Microsoft account (InteractiveBrowserCredential).
* A login that already exists on this computer: ``az login``, ``azd auth login``,
  Azure PowerShell, or ``AZURE_*`` environment variables.

After signing in, the subscriptions you can see are listed so you can pick one.
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

from azure.core.exceptions import ClientAuthenticationError

from orphanaut.auth.aws import AuthenticationError
from orphanaut.models import AuthConfig, AuthMethod
from orphanaut.providers.azure_arm import ArmClient, ArmError
from orphanaut.providers.session import AzureSession

_ARM_SCOPE = "https://management.azure.com/.default"


def _azure_profile_path() -> Path:
    base = os.environ.get("AZURE_CONFIG_DIR") or str(Path.home() / ".azure")
    return Path(base) / "azureProfile.json"


def detect_local_azure() -> str:
    """Return a short description of an existing Azure login, or '' if none is found."""
    if os.environ.get("AZURE_CLIENT_ID") and os.environ.get("AZURE_TENANT_ID"):
        return "AZURE_* environment variables"
    path = _azure_profile_path()
    if path.exists() and shutil.which("az"):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            subs = data.get("subscriptions", [])
            default = next((s for s in subs if s.get("isDefault")), subs[0] if subs else None)
            if default:
                return f"Azure CLI - {default.get('name', default.get('id', ''))}"
        except (OSError, ValueError):
            pass
    return ""


def _credential(config: AuthConfig):
    from azure.identity import (
        AzureCliCredential,
        AzureDeveloperCliCredential,
        AzurePowerShellCredential,
        ChainedTokenCredential,
        ClientSecretCredential,
        EnvironmentCredential,
        InteractiveBrowserCredential,
    )

    match config.method:
        case AuthMethod.SERVICE_PRINCIPAL:
            tenant_id = config.tenant_id.strip()
            client_id = config.client_id.strip()
            client_secret = config.client_secret.strip()
            if not all([tenant_id, client_id, client_secret]):
                raise AuthenticationError(
                    "Tenant ID, Client ID and Client Secret are all required for a "
                    "service principal."
                )
            return ClientSecretCredential(
                tenant_id=tenant_id, client_id=client_id, client_secret=client_secret
            )
        case AuthMethod.BROWSER:
            kwargs = {}
            if config.tenant_id.strip():
                kwargs["tenant_id"] = config.tenant_id.strip()
            return InteractiveBrowserCredential(**kwargs)
        case AuthMethod.LOCAL:
            return ChainedTokenCredential(
                EnvironmentCredential(),
                AzureCliCredential(process_timeout=30),
                AzureDeveloperCliCredential(process_timeout=30),
                AzurePowerShellCredential(process_timeout=30),
            )
        case _:
            raise AuthenticationError(f"Unsupported Azure sign-in method: {config.method}")


def list_subscriptions(credential) -> list[tuple[str, str]]:
    """Return (subscription_id, display_name) for enabled subscriptions."""
    try:
        subs = ArmClient(credential).list("/subscriptions", "2022-12-01")
        return [
            (s["subscriptionId"], s.get("displayName", s["subscriptionId"]))
            for s in subs
            if s.get("state", "Enabled") in {"Enabled", "Warned", "PastDue"}
        ]
    except ArmError as exc:
        raise AuthenticationError(f"Could not list Azure subscriptions: {exc}") from exc


def azure_sign_in(config: AuthConfig):
    """Sign in and return (credential, subscriptions)."""
    credential = _credential(config)
    try:
        credential.get_token(_ARM_SCOPE)
    except ClientAuthenticationError as exc:
        hint = ""
        if config.method == AuthMethod.LOCAL:
            hint = " Run 'az login' in a terminal first, or use 'Sign in with browser'."
        raise AuthenticationError(f"Azure sign-in failed.{hint}\n\n{exc.message or exc}") from exc
    except Exception as exc:
        raise AuthenticationError(f"Azure sign-in failed: {exc}") from exc
    subscriptions = list_subscriptions(credential)
    wanted = config.subscription_id.strip()
    if wanted and wanted not in {sub_id for sub_id, _ in subscriptions}:
        # Service principals sometimes can't list subscriptions but can still use one.
        subscriptions.insert(0, (wanted, wanted))
    if not subscriptions:
        raise AuthenticationError(
            "Signed in, but this account has no Azure subscriptions it can read. "
            "Ask for at least the Reader role on a subscription."
        )
    return credential, subscriptions


def create_azure_session(config: AuthConfig) -> AzureSession:
    credential, subscriptions = azure_sign_in(config)
    wanted = config.subscription_id.strip() or subscriptions[0][0]
    return AzureSession(credential=credential, subscription_id=wanted)


def validate_azure_session(session: AzureSession) -> tuple[str, str]:
    try:
        data = ArmClient(session.credential).get(
            f"/subscriptions/{session.subscription_id}", "2022-12-01"
        )
        return session.subscription_id, f"Subscription: {data.get('displayName', '')}".strip()
    except ArmError as exc:
        raise AuthenticationError(
            f"Can't read subscription {session.subscription_id}: {exc}"
        ) from exc
    except Exception as exc:
        raise AuthenticationError(f"Azure authentication failed: {exc}") from exc
