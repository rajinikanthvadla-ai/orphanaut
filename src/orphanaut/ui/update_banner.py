"""'A new version is available' banner: check, download and launch the update."""

from __future__ import annotations

import webbrowser

from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
)

from orphanaut import __version__, updater
from orphanaut.ui.workers import run_in_thread


class CheckWorker(QObject):
    found = Signal(object)  # ReleaseInfo | None
    error = Signal(str)
    finished = Signal()

    def run(self) -> None:
        try:
            self.found.emit(updater.check_for_update())
        except updater.UpdateError as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class DownloadWorker(QObject):
    progress = Signal(int, int)
    downloaded = Signal(str)
    error = Signal(str)
    finished = Signal()

    def __init__(self, asset: updater.Asset) -> None:
        super().__init__()
        self._asset = asset
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            path = updater.download(self._asset, self.progress.emit, lambda: self._cancelled)
            self.downloaded.emit(str(path))
        except updater.UpdateError as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class UpdateBanner(QFrame):
    """Hidden until a newer release exists; sits under the cloud tabs."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("updateBanner")
        self._release: updater.ReleaseInfo | None = None
        self._threads: dict = {}
        self._download: DownloadWorker | None = None
        self._manual = False
        layout = QHBoxLayout(self)
        layout.setContentsMargins(22, 8, 22, 8)
        self._text = QLabel("")
        self._text.setObjectName("updateText")
        self._progress = QProgressBar()
        self._progress.setFixedWidth(200)
        self._progress.setVisible(False)
        self._notes_btn = QPushButton("What's new")
        self._notes_btn.clicked.connect(self._show_notes)
        self._action_btn = QPushButton("Update now")
        self._action_btn.setObjectName("primary")
        self._action_btn.clicked.connect(self._on_action)
        self._later_btn = QPushButton("Later")
        self._later_btn.clicked.connect(self._on_later)
        layout.addWidget(self._text, stretch=1)
        layout.addWidget(self._progress)
        layout.addWidget(self._notes_btn)
        layout.addWidget(self._action_btn)
        layout.addWidget(self._later_btn)
        self.setVisible(False)

    # ------------------------------------------------------------- checking
    def check(self, manual: bool = False) -> None:
        """Ask GitHub for the latest release. Manual checks also report 'up to date'."""
        if not manual and updater.checks_disabled():
            return
        self._manual = manual
        self._start(CheckWorker(), {"found": self._on_found, "error": self._on_check_error})

    def _start(self, worker: QObject, connections: dict) -> None:
        thread = run_in_thread(worker, self)
        for name, slot in connections.items():
            getattr(worker, name).connect(slot)
        worker.finished.connect(self._forget)
        self._threads[worker] = thread
        thread.start()

    def _forget(self) -> None:
        self._threads.pop(self.sender(), None)

    def _on_found(self, release: updater.ReleaseInfo | None) -> None:
        if release is None:
            if self._manual:
                QMessageBox.information(self, "No updates",
                                        f"You have the latest version ({__version__}).")
            return
        skipped = QSettings().value("update/skipped_version", "")
        if skipped == release.version and not self._manual:
            return
        self._release = release
        self._text.setText(
            f"<b>Orphanaut {release.version}</b> is available - you have {__version__}."
        )
        self._action_btn.setText(updater.update_action_label(release))
        self._action_btn.setEnabled(True)
        self.setVisible(True)

    def _on_check_error(self, message: str) -> None:
        if self._manual:
            QMessageBox.warning(self, "Update check failed", message)

    # -------------------------------------------------------------- actions
    def _show_notes(self) -> None:
        if not self._release:
            return
        box = QMessageBox(self)
        box.setWindowTitle(f"What's new in {self._release.version}")
        box.setText(self._release.notes[:3000] or "See the release page for details.")
        box.exec()

    def _on_later(self) -> None:
        if self._download:
            self._download.cancel()
        if self._release:
            QSettings().setValue("update/skipped_version", self._release.version)
        self.setVisible(False)

    def _on_action(self) -> None:
        if not self._release:
            return
        asset = updater.pick_asset(self._release)
        if asset is None:
            webbrowser.open(self._release.page_url)
            return
        self._action_btn.setEnabled(False)
        self._notes_btn.setEnabled(False)
        self._progress.setRange(0, 0)
        self._progress.setVisible(True)
        self._text.setText(f"Downloading Orphanaut {self._release.version}...")
        self._download = DownloadWorker(asset)
        self._start(self._download, {
            "progress": self._on_progress,
            "downloaded": self._on_downloaded,
            "error": self._on_download_error,
        })

    def _on_progress(self, done: int, total: int) -> None:
        if total:
            self._progress.setRange(0, 100)
            self._progress.setValue(int(done * 100 / total))

    def _on_downloaded(self, path: str) -> None:
        self._download = None
        self._progress.setVisible(False)
        from pathlib import Path

        try:
            updater.launch_update(Path(path))
        except OSError as exc:
            self._on_download_error(f"Could not start the update: {exc}")
            return
        if path.lower().endswith(".exe"):
            self._text.setText("Installing the update - Orphanaut will reopen by itself.")
            QApplication.instance().quit()
        else:
            self._text.setText(
                "The new version is open in Finder - quit Orphanaut, then drag it into "
                "Applications and replace the old one."
            )

    def _on_download_error(self, message: str) -> None:
        self._download = None
        self._progress.setVisible(False)
        self._action_btn.setEnabled(True)
        self._notes_btn.setEnabled(True)
        if self._release:
            self._text.setText(f"<b>Orphanaut {self._release.version}</b> is available.")
        QMessageBox.warning(
            self, "Update failed",
            f"{message}\n\nYou can also download it from the release page.",
        )

    def shutdown(self) -> None:
        if self._download:
            self._download.cancel()
        for thread in list(self._threads.values()):
            try:
                if thread.isRunning():
                    thread.quit()
                    thread.wait(2000)
            except RuntimeError:
                pass
