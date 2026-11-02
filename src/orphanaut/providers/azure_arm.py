"""Tiny Azure Resource Manager REST client.

The AI services (Azure OpenAI / AI Services, Machine Learning, AI Search) are
reached through plain ARM REST calls so the app does not need three more
management SDKs. Long-running deletes are polled until they finish.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from typing import Any

import requests

ARM = "https://management.azure.com"
_SCOPE = f"{ARM}/.default"


class ArmError(Exception):
    def __init__(self, status: int, message: str, code: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class ArmClient:
    def __init__(self, credential: Any, timeout: int = 30) -> None:
        self._credential = credential
        self._timeout = timeout
        self._http = requests.Session()
        self._token = ""
        self._expires = 0.0

    def _headers(self) -> dict[str, str]:
        if not self._token or time.time() > self._expires - 120:
            token = self._credential.get_token(_SCOPE)
            self._token, self._expires = token.token, float(token.expires_on)
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def _url(self, path: str) -> str:
        return path if path.startswith("http") else f"{ARM}{path}"

    def _request(self, method: str, path: str, api_version: str | None, **kwargs):
        params = dict(kwargs.pop("params", None) or {})
        if api_version and "api-version=" not in path:
            params["api-version"] = api_version
        response = self._http.request(
            method,
            self._url(path),
            params=params,
            headers=self._headers(),
            timeout=self._timeout,
            **kwargs,
        )
        if response.status_code >= 400:
            code, message = "", response.text[:500]
            try:
                error = response.json().get("error", {})
                code, message = error.get("code", ""), error.get("message", message)
            except ValueError:
                pass
            raise ArmError(response.status_code, message or response.reason, code)
        return response

    def get(self, path: str, api_version: str | None = None, **params) -> dict:
        response = self._request("GET", path, api_version, params=params)
        return response.json() if response.content else {}

    def list(self, path: str, api_version: str | None = None, **params) -> Iterator[dict]:
        url: str | None = path
        first = True
        while url:
            data = self.get(url, api_version if first else None, **(params if first else {}))
            first = False
            yield from data.get("value", [])
            url = data.get("nextLink")

    def post(self, path: str, api_version: str, body: dict | None = None) -> requests.Response:
        return self._request("POST", path, api_version, json=body or {})

    def delete(
        self,
        path: str,
        api_version: str,
        *,
        wait: bool = True,
        timeout: int = 1800,
        **params,
    ) -> None:
        try:
            response = self._request("DELETE", path, api_version, params=params)
        except ArmError as exc:
            if exc.status == 404:
                return  # Already gone.
            raise
        if wait and response.status_code == 202:
            self._wait(response, timeout)

    def _wait(self, response: requests.Response, timeout: int) -> None:
        poll_url = response.headers.get("Azure-AsyncOperation") or response.headers.get("Location")
        if not poll_url:
            return
        deadline = time.monotonic() + timeout
        delay = int(response.headers.get("Retry-After", "5") or 5)
        while time.monotonic() < deadline:
            time.sleep(min(max(delay, 2), 15))
            poll = self._http.get(poll_url, headers=self._headers(), timeout=self._timeout)
            if poll.status_code == 202:
                continue
            if poll.status_code == 404:
                return
            if poll.status_code >= 400:
                raise ArmError(poll.status_code, poll.text[:500])
            if not poll.content:
                return
            try:
                status = poll.json().get("status", "Succeeded")
            except ValueError:
                return
            if status.lower() in {"succeeded", "deleted"}:
                return
            if status.lower() in {"failed", "canceled", "cancelled"}:
                error = poll.json().get("error", {})
                raise ArmError(500, error.get("message", f"Delete {status.lower()}"))
        raise ArmError(408, "Timed out waiting for Azure to finish deleting.")


def parse_id(resource_id: str) -> dict[str, str]:
    """Split an ARM id into subscription, resource_group and name parts."""
    parts = resource_id.strip("/").split("/")
    lowered = [p.lower() for p in parts]
    out = {"name": parts[-1] if parts else ""}
    if "subscriptions" in lowered:
        out["subscription"] = parts[lowered.index("subscriptions") + 1]
    if "resourcegroups" in lowered:
        out["resource_group"] = parts[lowered.index("resourcegroups") + 1]
    return out
