"""Background workers for sign-in, scan and delete operations."""

from __future__ import annotations

from PySide6.QtCore import QObject, QThread, Signal

from orphanaut.actions.deleter import DeleteError, delete_resource
from orphanaut.auth.router import AuthenticationError, ConnectResult, connect
from orphanaut.models import AuthConfig, CloudResource
from orphanaut.providers.session import ProviderSession
from orphanaut.scanners.registry import scan_all


class AuthWorker(QObject):
    device_code = Signal(object)
    connected = Signal(object)
    error = Signal(str)
    finished = Signal()

    def __init__(self, config: AuthConfig) -> None:
        super().__init__()
        self._config = config
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        try:
            result = connect(
                self._config,
                on_device_code=self.device_code.emit,
                should_cancel=lambda: self._cancelled,
            )
            if not self._cancelled:
                self.connected.emit(result)
        except AuthenticationError as exc:
            self.error.emit(str(exc))
        except Exception as exc:  # Unexpected SDK errors still need a friendly message.
            self.error.emit(f"Sign-in failed: {exc}")
        finally:
            self.finished.emit()


class SwitchWorker(QObject):
    """Re-bind a connection to another account/subscription/project."""

    switched = Signal(object)
    error = Signal(str)
    finished = Signal()

    def __init__(self, result: ConnectResult, key: str) -> None:
        super().__init__()
        self._result = result
        self._key = key

    def run(self) -> None:
        try:
            assert self._result.rebind is not None
            self.switched.emit(self._result.rebind(self._key))
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class ScanWorker(QObject):
    progress = Signal(object)
    scanned = Signal(list)
    error = Signal(str)
    finished = Signal()

    def __init__(self, session: ProviderSession, regions: list[str]) -> None:
        super().__init__()
        self._session = session
        self._regions = regions

    def run(self) -> None:
        try:
            resources = scan_all(
                self._session,
                on_progress=self.progress.emit,
                regions=self._regions,
            )
            self.scanned.emit(resources)
        except Exception as exc:
            self.error.emit(str(exc))
        finally:
            self.finished.emit()


class DeleteWorker(QObject):
    progress = Signal(str)
    resource_deleted = Signal(str)
    resource_failed = Signal(str, str)
    finished = Signal()

    def __init__(self, session: ProviderSession, resources: list[CloudResource]) -> None:
        super().__init__()
        self._session = session
        self._resources = resources

    def run(self) -> None:
        total = len(self._resources)
        for index, resource in enumerate(self._resources, start=1):
            label = f"{resource.resource_type} {resource.name or resource.resource_id}"
            prefix = f"[{index}/{total}] "
            self.progress.emit(f"{prefix}Deleting {label}...")
            try:
                delete_resource(
                    self._session,
                    resource,
                    on_progress=lambda message, p=prefix: self.progress.emit(p + message),
                )
                self.resource_deleted.emit(resource.display_key)
            except DeleteError as exc:
                self.resource_failed.emit(resource.display_key, str(exc))
            except Exception as exc:
                self.resource_failed.emit(resource.display_key, str(exc))
        self.finished.emit()


def run_in_thread(worker: QObject, parent: QObject | None = None) -> QThread:
    """Move a worker to a background thread and start it when the thread starts."""
    thread = QThread(parent)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(thread.quit)
    worker.finished.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    return thread
