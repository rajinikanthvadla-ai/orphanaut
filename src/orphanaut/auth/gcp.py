"""GCP authentication via service account JSON key."""

from __future__ import annotations

import json

from google.auth.exceptions import GoogleAuthError
from google.oauth2 import service_account
from googleapiclient import discovery
from googleapiclient.errors import HttpError

from orphanaut.auth.aws import AuthenticationError
from orphanaut.models import AuthConfig, AuthMethod
from orphanaut.providers.session import GcpSession


def create_gcp_session(config: AuthConfig) -> GcpSession:
    if config.method != AuthMethod.SERVICE_ACCOUNT:
        raise AuthenticationError("GCP requires a service account JSON key.")

    project_id = config.project_id.strip()
    key_json = config.service_account_json.strip()
    if not project_id or not key_json:
        raise AuthenticationError("Project ID and service account JSON key are required.")

    try:
        info = json.loads(key_json)
    except json.JSONDecodeError as exc:
        raise AuthenticationError("Service account key must be valid JSON.") from exc

    if info.get("project_id") and not project_id:
        project_id = info["project_id"]

    try:
        credentials = service_account.Credentials.from_service_account_info(
            info,
            scopes=["https://www.googleapis.com/auth/cloud-platform"],
        )
    except (GoogleAuthError, ValueError) as exc:
        raise AuthenticationError(f"GCP authentication failed: {exc}") from exc

    return GcpSession(credentials=credentials, project_id=project_id)


def validate_gcp_session(session: GcpSession) -> tuple[str, str]:
    try:
        crm = discovery.build(
            "cloudresourcemanager",
            "v1",
            credentials=session.credentials,
            cache_discovery=False,
        )
        project = crm.projects().get(projectId=session.project_id).execute()
        name = project.get("name", session.project_id)
        return session.project_id, f"Project: {name}"
    except HttpError as exc:
        raise AuthenticationError(f"GCP authentication failed: {exc}") from exc
    except Exception as exc:
        raise AuthenticationError(f"GCP authentication failed: {exc}") from exc
