"""Application entry point."""

from __future__ import annotations

import multiprocessing
import sys
import traceback
from pathlib import Path


def _write_startup_log(message: str) -> Path:
    log_dir = Path.home() / "Orphanaut"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "startup.log"
    log_path.write_text(message, encoding="utf-8")
    return log_path


def _show_startup_error(log_path: Path, detail: str) -> None:
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        if QApplication.instance() is None:
            QApplication(sys.argv)
        QMessageBox.critical(
            None,
            "Orphanaut failed to start",
            (
                "Orphanaut could not open.\n\n"
                f"Details saved to:\n{log_path}\n\n"
                "Windows tips:\n"
                "• This app does not install — extract the zip and run Orphanaut.exe\n"
                "• Use a folder like C:\\Orphanaut (not Downloads)\n"
                "• If blocked, open Windows Security → Protection history → Allow\n\n"
                f"{detail[:400]}"
            ),
        )
    except Exception:
        pass


def main() -> None:
    multiprocessing.freeze_support()

    try:
        from PySide6.QtWidgets import QApplication

        from orphanaut.ui.main_window import MainWindow
        from orphanaut.ui.styles import STYLESHEET

        app = QApplication(sys.argv)
        app.setApplicationName("Orphanaut")
        app.setOrganizationName("Orphanaut")
        app.setStyleSheet(STYLESHEET)

        window = MainWindow()
        window.show()

        sys.exit(app.exec())
    except Exception as exc:
        log_path = _write_startup_log(traceback.format_exc())
        _show_startup_error(log_path, str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
