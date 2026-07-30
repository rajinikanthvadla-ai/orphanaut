"""Main application window."""

from __future__ import annotations

import csv
from pathlib import Path

import boto3
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from orphanaut.auth.credentials import AuthenticationError, create_session, validate_credentials
from orphanaut.models import AuthConfig, AwsResource
from orphanaut.ui.auth_panel import AuthPanel
from orphanaut.ui.workers import DeleteWorker, ScanWorker, run_in_thread


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Orphanaut — AWS Resource Scanner")
        self.setMinimumSize(1100, 700)
        self.resize(1280, 800)

        self._session: boto3.Session | None = None
        self._resources: list[AwsResource] = []
        self._resource_map: dict[str, AwsResource] = {}
        self._scan_thread = None
        self._delete_thread = None

        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(16, 16, 16, 8)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter, stretch=1)

        self._auth_panel = AuthPanel()
        self._auth_panel.setMinimumWidth(340)
        self._auth_panel.setMaximumWidth(420)
        self._auth_panel.connect_requested.connect(self._on_connect)
        self._auth_panel.connection_changed.connect(self._on_connection_changed)
        splitter.addWidget(self._auth_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 0, 0, 0)

        toolbar = QHBoxLayout()
        self._scan_btn = QPushButton("▶  Scan All Regions")
        self._scan_btn.setObjectName("primary")
        self._scan_btn.setEnabled(False)
        self._scan_btn.setMinimumHeight(36)
        self._scan_btn.clicked.connect(self._on_scan)

        self._delete_btn = QPushButton("Delete Selected")
        self._delete_btn.setObjectName("danger")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._on_delete)

        self._export_btn = QPushButton("Export CSV")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._on_export)

        self._search_input = QLineEdit()
        self._search_input.setObjectName("search")
        self._search_input.setPlaceholderText("Filter by service, region, ID, name...")
        self._search_input.textChanged.connect(self._apply_filter)

        self._count_label = QLabel("0 resources")
        self._count_label.setObjectName("subtitle")

        toolbar.addWidget(self._scan_btn)
        toolbar.addWidget(self._delete_btn)
        toolbar.addWidget(self._export_btn)
        toolbar.addStretch()
        toolbar.addWidget(self._search_input)
        right_layout.addLayout(toolbar)

        self._content_stack = QStackedWidget()

        self._welcome_view = self._build_welcome_view()
        self._content_stack.addWidget(self._welcome_view)

        self._ready_view = self._build_ready_view()
        self._content_stack.addWidget(self._ready_view)

        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget(0, len(AwsResource.COLUMNS))
        self._table.setHorizontalHeaderLabels(AwsResource.COLUMNS)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self._table.setSortingEnabled(True)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        table_layout.addWidget(self._table)
        self._content_stack.addWidget(table_container)

        right_layout.addWidget(self._content_stack, stretch=1)

        summary_row = QHBoxLayout()
        summary_row.addWidget(self._count_label)
        summary_row.addStretch()
        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setVisible(False)
        self._progress.setFixedWidth(200)
        summary_row.addWidget(self._progress)
        right_layout.addLayout(summary_row)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 900])

        status = QStatusBar()
        self.setStatusBar(status)
        status.showMessage("Welcome — connect with your AWS Access Keys to get started")

    def _build_welcome_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("welcomeCard")
        card.setMaximumWidth(560)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(16)
        card_layout.setContentsMargins(32, 32, 32, 32)

        heading = QLabel("Welcome to Orphanaut")
        heading.setObjectName("welcomeTitle")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)

        intro = QLabel(
            "This app helps you find AWS resources left running in your account "
            "that can cost money — EC2 instances, databases, storage, and more."
        )
        intro.setObjectName("welcomeBody")
        intro.setWordWrap(True)
        intro.setAlignment(Qt.AlignmentFlag.AlignCenter)

        steps = QLabel(
            "<table cellspacing='0' cellpadding='6'>"
            "<tr><td><span class='bigStep'>1</span></td>"
            "<td><b>Paste your Access Key ID &amp; Secret Key</b> in the left panel</td></tr>"
            "<tr><td><span class='bigStep'>2</span></td>"
            "<td><b>Click Connect</b> to verify your AWS account</td></tr>"
            "<tr><td><span class='bigStep'>3</span></td>"
            "<td><b>Scan All Regions</b> to find billable resources</td></tr>"
            "<tr><td><span class='bigStep'>4</span></td>"
            "<td><b>Review &amp; delete</b> anything you no longer need</td></tr>"
            "</table>"
        )
        steps.setObjectName("welcomeSteps")
        steps.setWordWrap(True)

        note = QLabel(
            "Your keys are only used in this session and are never saved to disk."
        )
        note.setObjectName("welcomeNote")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setWordWrap(True)

        card_layout.addWidget(heading)
        card_layout.addWidget(intro)
        card_layout.addWidget(steps)
        card_layout.addWidget(note)
        layout.addWidget(card)
        return widget

    def _build_ready_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("welcomeCard")
        card.setMaximumWidth(480)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(14)
        card_layout.setContentsMargins(32, 32, 32, 32)

        icon = QLabel("✓")
        icon.setObjectName("readyIcon")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)

        heading = QLabel("You're connected!")
        heading.setObjectName("welcomeTitle")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)

        body = QLabel(
            "Click <b>Scan All Regions</b> above to search every AWS region "
            "for resources that might be costing you money.\n\n"
            "The scan may take a minute depending on how many resources you have."
        )
        body.setObjectName("welcomeBody")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)

        scan_hint = QPushButton("▶  Scan All Regions")
        scan_hint.setObjectName("primary")
        scan_hint.setMinimumHeight(44)
        scan_hint.clicked.connect(self._on_scan)

        card_layout.addWidget(icon)
        card_layout.addWidget(heading)
        card_layout.addWidget(body)
        card_layout.addWidget(scan_hint)
        layout.addWidget(card)

        self._ready_scan_btn = scan_hint
        return widget

    def _on_connection_changed(self, connected: bool) -> None:
        if connected:
            if not self._resources:
                self._content_stack.setCurrentIndex(1)
        else:
            self._content_stack.setCurrentIndex(0)
            self._scan_btn.setEnabled(False)

    def _on_connect(self, config: AuthConfig) -> None:
        self._auth_panel.set_connecting()
        try:
            session = create_session(config)
            account_id, arn = validate_credentials(session)
            self._session = session
            self._auth_panel.set_connected(account_id, arn)
            self._scan_btn.setEnabled(True)
            self._ready_scan_btn.setEnabled(True)
            self.statusBar().showMessage(f"Connected to account {account_id} — click Scan All Regions")
        except AuthenticationError as exc:
            self._auth_panel.set_error(str(exc))
            self.statusBar().showMessage("Authentication failed — check your Access Keys")
        finally:
            self._auth_panel.set_connect_enabled(True)

    def _on_scan(self) -> None:
        if not self._session:
            return

        self._scan_btn.setEnabled(False)
        self._ready_scan_btn.setEnabled(False)
        self._delete_btn.setEnabled(False)
        self._export_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._content_stack.setCurrentIndex(2)
        self.statusBar().showMessage("Scanning all AWS regions — this may take a minute...")

        worker = ScanWorker(self._session)
        thread = run_in_thread(worker, self)
        self._scan_thread = thread

        worker.progress.connect(self._on_scan_progress)
        worker.finished.connect(self._on_scan_finished)
        worker.error.connect(self._on_scan_error)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _on_scan_progress(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def _on_scan_finished(self, resources: list[AwsResource]) -> None:
        self._resources = resources
        self._populate_table(resources)
        self._scan_btn.setEnabled(True)
        self._ready_scan_btn.setEnabled(True)
        self._delete_btn.setEnabled(bool(resources))
        self._export_btn.setEnabled(bool(resources))
        self._progress.setVisible(False)
        self._auth_panel.set_scan_complete()
        self.statusBar().showMessage(f"Scan complete — found {len(resources)} resources")

    def _on_scan_error(self, message: str) -> None:
        self._scan_btn.setEnabled(True)
        self._ready_scan_btn.setEnabled(True)
        self._progress.setVisible(False)
        QMessageBox.critical(self, "Scan Failed", message)
        self.statusBar().showMessage("Scan failed")

    def _populate_table(self, resources: list[AwsResource]) -> None:
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        self._resource_map.clear()

        for row_idx, resource in enumerate(resources):
            self._resource_map[resource.display_key] = resource
            self._table.insertRow(row_idx)
            for col_idx, value in enumerate(resource.to_row()):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, resource.display_key)
                self._table.setItem(row_idx, col_idx, item)

        self._table.setSortingEnabled(True)
        self._update_count(len(resources))

    def _apply_filter(self, text: str) -> None:
        text = text.lower().strip()
        visible = 0
        for row in range(self._table.rowCount()):
            if not text:
                self._table.setRowHidden(row, False)
                visible += 1
                continue
            match = False
            for col in range(self._table.columnCount()):
                item = self._table.item(row, col)
                if item and text in item.text().lower():
                    match = True
                    break
            self._table.setRowHidden(row, not match)
            if match:
                visible += 1
        self._update_count(visible, total=len(self._resources))

    def _update_count(self, visible: int, total: int | None = None) -> None:
        if total is not None and visible != total:
            self._count_label.setText(f"{visible} of {total} resources shown")
        else:
            self._count_label.setText(f"{visible} resources")

    def _selected_resources(self) -> list[AwsResource]:
        selected: list[AwsResource] = []
        seen: set[str] = set()
        for item in self._table.selectedItems():
            key = item.data(Qt.ItemDataRole.UserRole)
            if key and key not in seen and key in self._resource_map:
                seen.add(key)
                selected.append(self._resource_map[key])
        return selected

    def _on_delete(self) -> None:
        selected = self._selected_resources()
        if not selected or not self._session:
            return

        preview = "\n".join(
            f"  • {r.service} / {r.resource_type}: {r.resource_id} ({r.region})"
            for r in selected[:15]
        )
        if len(selected) > 15:
            preview += f"\n  ... and {len(selected) - 15} more"

        reply = QMessageBox.warning(
            self,
            "Confirm Deletion",
            f"You are about to permanently delete {len(selected)} resource(s):\n\n"
            f"{preview}\n\n"
            "This action cannot be undone. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._scan_btn.setEnabled(False)
        self._delete_btn.setEnabled(False)
        self._progress.setVisible(True)
        self.statusBar().showMessage("Deleting resources...")

        worker = DeleteWorker(self._session, selected)
        thread = run_in_thread(worker, self)
        self._delete_thread = thread

        worker.progress.connect(lambda msg: self.statusBar().showMessage(msg))
        worker.resource_deleted.connect(self._on_resource_deleted)
        worker.resource_failed.connect(self._on_resource_failed)
        worker.finished.connect(self._on_delete_finished)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _on_resource_deleted(self, display_key: str) -> None:
        self._resources = [r for r in self._resources if r.display_key != display_key]
        self._resource_map.pop(display_key, None)
        for row in range(self._table.rowCount()):
            item = self._table.item(row, 0)
            if item and item.data(Qt.ItemDataRole.UserRole) == display_key:
                self._table.removeRow(row)
                break
        self._update_count(self._table.rowCount() - sum(
            1 for r in range(self._table.rowCount()) if self._table.isRowHidden(r)
        ), total=len(self._resources))

    def _on_resource_failed(self, display_key: str, error: str) -> None:
        resource = self._resource_map.get(display_key)
        name = resource.resource_id if resource else display_key
        QMessageBox.warning(self, "Delete Failed", f"Could not delete {name}:\n{error}")

    def _on_delete_finished(self) -> None:
        self._scan_btn.setEnabled(True)
        self._delete_btn.setEnabled(bool(self._resources))
        self._progress.setVisible(False)
        self.statusBar().showMessage("Delete operation complete")

    def _on_export(self) -> None:
        if not self._resources:
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Resources",
            str(Path.home() / "orphanaut-scan.csv"),
            "CSV Files (*.csv)",
        )
        if not path:
            return

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(AwsResource.COLUMNS)
            for resource in self._resources:
                writer.writerow(resource.to_row())

        self.statusBar().showMessage(f"Exported to {path}")

    def closeEvent(self, event) -> None:
        for thread in (self._scan_thread, self._delete_thread):
            if thread and thread.isRunning():
                thread.quit()
                thread.wait(3000)
        super().closeEvent(event)
