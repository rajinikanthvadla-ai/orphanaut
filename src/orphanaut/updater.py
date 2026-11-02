"""Check GitHub Releases for a newer Orphanaut and fetch the right installer.

Only one anonymous request is made (the public "latest release" endpoint); no
data about the user or their clouds is sent. Set ORPHANAUT_NO_UPDATE_CHECK=1 to
turn the automatic check off.
"""

from __future__ import annotations

import os
import platform
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import requests

from orphanaut import __version__

REPO = "rajinikanthvadla-ai/orphanaut"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases/latest"
_VERSION_RE = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


class UpdateError(Exception):
    pass


@dataclass
class Asset:
    name: str
    url: str
    size: int


@dataclass
class ReleaseInfo:
    version: str
    notes: str
    page_url: str
    assets: list[Asset]


def parse_version(text: str) -> tuple[int, int, int]:
    match = _VERSION_RE.search(text or "")
    if not match:
        return (0, 0, 0)
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch or 0)


def is_newer(latest: str, current: str = __version__) -> bool:
    return parse_version(latest) > parse_version(current)


def checks_disabled() -> bool:
    return os.environ.get("ORPHANAUT_NO_UPDATE_CHECK", "").strip() not in ("", "0", "false")


def fetch_latest(timeout: float = 6.0) -> ReleaseInfo:
    try:
        response = requests.get(
            LATEST_URL,
            timeout=timeout,
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": f"Orphanaut/{__version__}"},
        )
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise UpdateError(f"Could not check for updates: {exc}") from exc
    return ReleaseInfo(
        version=str(data.get("tag_name", "")).lstrip("v"),
        notes=data.get("body") or "",
        page_url=data.get("html_url") or RELEASES_PAGE,
        assets=[
            Asset(a["name"], a["browser_download_url"], int(a.get("size", 0)))
            for a in data.get("assets", [])
        ],
    )


def check_for_update() -> ReleaseInfo | None:
    """Return the latest release if it is newer than this app, else None."""
    release = fetch_latest()
    return release if is_newer(release.version, __version__) else None


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def installed_with_setup() -> bool:
    """True when this Windows copy came from the installer (it can update in place)."""
    if sys.platform != "win32" or not is_frozen():
        return False
    return any(Path(sys.executable).parent.glob("unins*.exe"))


def mac_arch() -> str:
    machine = platform.machine().lower()
    return "AppleSilicon" if machine in ("arm64", "aarch64") else "Intel"


def pick_asset(release: ReleaseInfo) -> Asset | None:
    """The download that fits this computer, or None to just open the release page."""
    names = {a.name: a for a in release.assets}
    if sys.platform == "win32" and installed_with_setup():
        return names.get("Orphanaut-Setup-Windows.exe")
    if sys.platform == "darwin" and is_frozen():
        return names.get(f"Orphanaut-macOS-{mac_arch()}.dmg")
    return None


def update_action_label(release: ReleaseInfo) -> str:
    if pick_asset(release):
        return "Update now"
    if not is_frozen():
        return "View release"  # Running from source: pip / git pull.
    return "Download"


def download(asset: Asset, progress: Callable[[int, int], None] = lambda _d, _t: None,
             should_cancel: Callable[[], bool] = lambda: False) -> Path:
    target_dir = Path(tempfile.gettempdir()) if sys.platform == "win32" else (
        Path.home() / "Downloads")
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / asset.name
    partial = target.with_suffix(target.suffix + ".part")
    try:
        with requests.get(asset.url, stream=True, timeout=30,
                          headers={"User-Agent": f"Orphanaut/{__version__}"}) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length", asset.size) or 0)
            done = 0
            with open(partial, "wb") as handle:
                for chunk in response.iter_content(chunk_size=256 * 1024):
                    if should_cancel():
                        raise UpdateError("Download cancelled.")
                    handle.write(chunk)
                    done += len(chunk)
                    progress(done, total)
        if asset.size and partial.stat().st_size != asset.size:
            raise UpdateError("The download was incomplete. Please try again.")
        partial.replace(target)
    except requests.RequestException as exc:
        raise UpdateError(f"Download failed: {exc}") from exc
    finally:
        if partial.exists():
            partial.unlink(missing_ok=True)
    return target


def launch_update(path: Path) -> None:
    """Start the installer / open the disk image. The caller should then quit the app."""
    if sys.platform == "win32":
        # Inno Setup closes nothing itself here — we quit right after — and relaunches
        # Orphanaut when it finishes (see installer/orphanaut.iss).
        subprocess.Popen([str(path), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART"],
                         close_fds=True)
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
