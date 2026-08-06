"""Authentication router for AWS, Azure, and GCP."""

from __future__ import annotations

from orphanaut.auth.aws import AuthenticationError, create_aws_session, validate_aws_session
from orphanaut.auth.azure import create_azure_session, validate_azure_session
from orphanaut.auth.gcp import create_gcp_session, validate_gcp_session
from orphanaut.models import AuthConfig, CloudProvider
from orphanaut.providers.session import ProviderSession

__all__ = ["AuthenticationError", "create_session", "validate_session", "list_regions_for_provider"]


def create_session(config: AuthConfig) -> ProviderSession:
    match config.provider:
        case CloudProvider.AWS:
            session = create_aws_session(config)
            account_id, arn = validate_aws_session(session)
            return ProviderSession(
                provider=CloudProvider.AWS,
                session=session,
                account_id=account_id,
                account_label=arn,
            )
        case CloudProvider.AZURE:
            session = create_azure_session(config)
            subscription_id, label = validate_azure_session(session)
            return ProviderSession(
                provider=CloudProvider.AZURE,
                session=session,
                account_id=subscription_id,
                account_label=label,
            )
        case CloudProvider.GCP:
            session = create_gcp_session(config)
            project_id, label = validate_gcp_session(session)
            return ProviderSession(
                provider=CloudProvider.GCP,
                session=session,
                account_id=project_id,
                account_label=label,
            )
        case _:
            raise AuthenticationError(f"Unsupported provider: {config.provider}")


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
