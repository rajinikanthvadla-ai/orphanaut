"""AWS authentication helpers.

Three ways in:
* Access keys pasted into the app (optionally with a session token).
* Browser sign-in through AWS IAM Identity Center (SSO) using the OAuth device
  flow — no AWS CLI needed; the app opens the browser and waits.
* A login that already exists on this computer: a named profile in
  ``~/.aws/credentials`` / ``~/.aws/config`` or ``AWS_*`` environment variables.
"""

from __future__ import annotations

import configparser
import os
import time
import webbrowser
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import (
    BotoCoreError,
    ClientError,
    NoCredentialsError,
    ProfileNotFound,
    SSOTokenLoadError,
    TokenRetrievalError,
    UnauthorizedSSOTokenError,
)

from orphanaut.models import AuthConfig, AuthMethod

ENV_PROFILE = "(environment variables)"
_SSO_CONFIG = Config(connect_timeout=10, read_timeout=30, retries={"total_max_attempts": 3})


class AuthenticationError(Exception):
    """Raised when cloud authentication fails."""


def _aws_dir() -> Path:
    return Path.home() / ".aws"


def _read_ini(path: Path) -> configparser.ConfigParser:
    parser = configparser.ConfigParser(interpolation=None)
    if path.exists():
        try:
            parser.read(path, encoding="utf-8")
        except configparser.Error:
            pass
    return parser


def _config_path() -> Path:
    return Path(os.environ.get("AWS_CONFIG_FILE") or _aws_dir() / "config")


def _credentials_path() -> Path:
    return Path(os.environ.get("AWS_SHARED_CREDENTIALS_FILE") or _aws_dir() / "credentials")


def list_sso_profiles() -> list[str]:
    """Return profile names from the local AWS config that look SSO-enabled."""
    parser = _read_ini(_config_path())
    profiles: list[str] = []
    for section in parser.sections():
        if not (section == "default" or section.startswith("profile ")):
            continue
        name = section.removeprefix("profile ").strip()
        if parser.has_option(section, "sso_start_url") or parser.has_option(section, "sso_session"):
            profiles.append(name)
    return sorted(set(profiles))


def list_local_profiles() -> list[str]:
    """All usable profiles on this computer, plus env vars when they are set."""
    names: set[str] = set()
    for section in _read_ini(_credentials_path()).sections():
        names.add(section.strip())
    for section in _read_ini(_config_path()).sections():
        if section == "default" or section.startswith("profile "):
            names.add(section.removeprefix("profile ").strip())
    profiles = sorted(names, key=lambda n: (n != "default", n))
    if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"):
        profiles.insert(0, ENV_PROFILE)
    return profiles


@dataclass
class SsoSettings:
    start_url: str
    region: str
    account_id: str = ""
    role_name: str = ""


def sso_settings_for_profile(profile: str) -> SsoSettings | None:
    """Read the IAM Identity Center settings of a local profile (legacy or sso-session)."""
    parser = _read_ini(_config_path())
    section = "default" if profile == "default" else f"profile {profile}"
    if not parser.has_section(section):
        return None
    get = lambda sec, key: parser.get(sec, key, fallback="").strip()  # noqa: E731
    start_url = get(section, "sso_start_url")
    region = get(section, "sso_region")
    session_name = get(section, "sso_session")
    if session_name and parser.has_section(f"sso-session {session_name}"):
        sso_section = f"sso-session {session_name}"
        start_url = start_url or get(sso_section, "sso_start_url")
        region = region or get(sso_section, "sso_region")
    if not start_url:
        return None
    return SsoSettings(
        start_url=start_url,
        region=region or "us-east-1",
        account_id=get(section, "sso_account_id"),
        role_name=get(section, "sso_role_name"),
    )


def create_aws_session(config: AuthConfig) -> boto3.Session:
    """Build a boto3 session for key-based or local-profile auth."""
    if config.method == AuthMethod.ACCESS_KEYS:
        access_key = config.access_key_id.strip()
        secret_key = config.secret_access_key.strip()
        if not access_key or not secret_key:
            raise AuthenticationError("Access Key ID and Secret Access Key are required.")
        if not (access_key.startswith("AKIA") or access_key.startswith("ASIA")):
            raise AuthenticationError(
                "That doesn't look like an Access Key ID — it usually starts with "
                "AKIA (long-term) or ASIA (temporary)."
            )
        if access_key.startswith("ASIA") and not config.session_token.strip():
            raise AuthenticationError(
                "Keys that start with ASIA are temporary and also need the Session Token."
            )
        kwargs: dict[str, str] = {
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "region_name": config.region,
        }
        if config.session_token.strip():
            kwargs["aws_session_token"] = config.session_token.strip()
        return boto3.Session(**kwargs)

    if config.method in (AuthMethod.SSO_PROFILE, AuthMethod.LOCAL):
        profile = config.profile_name.strip()
        if not profile:
            raise AuthenticationError("Pick an AWS profile from this computer.")
        if profile == ENV_PROFILE:
            return boto3.Session(region_name=config.region)
        try:
            return boto3.Session(profile_name=profile, region_name=config.region)
        except ProfileNotFound as exc:
            raise AuthenticationError(f"Profile '{profile}' was not found in ~/.aws.") from exc

    raise AuthenticationError(f"Unsupported AWS auth method: {config.method}")


def validate_aws_session(session: boto3.Session) -> tuple[str, str]:
    """Verify credentials via STS GetCallerIdentity."""
    try:
        sts = session.client("sts", region_name=session.region_name or "us-east-1")
        identity = sts.get_caller_identity()
        return identity["Account"], identity["Arn"]
    except NoCredentialsError as exc:
        raise AuthenticationError(
            "No AWS credentials found for that profile. Paste access keys or use "
            "'Sign in with browser'."
        ) from exc
    except (SSOTokenLoadError, UnauthorizedSSOTokenError, TokenRetrievalError) as exc:
        raise AuthenticationError(
            "Your AWS SSO login on this computer has expired. Use 'Sign in with browser' "
            "and pick this profile to log in again."
        ) from exc
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "Unknown")
        if code in {"ExpiredToken", "InvalidClientTokenId", "SignatureDoesNotMatch"}:
            raise AuthenticationError(
                "AWS rejected these credentials — they are wrong, deactivated or expired. "
                "Double-check the Access Key ID and Secret Access Key."
            ) from exc
        raise AuthenticationError(f"AWS authentication failed: {exc}") from exc
    except BotoCoreError as exc:
        raise AuthenticationError(f"Could not reach AWS: {exc}") from exc


@dataclass
class DeviceCode:
    user_code: str
    verification_url: str
    expires_in: int


class AwsBrowserLogin:
    """IAM Identity Center sign-in with the OAuth device authorization flow."""

    def __init__(self, start_url: str, sso_region: str) -> None:
        start_url = start_url.strip()
        if not start_url:
            raise AuthenticationError(
                "Enter your AWS access portal URL (e.g. https://my-org.awsapps.com/start)."
            )
        if not start_url.startswith("http"):
            start_url = f"https://{start_url}"
        self.start_url = start_url
        self.region = (sso_region or "us-east-1").strip()
        self._oidc = boto3.client("sso-oidc", region_name=self.region, config=_SSO_CONFIG)
        self._sso = boto3.client("sso", region_name=self.region, config=_SSO_CONFIG)
        self._client: dict | None = None
        self._device: dict | None = None
        self.access_token = ""

    def start(self, open_browser: bool = True) -> DeviceCode:
        try:
            self._client = self._oidc.register_client(clientName="orphanaut", clientType="public")
            self._device = self._oidc.start_device_authorization(
                clientId=self._client["clientId"],
                clientSecret=self._client["clientSecret"],
                startUrl=self.start_url,
            )
        except (ClientError, BotoCoreError) as exc:
            raise AuthenticationError(
                f"Could not start AWS browser sign-in. Check the portal URL and SSO region. ({exc})"
            ) from exc
        url = self._device.get("verificationUriComplete") or self._device["verificationUri"]
        if open_browser:
            webbrowser.open(url)
        return DeviceCode(
            user_code=self._device["userCode"],
            verification_url=url,
            expires_in=int(self._device.get("expiresIn", 600)),
        )

    def wait(self, should_cancel: Callable[[], bool] = lambda: False) -> str:
        assert self._client and self._device, "call start() first"
        interval = int(self._device.get("interval", 5))
        deadline = time.monotonic() + int(self._device.get("expiresIn", 600))
        while time.monotonic() < deadline:
            if should_cancel():
                raise AuthenticationError("Browser sign-in was cancelled.")
            try:
                token = self._oidc.create_token(
                    clientId=self._client["clientId"],
                    clientSecret=self._client["clientSecret"],
                    grantType="urn:ietf:params:oauth:grant-type:device_code",
                    deviceCode=self._device["deviceCode"],
                )
                self.access_token = token["accessToken"]
                return self.access_token
            except self._oidc.exceptions.AuthorizationPendingException:
                pass
            except self._oidc.exceptions.SlowDownException:
                interval += 5
            except (ClientError, BotoCoreError) as exc:
                raise AuthenticationError(f"AWS browser sign-in failed: {exc}") from exc
            time.sleep(interval)
        raise AuthenticationError("Browser sign-in timed out. Click Sign in again.")

    def account_roles(self) -> list[tuple[str, str, str]]:
        """Return (account_id, account_name, role_name) for every role you can use."""
        roles: list[tuple[str, str, str]] = []
        try:
            for page in self._sso.get_paginator("list_accounts").paginate(
                accessToken=self.access_token
            ):
                for account in page.get("accountList", []):
                    account_id = account["accountId"]
                    name = account.get("accountName", account_id)
                    for role_page in self._sso.get_paginator("list_account_roles").paginate(
                        accessToken=self.access_token, accountId=account_id
                    ):
                        for role in role_page.get("roleList", []):
                            roles.append((account_id, name, role["roleName"]))
        except (ClientError, BotoCoreError) as exc:
            raise AuthenticationError(f"Could not list your AWS accounts: {exc}") from exc
        if not roles:
            raise AuthenticationError("Your AWS user has no accounts or roles assigned.")
        return roles

    def session_for(self, account_id: str, role_name: str, region: str) -> boto3.Session:
        try:
            creds = self._sso.get_role_credentials(
                roleName=role_name, accountId=account_id, accessToken=self.access_token
            )["roleCredentials"]
        except (ClientError, BotoCoreError) as exc:
            raise AuthenticationError(f"Could not get credentials for {role_name}: {exc}") from exc
        return boto3.Session(
            aws_access_key_id=creds["accessKeyId"],
            aws_secret_access_key=creds["secretAccessKey"],
            aws_session_token=creds["sessionToken"],
            region_name=region,
        )


# Backward-compatible aliases.
create_session = create_aws_session
validate_credentials = validate_aws_session
