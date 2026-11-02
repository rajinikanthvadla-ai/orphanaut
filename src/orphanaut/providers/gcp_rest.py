"""Small authorized REST helper for Google Cloud APIs (Vertex AI, Workbench)."""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

from google.auth.transport.requests import AuthorizedSession


class GcpApiError(Exception):
    def __init__(self, status: int, message: str, reason: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.reason = reason

    @property
    def api_disabled(self) -> bool:
        text = f"{self.reason} {self}".lower()
        return self.status == 403 and (
            "service_disabled" in text or "has not been used" in text or "is disabled" in text
        )


class GcpRest:
    def __init__(self, credentials: Any, project_id: str, timeout: int = 30) -> None:
        self.project_id = project_id
        self._timeout = timeout
        self._http = AuthorizedSession(credentials)
        # User (ADC) credentials need a billing/quota project for most APIs.
        self._http.headers["x-goog-user-project"] = project_id

    def _check(self, response) -> dict:
        if response.status_code >= 400:
            reason, message = "", response.text[:500]
            try:
                error = response.json().get("error", {})
                message = error.get("message", message)
                details = error.get("details", []) or error.get("errors", [])
                reason = " ".join(str(d.get("reason", "")) for d in details)
                reason = f"{error.get('status', '')} {reason}".strip()
            except ValueError:
                pass
            raise GcpApiError(response.status_code, message, reason)
        return response.json() if response.content else {}

    def get(self, url: str, **params) -> dict:
        return self._check(self._http.get(url, params=params, timeout=self._timeout))

    def list(self, url: str, key: str, **params) -> Iterator[dict]:
        token = ""
        while True:
            if token:
                params["pageToken"] = token
            data = self.get(url, **params)
            yield from data.get(key, [])
            token = data.get("nextPageToken", "")
            if not token:
                return

    def post(self, url: str, body: dict | None = None) -> dict:
        return self._check(self._http.post(url, json=body or {}, timeout=self._timeout))

    def delete(self, url: str, **params) -> dict:
        response = self._http.delete(url, params=params, timeout=self._timeout)
        if response.status_code == 404:
            return {}
        return self._check(response)

    def wait(self, operation: dict, base: str, timeout: int = 1800) -> dict:
        """Poll a long-running operation (``{"name": ..., "done": ...}``) until done."""
        if not operation or operation.get("done") or not operation.get("name"):
            return operation
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            time.sleep(5)
            operation = self.get(f"{base}/{operation['name']}")
            if operation.get("done"):
                if "error" in operation:
                    raise GcpApiError(500, operation["error"].get("message", "Operation failed"))
                return operation
        raise GcpApiError(408, "Timed out waiting for Google Cloud to finish.")


def vertex_base(region: str) -> str:
    return f"https://{region}-aiplatform.googleapis.com/v1"
