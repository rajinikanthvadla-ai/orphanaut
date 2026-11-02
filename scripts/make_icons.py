"""Regenerate assets/icon.{png,ico,icns} from the in-code logo.

    python scripts/make_icons.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QImageWriter
from PySide6.QtWidgets import QApplication

from orphanaut.ui.icons import app_pixmap

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841 - needed for QPixmap
    out = ROOT / "assets"
    out.mkdir(exist_ok=True)
    app_pixmap(512).save(str(out / "icon.png"))
    app_pixmap(256).save(str(out / "icon.ico"), "ICO")
    supported = {bytes(f).decode() for f in QImageWriter.supportedImageFormats()}
    if "icns" in supported:
        app_pixmap(1024).save(str(out / "icon.icns"), "ICNS")
    print("wrote", sorted(p.name for p in out.iterdir()))


if __name__ == "__main__":
    main()
