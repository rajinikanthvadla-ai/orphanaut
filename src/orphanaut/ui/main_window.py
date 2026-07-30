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
from orphanaut.aws.pricing import estimate_monthly_cost, format_monthly_cost
from orphanaut.models import AuthConfig, AwsResource
from orphanaut.scanners.registry import ScanProgress
from orphanaut.ui.auth_panel import AuthPanel
from orphanaut.ui.region_panel import RegionPanel
from orphanaut.ui.workers import DeleteWorker, ScanWorker, run_in_thread

TABLE_COLUMNS = [*AwsResource.COLUMNS, "Est. Cost"]


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
        self._scan_worker = None
        self._delete_thread = None
        self._delete_worker = None
        self._scan_failed_checks = 0

        self._build_ui()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(16, 16, 16, 8)
        root_layout.setSpacing(12)

        header = QHBoxLayout()
        brand = QVBoxLayout()
        app_title = QLabel("Orphanaut")
        app_title.setObjectName("appTitle")
        app_subtitle = QLabel("Find forgotten AWS resources before they cost you")
        app_subtitle.setObjectName("subtitle")
        brand.addWidget(app_title)
        brand.addWidget(app_subtitle)
        privacy = QLabel("🔒 Credentials stay on this device")
        privacy.setObjectName("privacyBadge")
        header.addLayout(brand)
        header.addStretch()
        header.addWidget(privacy)
        root_layout.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        root_layout.addWidget(splitter, stretch=1)

        self._auth_panel = AuthPanel()
        self._auth_panel.setMinimumWidth(340)
        self._auth_panel.setMaximumWidth(420)
        self._auth_panel.connect_requested.connect(self._on_connect)
        self._auth_panel.connection_changed.connect(self._on_connection_changed)

        self._region_panel = RegionPanel()
        self._region_panel.selection_changed.connect(self._update_scan_button_label)

        splitter.addWidget(self._auth_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(8, 0, 0, 0)

        toolbar = QHBoxLayout()
        self._scan_btn = QPushButton("▶  Scan Selected Regions")
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

        self._regions_btn = QPushButton("Regions")
        self._regions_btn.setEnabled(False)
        self._regions_btn.clicked.connect(lambda: self._content_stack.setCurrentIndex(1))

        self._search_input = QLineEdit()
        self._search_input.setObjectName("search")
        self._search_input.setPlaceholderText("Filter by service, region, ID, name...")
        self._search_input.textChanged.connect(self._apply_filter)

        self._count_label = QLabel("0 resources")
        self._count_label.setObjectName("subtitle")

        toolbar.addWidget(self._scan_btn)
        toolbar.addWidget(self._export_btn)
        toolbar.addWidget(self._regions_btn)
        toolbar.addStretch()
        toolbar.addWidget(self._search_input)
        toolbar.addWidget(self._delete_btn)
        right_layout.addLayout(toolbar)

        self._content_stack = QStackedWidget()

        self._welcome_view = self._build_welcome_view()
        self._content_stack.addWidget(self._welcome_view)

        self._ready_view = self._build_ready_view()
        self._content_stack.addWidget(self._ready_view)

        self._scanning_view = self._build_scanning_view()
        self._content_stack.addWidget(self._scanning_view)

        table_container = QWidget()
        table_layout = QVBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)

        self._table = QTableWidget(0, len(TABLE_COLUMNS))
        self._table.setHorizontalHeaderLabels(TABLE_COLUMNS)
        self._table.horizontalHeaderItem(len(TABLE_COLUMNS) - 1).setToolTip(
            "Rough on-demand estimate based on resource type/size while it "
            "keeps running. Not your actual AWS bill — real pricing varies "
            "by region, discounts, and usage."
        )
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self._table.setSortingEnabled(True)
        self._table.itemSelectionChanged.connect(self._update_delete_button)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._scan_activity_label = QLabel()
        self._scan_activity_label.setObjectName("scanBanner")
        self._scan_activity_label.setWordWrap(True)
        self._scan_activity_label.setVisible(False)
        self._scan_warning_label = QLabel()
        self._scan_warning_label.setObjectName("warningBanner")
        self._scan_warning_label.setWordWrap(True)
        self._scan_warning_label.setVisible(False)
        table_layout.addWidget(self._scan_activity_label)
        table_layout.addWidget(self._scan_warning_label)
        table_layout.addWidget(self._table)
        self._content_stack.addWidget(table_container)

        right_layout.addWidget(self._content_stack, stretch=1)

        self._cost_label = QLabel("")
        self._cost_label.setObjectName("subtitle")
        self._cost_label.setToolTip(
            "Rough on-demand estimate of what these resources cost per month "
            "if left running. Actual AWS billing may differ."
        )

        summary_row = QHBoxLayout()
        summary_row.addWidget(self._count_label)
        summary_row.addWidget(self._cost_label)
        summary_row.addStretch()
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress.setVisible(False)
        self._progress.setFixedWidth(220)
        self._progress.setFormat("%p%")
        summary_row.addWidget(self._progress)
        right_layout.addLayout(summary_row)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 900])

        status = QStatusBar()
        self.setStatusBar(status)
        status.showMessage("Welcome — connect with your AWS Access Keys to get started")
        credit = QLabel("Orphanaut · made by Rajinikanth Vadla")
        credit.setObjectName("creditLabel")
        status.addPermanentWidget(credit)

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
            "<td><b>Select regions</b> you used, then click Scan</td></tr>"
            "<tr><td><span class='bigStep'>4</span></td>"
            "<td><b>Review &amp; delete</b> anything you no longer need</td></tr>"
            "</table>"
        )
        steps.setObjectName("welcomeSteps")
        steps.setWordWrap(True)

        note = QLabel("Your keys are only used in this session and are never saved to disk.")
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
        card.setMaximumWidth(720)
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
            "Choose only the regions used in your lab. Start with one region for the "
            "fastest result; you can add more and scan again."
        )
        body.setObjectName("welcomeBody")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)

        scan_hint = QPushButton("▶  Scan Selected Regions")
        scan_hint.setObjectName("primary")
        scan_hint.setMinimumHeight(44)
        scan_hint.clicked.connect(self._on_scan)

        card_layout.addWidget(icon)
        card_layout.addWidget(heading)
        card_layout.addWidget(body)
        card_layout.addWidget(self._region_panel, stretch=1)
        card_layout.addWidget(scan_hint)
        layout.addWidget(card)

        self._ready_scan_btn = scan_hint
        return widget

    def _build_scanning_view(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card = QFrame()
        card.setObjectName("welcomeCard")
        card.setMaximumWidth(520)
        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(14)
        card_layout.setContentsMargins(32, 32, 32, 32)

        heading = QLabel("Scanning your AWS account...")
        heading.setObjectName("welcomeTitle")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._scan_status_label = QLabel("Starting scan...")
        self._scan_status_label.setObjectName("welcomeBody")
        self._scan_status_label.setWordWrap(True)
        self._scan_status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._scan_found_label = QLabel("0 resources found so far")
        self._scan_found_label.setObjectName("welcomeNote")
        self._scan_found_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        note = QLabel(
            "Common resources (EC2, RDS, Lambda, S3…) show up within the first minute.\n"
            "A full deep scan usually takes 3–8 minutes."
        )
        note.setObjectName("welcomeNote")
        note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        note.setWordWrap(True)

        card_layout.addWidget(heading)
        card_layout.addWidget(self._scan_status_label)
        card_layout.addWidget(self._scan_found_label)
        card_layout.addWidget(note)
        layout.addWidget(card)
        return widget

    def _on_connection_changed(self, connected: bool) -> None:
        if connected:
            if not self._resources:
                self._content_stack.setCurrentIndex(1)
            self._update_scan_button_label()
        else:
            self._content_stack.setCurrentIndex(0)
            self._scan_btn.setEnabled(False)
            self._regions_btn.setEnabled(False)
            self._region_panel.clear()

    def _update_scan_button_label(self) -> None:
        regions = self._region_panel.selected_regions()
        count = len(regions)
        if count == 0:
            label = "▶  Scan (pick regions first)"
        elif count == 1:
            label = f"▶  Scan {regions[0]}"
        else:
            label = f"▶  Scan {count} Regions"
        self._scan_btn.setText(label)
        self._ready_scan_btn.setText(label)

    def _load_regions(self) -> None:
        if not self._session:
            return
        regions = sorted(self._session.get_available_regions("ec2"))
        self._region_panel.set_regions(regions)
        self.statusBar().showMessage("Choose regions to scan — us-east-1 is selected by default")

    def _on_connect(self, config: AuthConfig) -> None:
        self._auth_panel.set_connecting()
        try:
            session = create_session(config)
            account_id, arn = validate_credentials(session)
            self._session = session
            self._auth_panel.set_connected(account_id, arn)
            self._scan_btn.setEnabled(True)
            self._ready_scan_btn.setEnabled(True)
            self._regions_btn.setEnabled(True)
            self._load_regions()
            self._update_scan_button_label()
            self.statusBar().showMessage(
                f"Connected to account {account_id} — select regions and scan"
            )
        except AuthenticationError as exc:
            self._auth_panel.set_error(str(exc))
            self.statusBar().showMessage("Authentication failed — check your Access Keys")
        finally:
            self._auth_panel.set_connect_enabled(True)

    def _on_scan(self) -> None:
        if not self._session:
            return

        selected_regions = self._region_panel.selected_regions()
        if not selected_regions:
            QMessageBox.warning(
                self,
                "No regions selected",
                "Check at least one region on the left panel before scanning.\n\n"
                "Tip: click **Common 5** for the regions most labs use.",
            )
            return

        self._scan_btn.setEnabled(False)
        self._ready_scan_btn.setEnabled(False)
        self._delete_btn.setEnabled(False)
        self._export_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._count_label.setText("Scanning...")
        self._resources = []
        self._resource_map.clear()
        self._scan_failed_checks = 0
        self._table.setRowCount(0)
        self._scan_warning_label.setVisible(False)
        self._scan_activity_label.setText(
            f"Scanning {len(selected_regions)} region(s)… Starting AWS checks."
        )
        self._scan_activity_label.setVisible(True)
        self._content_stack.setCurrentIndex(3)
        self._scan_status_label.setText("Starting scan...")
        self._scan_found_label.setText("0 resources found so far")
        self.statusBar().showMessage(
            f"Scanning {len(selected_regions)} region(s) — results appear as they are found"
        )

        worker = ScanWorker(self._session, selected_regions)
        thread = run_in_thread(worker, self)
        self._scan_worker = worker
        self._scan_thread = thread

        worker.progress.connect(self._on_scan_progress)
        worker.finished.connect(self._on_scan_finished)
        worker.error.connect(self._on_scan_error)
        thread.finished.connect(self._on_scan_thread_finished)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _on_scan_progress(self, progress: ScanProgress) -> None:
        self.statusBar().showMessage(progress.message)
        self._scan_status_label.setText(progress.message)
        self._scan_found_label.setText(f"{progress.resources_found} resources found so far")
        self._scan_activity_label.setText(progress.message)
        self._scan_failed_checks = progress.failed_checks
        if progress.failed_checks:
            self._scan_warning_label.setText(
                f"⚠ {progress.failed_checks} check(s) unavailable. "
                "Results may be incomplete. "
                + (f"Latest: {progress.last_error}" if progress.last_error else "")
            )
            self._scan_warning_label.setVisible(True)
        if progress.total > 0:
            percent = int((progress.completed / progress.total) * 100)
            self._progress.setValue(percent)
            self._count_label.setText(f"Scanning... {progress.completed}/{progress.total}")
        if progress.new_resources:
            self._append_resources(progress.new_resources)
            self._content_stack.setCurrentIndex(3)
            self._export_btn.setEnabled(True)

    def _append_resources(self, resources: list[AwsResource]) -> None:
        self._table.setSortingEnabled(False)
        for resource in resources:
            if resource.display_key in self._resource_map:
                continue
            self._resources.append(resource)
            self._resource_map[resource.display_key] = resource
            row_idx = self._table.rowCount()
            self._table.insertRow(row_idx)
            for col_idx, value in enumerate(self._row_values(resource)):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, resource.display_key)
                self._table.setItem(row_idx, col_idx, item)
        self._table.setSortingEnabled(True)
        self._update_count(len(self._resources))
        self._update_cost_summary()
        self._update_delete_button()

    @staticmethod
    def _row_values(resource: AwsResource) -> list[str]:
        cost = format_monthly_cost(estimate_monthly_cost(resource))
        return [*resource.to_row(), cost]

    def _update_cost_summary(self) -> None:
        if not self._resources:
            self._cost_label.setText("")
            return
        total = 0.0
        priced = 0
        for resource in self._resources:
            cost = estimate_monthly_cost(resource)
            if cost is not None:
                total += cost
                priced += 1
        self._cost_label.setText(
            f"≈ ${total:,.2f}/mo if left running ({priced}/{len(self._resources)} priced)"
        )

    def _on_scan_finished(self, resources: list[AwsResource]) -> None:
        self._resources = resources
        self._populate_table(resources)
        self._scan_btn.setEnabled(True)
        self._ready_scan_btn.setEnabled(True)
        self._update_delete_button()
        self._export_btn.setEnabled(bool(resources))
        self._progress.setVisible(False)
        self._progress.setValue(100)
        self._scan_activity_label.setVisible(False)
        self._content_stack.setCurrentIndex(3)
        self._auth_panel.set_scan_complete()
        if self._scan_failed_checks:
            self.statusBar().showMessage(
                f"Scan finished with {self._scan_failed_checks} unavailable checks — "
                f"{len(resources)} resources found"
            )
        elif resources:
            self.statusBar().showMessage(f"Scan complete — found {len(resources)} resources")
        else:
            self.statusBar().showMessage(
                "Scan complete — no billable resources found in selected regions"
            )
            QMessageBox.information(
                self,
                "Scan complete",
                "No resources were found in the selected regions.\n\n"
                "Try:\n"
                "• Select more regions (or click **All**)\n"
                "• Confirm your AWS keys have read permissions\n"
                "• Check the AWS Console to see if resources exist",
            )

    def _on_scan_error(self, message: str) -> None:
        self._scan_btn.setEnabled(True)
        self._ready_scan_btn.setEnabled(True)
        self._progress.setVisible(False)
        self._scan_activity_label.setVisible(False)
        self._content_stack.setCurrentIndex(3 if self._resources else 1)
        QMessageBox.critical(self, "Scan Failed", message)
        self.statusBar().showMessage("Scan failed")

    def _on_scan_thread_finished(self) -> None:
        self._scan_worker = None
        self._scan_thread = None

    def _populate_table(self, resources: list[AwsResource]) -> None:
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        self._resource_map.clear()

        for row_idx, resource in enumerate(resources):
            self._resource_map[resource.display_key] = resource
            self._table.insertRow(row_idx)
            for col_idx, value in enumerate(self._row_values(resource)):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, resource.display_key)
                self._table.setItem(row_idx, col_idx, item)

        self._table.setSortingEnabled(True)
        self._update_count(len(resources))
        self._update_cost_summary()

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

    def _update_delete_button(self) -> None:
        selected = self._selected_resources()
        deletable = bool(selected) and all(resource.deletable for resource in selected)
        self._delete_btn.setEnabled(deletable)
        if selected and not deletable:
            self._delete_btn.setToolTip("One or more selected resources are in use or protected.")
        else:
            self._delete_btn.setToolTip("")

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
        self._delete_worker = worker
        self._delete_thread = thread

        worker.progress.connect(lambda msg: self.statusBar().showMessage(msg))
        worker.resource_deleted.connect(self._on_resource_deleted)
        worker.resource_failed.connect(self._on_resource_failed)
        worker.finished.connect(self._on_delete_finished)
        thread.finished.connect(self._on_delete_thread_finished)
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
        self._update_count(
            self._table.rowCount()
            - sum(1 for r in range(self._table.rowCount()) if self._table.isRowHidden(r)),
            total=len(self._resources),
        )
        self._update_cost_summary()

    def _on_resource_failed(self, display_key: str, error: str) -> None:
        resource = self._resource_map.get(display_key)
        name = resource.resource_id if resource else display_key
        QMessageBox.warning(self, "Delete Failed", f"Could not delete {name}:\n{error}")

    def _on_delete_finished(self) -> None:
        self._scan_btn.setEnabled(True)
        self._update_delete_button()
        self._progress.setVisible(False)
        self.statusBar().showMessage("Delete operation complete")

    def _on_delete_thread_finished(self) -> None:
        self._delete_worker = None
        self._delete_thread = None

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
            writer.writerow(TABLE_COLUMNS)
            for resource in self._resources:
                writer.writerow(self._row_values(resource))

        self.statusBar().showMessage(f"Exported to {path}")

    def closeEvent(self, event) -> None:
        for thread in (self._scan_thread, self._delete_thread):
            if thread and thread.isRunning():
                thread.quit()
                thread.wait(3000)
        super().closeEvent(event)
