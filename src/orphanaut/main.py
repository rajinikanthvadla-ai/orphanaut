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
                "• Use the installer, or extract the whole zip and run Orphanaut.exe\n"
                "• Use a folder like C:\\Orphanaut (not inside the zip)\n"
                "• If blocked, open Windows Security > Protection history > Allow\n\n"
                f"{detail[:400]}"
            ),
        )
    except Exception:
        pass


def self_test() -> int:
    """Smoke test used by CI on the packaged app: every module loads, the UI builds."""
    import importlib
    import pkgutil

    import orphanaut

    for module in pkgutil.walk_packages(orphanaut.__path__, "orphanaut."):
        importlib.import_module(module.name)

    # Bundled Google API discovery documents must be present in frozen builds.
    from google.auth.credentials import AnonymousCredentials
    from googleapiclient import discovery

    discovery.build("compute", "v1", credentials=AnonymousCredentials(), static_discovery=True)

    from PySide6.QtWidgets import QApplication

    from orphanaut.ui.main_window import MainWindow
    from orphanaut.ui.styles import apply_theme

    app = QApplication.instance() or QApplication(sys.argv)
    apply_theme(app)
    window = MainWindow(check_updates=False)
    window.show()
    app.processEvents()
    window.close()
    if sys.stdout:  # Windowed (no-console) builds have no stdout.
        print(f"Orphanaut {orphanaut.__version__} self-test OK")
    return 0


def main() -> None:
    multiprocessing.freeze_support()

    if "--version" in sys.argv:
        from orphanaut import __version__

        if sys.stdout:
            print(__version__)
        return
    if "--self-test" in sys.argv:
        sys.exit(self_test())

    try:
        from PySide6.QtWidgets import QApplication

        from orphanaut.ui.icons import app_icon
        from orphanaut.ui.main_window import MainWindow
        from orphanaut.ui.styles import apply_theme

        app = QApplication(sys.argv)
        app.setApplicationName("Orphanaut")
        app.setOrganizationName("Orphanaut")
        app.setWindowIcon(app_icon())
        apply_theme(app)

        window = MainWindow()
        window.show()

        sys.exit(app.exec())
    except Exception as exc:
        log_path = _write_startup_log(traceback.format_exc())
        _show_startup_error(log_path, str(exc))
        sys.exit(1)


if __name__ == "__main__":
    main()
