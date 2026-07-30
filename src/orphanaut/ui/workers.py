"""Background workers for scan and delete operations."""

from __future__ import annotations

import boto3
from PySide6.QtCore import QObject, QThread, Signal

from orphanaut.actions.deleter import DeleteError, delete_resource
from orphanaut.models import AwsResource
from orphanaut.scanners.registry import scan_all


class ScanWorker(QObject):
    progress = Signal(object)
    finished = Signal(list)
    error = Signal(str)

    def __init__(self, session: boto3.Session, regions: list[str]) -> None:
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
            self.finished.emit(resources)
        except Exception as exc:
            self.error.emit(str(exc))


class DeleteWorker(QObject):
    progress = Signal(str)
    resource_deleted = Signal(str)
    resource_failed = Signal(str, str)
    finished = Signal()

    def __init__(self, session: boto3.Session, resources: list[AwsResource]) -> None:
        super().__init__()
        self._session = session
        self._resources = resources

    def run(self) -> None:
        for resource in self._resources:
            label = f"{resource.service} {resource.resource_id}"
            self.progress.emit(f"Deleting {label}...")
            try:
                delete_resource(self._session, resource)
                self.resource_deleted.emit(resource.display_key)
            except DeleteError as exc:
                self.resource_failed.emit(resource.display_key, str(exc))
            except Exception as exc:
                self.resource_failed.emit(resource.display_key, str(exc))
        self.finished.emit()


def run_in_thread(worker: QObject, parent: QObject | None = None) -> QThread:
    """Move a worker to a background thread and start it."""
    thread = QThread(parent)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.finished.connect(worker.deleteLater)
    worker.finished.connect(thread.quit)
    return thread
