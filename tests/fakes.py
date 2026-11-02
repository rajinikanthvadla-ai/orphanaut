"""Small fake cloud clients for unit tests (no network)."""

from __future__ import annotations

from collections import defaultdict


class FakePaginator:
    def __init__(self, client: FakeClient, op: str) -> None:
        self._client = client
        self._op = op

    def paginate(self, **kwargs):
        yield self._client._respond(self._op, kwargs)


class FakeClient:
    """Responds to any boto3-style call from a table of canned responses.

    ``responses[op]`` is a dict, or a callable ``(kwargs) -> dict``.
    Every call is recorded in ``calls`` as ``(op, kwargs)``.
    """

    def __init__(self, responses: dict | None = None) -> None:
        self.responses = responses or {}
        self.calls: list[tuple[str, dict]] = []
        self.exceptions = type("Exceptions", (), {})

    def _respond(self, op: str, kwargs: dict) -> dict:
        self.calls.append((op, kwargs))
        response = self.responses.get(op, {})
        return response(kwargs) if callable(response) else response

    def get_paginator(self, op: str) -> FakePaginator:
        return FakePaginator(self, op)

    def __getattr__(self, op: str):
        if op.startswith("_"):
            raise AttributeError(op)
        return lambda **kwargs: self._respond(op, kwargs)

    def ops(self) -> list[str]:
        return [op for op, _ in self.calls]


class FakeSession:
    """boto3.Session stand-in that hands out FakeClients by service name."""

    def __init__(self, clients: dict[str, FakeClient]) -> None:
        self.clients = defaultdict(FakeClient, clients)

    def client(self, name: str, **_kwargs) -> FakeClient:
        return self.clients[name]
