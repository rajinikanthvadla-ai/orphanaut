"""Tests for Lightsail pagination."""

from unittest.mock import Mock

from orphanaut.scanners.lightsail import LightsailScanner


class FakeLightsailClient:
    def __init__(self):
        self.calls = []

    def get_instances(self, **kwargs):
        self.calls.append(kwargs)
        if not kwargs:
            return {
                "instances": [_instance("first")],
                "nextPageToken": "next",
            }
        return {"instances": [_instance("second")]}


def _instance(name):
    return {
        "arn": f"arn:aws:lightsail:us-east-1:123:Instance/{name}",
        "name": name,
        "state": {"name": "running"},
        "bundleId": "nano_3_0",
    }


def test_lightsail_scanner_reads_all_pages():
    client = FakeLightsailClient()
    scanner = LightsailScanner(Mock(), "us-east-1")
    scanner.client = Mock(return_value=client)

    resources = scanner.scan()

    assert [resource.name for resource in resources] == ["first", "second"]
    assert client.calls == [{}, {"pageToken": "next"}]
