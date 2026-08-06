"""AWS authentication helpers."""

from __future__ import annotations

import configparser
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, ProfileNotFound

from orphanaut.models import AuthConfig, AuthMethod


class AuthenticationError(Exception):
    """Raised when cloud authentication fails."""


def list_sso_profiles() -> list[str]:
    """Return profile names from the local AWS config that look SSO-enabled."""
    config_path = Path.home() / ".aws" / "config"
    if not config_path.exists():
        return []

    parser = configparser.ConfigParser()
    parser.read(config_path)
    profiles: list[str] = []
    for section in parser.sections():
        name = section.removeprefix("profile ").strip()
        if parser.has_option(section, "sso_start_url") or parser.has_option(section, "sso_session"):
            profiles.append(name)
        elif section == "default" and (
            parser.has_option(section, "sso_start_url") or parser.has_option(section, "sso_session")
        ):
            profiles.append("default")
    return sorted(set(profiles))


def create_aws_session(config: AuthConfig) -> boto3.Session:
    """Build a boto3 session from the provided auth configuration."""
    if config.method == AuthMethod.ACCESS_KEYS:
        if not config.access_key_id or not config.secret_access_key:
            raise AuthenticationError("Access Key ID and Secret Access Key are required.")
        kwargs: dict[str, str] = {
            "aws_access_key_id": config.access_key_id.strip(),
            "aws_secret_access_key": config.secret_access_key.strip(),
            "region_name": config.region,
        }
        if config.session_token.strip():
            kwargs["aws_session_token"] = config.session_token.strip()
        return boto3.Session(**kwargs)

    if config.method == AuthMethod.SSO_PROFILE:
        if not config.profile_name.strip():
            raise AuthenticationError("An AWS SSO profile name is required.")
        try:
            return boto3.Session(
                profile_name=config.profile_name.strip(),
                region_name=config.region,
            )
        except ProfileNotFound as exc:
            raise AuthenticationError(
                f"Profile '{config.profile_name}' not found in ~/.aws/config."
            ) from exc

    raise AuthenticationError(f"Unsupported AWS auth method: {config.method}")


def validate_aws_session(session: boto3.Session) -> tuple[str, str]:
    """Verify credentials via STS GetCallerIdentity."""
    try:
        sts = session.client("sts")
        identity = sts.get_caller_identity()
        return identity["Account"], identity["Arn"]
    except NoCredentialsError as exc:
        raise AuthenticationError(
            "No AWS credentials found. Check your keys or run 'aws sso login' for SSO profiles."
        ) from exc
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        if code in {"ExpiredToken", "InvalidClientTokenId", "SignatureDoesNotMatch"}:
            raise AuthenticationError(
                "Credentials are invalid or expired. For SSO, run 'aws sso login' first."
            ) from exc
        raise AuthenticationError(f"AWS authentication failed: {exc}") from exc


# Backward-compatible aliases.
create_session = create_aws_session
validate_credentials = validate_aws_session
