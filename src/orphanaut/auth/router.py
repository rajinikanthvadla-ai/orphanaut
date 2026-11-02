"""Authentication router for AWS, Azure, and GCP."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from orphanaut.auth.aws import (
    AuthenticationError,
    AwsBrowserLogin,
    DeviceCode,
    create_aws_session,
    validate_aws_session,
)
from orphanaut.auth.azure import azure_sign_in, validate_azure_session
from orphanaut.auth.gcp import gcp_sign_in, validate_gcp_session
from orphanaut.models import AuthConfig, AuthMethod, CloudProvider
from orphanaut.providers.session import AzureSession, GcpSession, ProviderSession

__all__ = [
    "AuthenticationError",
    "Choice",
    "ConnectResult",
    "connect",
    "create_session",
    "validate_session",
    "list_regions_for_provider",
]


@dataclass
class Choice:
    key: str
    label: str


@dataclass
class ConnectResult:
    """A signed-in session plus the other accounts/subscriptions/projects you can switch to."""

    session: ProviderSession
    choice_title: str = ""
    choices: list[Choice] = field(default_factory=list)
    rebind: Callable[[str], ProviderSession] | None = None


def _aws_session(session, provider_label: str = "") -> ProviderSession:
    account_id, arn = validate_aws_session(session)
    return ProviderSession(
        provider=CloudProvider.AWS,
        session=session,
        account_id=account_id,
        account_label=provider_label or arn,
    )


def _azure_session(credential, subscription_id: str) -> ProviderSession:
    session = AzureSession(credential=credential, subscription_id=subscription_id)
    sub_id, label = validate_azure_session(session)
    return ProviderSession(CloudProvider.AZURE, session, sub_id, label)


def _gcp_session(credentials, project_id: str) -> ProviderSession:
    session = GcpSession(credentials=credentials, project_id=project_id)
    pid, label = validate_gcp_session(session)
    return ProviderSession(CloudProvider.GCP, session, pid, label)


def _connect_aws_browser(
    config: AuthConfig,
    on_device_code: Callable[[DeviceCode], None] | None,
    should_cancel: Callable[[], bool],
) -> ConnectResult:
    login = AwsBrowserLogin(config.sso_start_url, config.sso_region)
    code = login.start()
    if on_device_code:
        on_device_code(code)
    login.wait(should_cancel)
    roles = login.account_roles()
    choices = [
        Choice(f"{account_id}|{role}", f"{name} ({account_id}) — {role}")
        for account_id, name, role in roles
    ]
    preferred = f"{config.sso_account_id}|{config.sso_role_name}"
    if preferred in {c.key for c in choices}:
        choices.sort(key=lambda c: c.key != preferred)

    def rebind(key: str) -> ProviderSession:
        account_id, role = key.split("|", 1)
        return _aws_session(login.session_for(account_id, role, config.region))

    return ConnectResult(rebind(choices[0].key), "Account / role", choices, rebind)


def connect(
    config: AuthConfig,
    on_device_code: Callable[[DeviceCode], None] | None = None,
    should_cancel: Callable[[], bool] = lambda: False,
) -> ConnectResult:
    """Sign in with any supported method. Blocking — run it off the UI thread."""
    match config.provider:
        case CloudProvider.AWS:
            if config.method == AuthMethod.BROWSER:
                return _connect_aws_browser(config, on_device_code, should_cancel)
            return ConnectResult(_aws_session(create_aws_session(config)))
        case CloudProvider.AZURE:
            credential, subscriptions = azure_sign_in(config)
            preferred = config.subscription_id.strip() or subscriptions[0][0]
            choices = [Choice(sub_id, f"{name} ({sub_id})") for sub_id, name in subscriptions]
            choices.sort(key=lambda c: c.key != preferred)

            def rebind_azure(sub_id: str) -> ProviderSession:
                return _azure_session(credential, sub_id)

            return ConnectResult(rebind_azure(preferred), "Subscription", choices, rebind_azure)
        case CloudProvider.GCP:
            credentials, projects = gcp_sign_in(config)
            choices = [
                Choice(pid, f"{name} ({pid})" if name != pid else pid) for pid, name in projects
            ]

            def rebind_gcp(project_id: str) -> ProviderSession:
                return _gcp_session(credentials, project_id)

            return ConnectResult(rebind_gcp(choices[0].key), "Project", choices, rebind_gcp)
        case _:
            raise AuthenticationError(f"Unsupported provider: {config.provider}")


def create_session(config: AuthConfig) -> ProviderSession:
    return connect(config).session


def validate_session(provider_session: ProviderSession) -> tuple[str, str]:
    match provider_session.provider:
        case CloudProvider.AWS:
            return validate_aws_session(provider_session.session)
        case CloudProvider.AZURE:
            return validate_azure_session(provider_session.session)
        case CloudProvider.GCP:
            return validate_gcp_session(provider_session.session)
        case _:
            raise AuthenticationError(f"Unsupported provider: {provider_session.provider}")


def list_regions_for_provider(provider: CloudProvider, session: object | None = None) -> list[str]:
    match provider:
        case CloudProvider.AWS:
            if session is None:
                from orphanaut.aws.regions import COMMON_REGIONS

                return sorted(COMMON_REGIONS)
            from orphanaut.aws.regions import get_all_regions

            return get_all_regions(session)  # type: ignore[arg-type]
        case CloudProvider.AZURE:
            from orphanaut.providers.azure_regions import AZURE_ALL_REGIONS

            return list(AZURE_ALL_REGIONS)
        case CloudProvider.GCP:
            from orphanaut.providers.gcp_regions import GCP_ALL_REGIONS

            return list(GCP_ALL_REGIONS)
        case _:
            return []
