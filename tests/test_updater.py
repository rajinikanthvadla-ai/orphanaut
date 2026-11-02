"""Tests for the in-app update checker (network calls are faked)."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from orphanaut import updater  # noqa: E402

ASSETS = [
    updater.Asset("Orphanaut-Setup-Windows.exe", "https://x/setup.exe", 10),
    updater.Asset("Orphanaut-Windows-Portable.zip", "https://x/p.zip", 10),
    updater.Asset("Orphanaut-macOS-AppleSilicon.dmg", "https://x/arm.dmg", 10),
    updater.Asset("Orphanaut-macOS-Intel.dmg", "https://x/intel.dmg", 10),
]
RELEASE = updater.ReleaseInfo("9.0.0", "notes", "https://x/release", ASSETS)


@pytest.mark.parametrize(
    ("latest", "current", "newer"),
    [
        ("2.1.2", "2.1.1", True),
        ("v2.2.0", "2.1.9", True),
        ("2.10.0", "2.9.0", True),
        ("2.1.1", "2.1.1", False),
        ("2.1.0", "2.1.1", False),
        ("garbage", "2.1.1", False),
    ],
)
def test_is_newer(latest, current, newer):
    assert updater.is_newer(latest, current) is newer


class FakeResponse:
    def __init__(self, data=None, chunks=(), headers=None):
        self._data = data
        self._chunks = chunks
        self.headers = headers or {}

    def raise_for_status(self):
        pass

    def json(self):
        return self._data

    def iter_content(self, chunk_size=0):
        yield from self._chunks

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def test_check_for_update_parses_release(monkeypatch):
    data = {"tag_name": "v99.0.0", "body": "big release", "html_url": "https://r",
            "assets": [{"name": "a.dmg", "browser_download_url": "https://d", "size": 5}]}
    monkeypatch.setattr(updater.requests, "get", lambda *a, **k: FakeResponse(data))
    release = updater.check_for_update()
    assert release.version == "99.0.0"
    assert release.assets[0].url == "https://d"


def test_no_update_when_current(monkeypatch):
    data = {"tag_name": f"v{updater.__version__}", "assets": []}
    monkeypatch.setattr(updater.requests, "get", lambda *a, **k: FakeResponse(data))
    assert updater.check_for_update() is None


def test_network_error_becomes_update_error(monkeypatch):
    def boom(*_a, **_k):
        raise updater.requests.ConnectionError("offline")

    monkeypatch.setattr(updater.requests, "get", boom)
    with pytest.raises(updater.UpdateError, match="offline"):
        updater.check_for_update()


def test_pick_asset_windows_installer(monkeypatch):
    monkeypatch.setattr(updater.sys, "platform", "win32")
    monkeypatch.setattr(updater, "installed_with_setup", lambda: True)
    assert updater.pick_asset(RELEASE).name == "Orphanaut-Setup-Windows.exe"
    assert updater.update_action_label(RELEASE) == "Update now"


def test_pick_asset_windows_portable_opens_page(monkeypatch):
    monkeypatch.setattr(updater.sys, "platform", "win32")
    monkeypatch.setattr(updater, "installed_with_setup", lambda: False)
    monkeypatch.setattr(updater, "is_frozen", lambda: True)
    assert updater.pick_asset(RELEASE) is None
    assert updater.update_action_label(RELEASE) == "Download"


@pytest.mark.parametrize(("machine", "name"), [("arm64", "AppleSilicon"), ("x86_64", "Intel")])
def test_pick_asset_mac_by_chip(monkeypatch, machine, name):
    monkeypatch.setattr(updater.sys, "platform", "darwin")
    monkeypatch.setattr(updater, "is_frozen", lambda: True)
    monkeypatch.setattr(updater.platform, "machine", lambda: machine)
    assert updater.pick_asset(RELEASE).name == f"Orphanaut-macOS-{name}.dmg"


def test_source_install_just_views_release(monkeypatch):
    monkeypatch.setattr(updater.sys, "platform", "linux")
    monkeypatch.setattr(updater, "is_frozen", lambda: False)
    assert updater.pick_asset(RELEASE) is None
    assert updater.update_action_label(RELEASE) == "View release"


def test_download_writes_file_and_reports_progress(monkeypatch, tmp_path):
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(updater.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(updater.requests, "get", lambda *a, **k: FakeResponse(
        chunks=[b"hello", b"world"], headers={"Content-Length": "10"}))
    seen = []
    path = updater.download(updater.Asset("x.bin", "https://x", 10),
                            lambda d, t: seen.append((d, t)))
    assert path.read_bytes() == b"helloworld"
    assert seen[-1] == (10, 10)


def test_incomplete_download_is_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(updater.tempfile, "gettempdir", lambda: str(tmp_path))
    monkeypatch.setattr(updater.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(updater.requests, "get",
                        lambda *a, **k: FakeResponse(chunks=[b"half"]))
    with pytest.raises(updater.UpdateError, match="incomplete"):
        updater.download(updater.Asset("x.bin", "https://x", 10))
    assert not any(tmp_path.rglob("x.bin*"))


def test_banner_shows_for_newer_release(monkeypatch):
    from PySide6.QtWidgets import QApplication

    from orphanaut.ui.update_banner import UpdateBanner

    app = QApplication.instance() or QApplication([])
    app.setOrganizationName("OrphanautTests")  # keep test settings out of the real app's
    monkeypatch.setattr(updater.sys, "platform", "win32")
    monkeypatch.setattr(updater, "installed_with_setup", lambda: True)
    banner = UpdateBanner()
    banner._on_found(RELEASE)
    assert not banner.isHidden()
    assert "9.0.0" in banner._text.text()
    assert banner._action_btn.text() == "Update now"
    banner._on_later()
    assert banner.isHidden()


def test_checks_can_be_disabled(monkeypatch):
    monkeypatch.setenv("ORPHANAUT_NO_UPDATE_CHECK", "1")
    assert updater.checks_disabled()
    monkeypatch.setenv("ORPHANAUT_NO_UPDATE_CHECK", "0")
    assert not updater.checks_disabled()
