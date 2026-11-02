"""Google Cloud authentication.

* Service account JSON key (pasted or picked from a file).
* Browser sign-in with your Google account — runs
  ``gcloud auth application-default login`` which opens the browser.
* A login that already exists on this computer (Application Default
  Credentials from gcloud, or ``GOOGLE_APPLICATION_CREDENTIALS``).

After signing in, the projects you can see are listed so you can pick one.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from google.auth.exceptions import DefaultCredentialsError, GoogleAuthError, RefreshError
from google.oauth2 import service_account
from googleapiclient import discovery
from googleapiclient.errors import HttpError

from orphanaut.auth.aws import AuthenticationError
from orphanaut.models import AuthConfig, AuthMethod
from orphanaut.providers.session import GcpSession

SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]
GCLOUD_INSTALL_URL = "https://cloud.google.com/sdk/docs/install"


def _gcloud_config_dir() -> Path:
    if os.environ.get("CLOUDSDK_CONFIG"):
        return Path(os.environ["CLOUDSDK_CONFIG"])
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home())) / "gcloud"
    return Path.home() / ".config" / "gcloud"


def adc_path() -> Path:
    env = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if env:
        return Path(env)
    return _gcloud_config_dir() / "application_default_credentials.json"


def gcloud_path() -> str | None:
    return shutil.which("gcloud")


def gcloud_default_project() -> str:
    path = _gcloud_config_dir() / "configurations" / "config_default"
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            key, _, value = line.partition("=")
            if key.strip() == "project":
                return value.strip()
    except OSError:
        pass
    return ""


def detect_local_gcp() -> str:
    """Return a short description of existing Google credentials, or ''."""
    if adc_path().exists():
        project = gcloud_default_project()
        return "Application Default Credentials" + (f" — {project}" if project else "")
    return ""


def _no_window() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0


def run_gcloud_browser_login() -> None:
    """Open the Google sign-in page via gcloud and wait for it to finish."""
    gcloud = gcloud_path()
    if not gcloud:
        raise AuthenticationError(
            "Browser sign-in for Google Cloud uses the gcloud CLI, which isn't installed.\n\n"
            f"Install it from {GCLOUD_INSTALL_URL} and try again — or use a service "
            "account JSON key instead."
        )
    try:
        result = subprocess.run(
            [gcloud, "auth", "application-default", "login", f"--scopes={SCOPES[0]}"],
            capture_output=True,
            text=True,
            timeout=600,
            creationflags=_no_window(),
        )
    except subprocess.TimeoutExpired as exc:
        raise AuthenticationError("Google sign-in timed out. Try again.") from exc
    except OSError as exc:
        raise AuthenticationError(f"Could not run gcloud: {exc}") from exc
    if result.returncode != 0:
        raise AuthenticationError(f"Google sign-in failed:\n{(result.stderr or '')[-600:]}")


def _service_account_credentials(config: AuthConfig):
    key_json = config.service_account_json.strip()
    if not key_json:
        raise AuthenticationError("Paste the service account JSON key, or pick the key file.")
    try:
        info = json.loads(key_json)
    except json.JSONDecodeError as exc:
        raise AuthenticationError("The service account key must be valid JSON.") from exc
    if info.get("type") != "service_account":
        raise AuthenticationError(
            'That JSON isn\'t a service account key (its "type" should be "service_account").'
        )
    try:
        credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    except (GoogleAuthError, ValueError) as exc:
        raise AuthenticationError(f"GCP authentication failed: {exc}") from exc
    return credentials, info.get("project_id", "")


def _adc_credentials():
    try:
        import google.auth

        credentials, project = google.auth.default(scopes=SCOPES)
    except DefaultCredentialsError as exc:
        raise AuthenticationError(
            "No Google login found on this computer. Use 'Sign in with browser' or run "
            "'gcloud auth application-default login'."
        ) from exc
    return credentials, project or gcloud_default_project()


def list_projects(credentials) -> list[tuple[str, str]]:
    """Return (project_id, name) for active projects the credentials can see."""
    try:
        crm = discovery.build(
            "cloudresourcemanager", "v1", credentials=credentials, cache_discovery=False
        )
        projects: list[tuple[str, str]] = []
        request = crm.projects().list(filter="lifecycleState:ACTIVE")
        while request is not None:
            response = request.execute()
            for project in response.get("projects", []):
                projects.append((project["projectId"], project.get("name", project["projectId"])))
            request = crm.projects().list_next(request, response)
        return sorted(projects)
    except (HttpError, GoogleAuthError, RefreshError):
        # Service accounts often can't list projects; the key's own project still works.
        return []


def gcp_sign_in(config: AuthConfig):
    """Sign in and return (credentials, projects)."""
    match config.method:
        case AuthMethod.SERVICE_ACCOUNT:
            credentials, key_project = _service_account_credentials(config)
        case AuthMethod.BROWSER:
            run_gcloud_browser_login()
            credentials, key_project = _adc_credentials()
        case AuthMethod.LOCAL:
            credentials, key_project = _adc_credentials()
        case _:
            raise AuthenticationError(f"Unsupported Google Cloud sign-in method: {config.method}")

    projects = list_projects(credentials)
    preferred = config.project_id.strip() or key_project
    if preferred and preferred not in {pid for pid, _ in projects}:
        projects.insert(0, (preferred, preferred))
    elif preferred:
        projects.sort(key=lambda p: p[0] != preferred)
    if not projects:
        raise AuthenticationError(
            "Signed in, but no Google Cloud project was found. Enter the Project ID."
        )
    return credentials, projects


def create_gcp_session(config: AuthConfig) -> GcpSession:
    credentials, projects = gcp_sign_in(config)
    return GcpSession(credentials=credentials, project_id=projects[0][0])


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
        if exc.resp.status in (403, 404):
            raise AuthenticationError(
                f"Can't open project '{session.project_id}'. Check the Project ID and that "
                "this account has at least the Viewer role on it."
            ) from exc
        raise AuthenticationError(f"GCP authentication failed: {exc}") from exc
    except RefreshError as exc:
        raise AuthenticationError(
            "Your Google login has expired. Use 'Sign in with browser' to log in again."
        ) from exc
    except Exception as exc:
        raise AuthenticationError(f"GCP authentication failed: {exc}") from exc
