"""Azure authentication via service principal."""

from __future__ import annotations

from azure.core.exceptions import ClientAuthenticationError

from orphanaut.auth.aws import AuthenticationError
from orphanaut.models import AuthConfig, AuthMethod
from orphanaut.providers.session import AzureSession


def create_azure_session(config: AuthConfig) -> AzureSession:
    if config.method != AuthMethod.SERVICE_PRINCIPAL:
        raise AuthenticationError("Azure requires a service principal (App Registration).")

    tenant_id = config.tenant_id.strip()
    client_id = config.client_id.strip()
    client_secret = config.client_secret.strip()
    subscription_id = config.subscription_id.strip()

    if not all([tenant_id, client_id, client_secret, subscription_id]):
        raise AuthenticationError(
            "Tenant ID, Client ID, Client Secret, and Subscription ID are all required."
        )

    try:
        from azure.identity import ClientSecretCredential

        credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )
    except ClientAuthenticationError as exc:
        raise AuthenticationError(f"Azure authentication failed: {exc}") from exc

    return AzureSession(credential=credential, subscription_id=subscription_id)


def validate_azure_session(session: AzureSession) -> tuple[str, str]:
    try:
        session.credential.get_token("https://management.azure.com/.default")
        return session.subscription_id, f"Subscription {session.subscription_id}"
    except ClientAuthenticationError as exc:
        raise AuthenticationError(f"Azure authentication failed: {exc}") from exc
    except Exception as exc:
        raise AuthenticationError(f"Azure authentication failed: {exc}") from exc
