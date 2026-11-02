"""One cloud's workspace: connection, regions, category tabs, results and delete impact map."""

from __future__ import annotations

import csv
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStackedWidget,
    QStyledItemDelegate,
    QTabBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from orphanaut.auth.router import ConnectResult, list_regions_for_provider
from orphanaut.categories import ALL, CATEGORIES
from orphanaut.dependencies import Action, impact_tree, root_action
from orphanaut.models import AuthConfig, AuthMethod, CloudProvider, CloudResource
from orphanaut.providers.pricing import estimate_monthly_cost, format_monthly_cost
from orphanaut.providers.session import ProviderSession
from orphanaut.scanners.registry import ScanProgress
from orphanaut.ui.connect_panel import ConnectPanel
from orphanaut.ui.guide import guide_html
from orphanaut.ui.impact_panel import DeleteConfirmDialog, ImpactPanel
from orphanaut.ui.styles import ACTION_COLORS
from orphanaut.ui.workers import AuthWorker, DeleteWorker, ScanWorker, SwitchWorker, run_in_thread

TABLE_COLUMNS = [
    "Region", "Service", "Type", "Name", "Status", "Est. $/mo", "Linked", "On delete", "Details",
]
_DEFAULT_REGION = {
    CloudProvider.AWS: "us-east-1",
    CloudProvider.AZURE: "eastus",
    CloudProvider.GCP: "us-central1",
}
_PAGE_GUIDE, _PAGE_READY, _PAGE_RESULTS = 0, 1, 2


class _NumberDelegate(QStyledItemDelegate):
    """Shows numeric cells nicely while Qt sorts them as numbers.

    (Overriding QTableWidgetItem.__lt__ in Python crashes some PySide6 builds.)
    """

    def __init__(self, money: bool, parent=None) -> None:
        super().__init__(parent)
        self._money = money

    def displayText(self, value, locale) -> str:  # noqa: N802 - Qt API
        if not isinstance(value, (int, float)) or value < 0 or (not self._money and value == 0):
            return "—" if not self._money or value < 0 else "$0.00"
        if not self._money:
            return str(value)
        return f"${value:,.0f}" if value >= 100 else f"${value:,.2f}"


class CloudWorkspace(QWidget):
    state_changed = Signal(object, bool)  # provider, connected
    status_message = Signal(str)

    def __init__(self, provider: CloudProvider) -> None:
        super().__init__()
        self.provider = provider
        self._session: ProviderSession | None = None
        self._connect_result: ConnectResult | None = None
        self._resources: list[CloudResource] = []
        self._by_key: dict[str, CloudResource] = {}
        self._failed_checks = 0
        self._busy = False
        self._threads: dict = {}  # worker -> QThread; keeps both alive while running
        self._auth_worker: AuthWorker | None = None
        self._failures: list[str] = []
        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 6)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        root.addWidget(splitter)

        side = QFrame()
        side.setObjectName("sidePanel")
        side_layout = QVBoxLayout(side)
        side_layout.setContentsMargins(0, 0, 0, 0)
        self.connect_panel = ConnectPanel(self.provider)
        self.connect_panel.connect_requested.connect(self._on_connect)
        self.connect_panel.cancel_requested.connect(self._on_cancel_connect)
        self.connect_panel.switch_requested.connect(self._on_switch)
        self.connect_panel.disconnect_requested.connect(self.disconnect)
        self.connect_panel.region_panel.selection_changed.connect(self._update_scan_label)
        side_layout.addWidget(self.connect_panel)
        side.setMinimumWidth(340)
        side.setMaximumWidth(460)
        splitter.addWidget(side)

        main = QWidget()
        main_layout = QVBoxLayout(main)
        main_layout.setContentsMargins(12, 0, 0, 0)
        main_layout.setSpacing(10)

        toolbar = QHBoxLayout()
        self._scan_btn = QPushButton("▶  Scan")
        self._scan_btn.setObjectName("primary")
        self._scan_btn.setEnabled(False)
        self._scan_btn.clicked.connect(self._on_scan)
        self._export_btn = QPushButton("Export CSV")
        self._export_btn.setEnabled(False)
        self._export_btn.clicked.connect(self._on_export)
        self._search = QLineEdit()
        self._search.setObjectName("search")
        self._search.setPlaceholderText("Search name, ID, service, region…")
        self._search.textChanged.connect(self._apply_filter)
        self._delete_btn = QPushButton("Delete selected")
        self._delete_btn.setObjectName("danger")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._on_delete)
        toolbar.addWidget(self._scan_btn)
        toolbar.addWidget(self._export_btn)
        toolbar.addStretch()
        toolbar.addWidget(self._search)
        toolbar.addWidget(self._delete_btn)
        main_layout.addLayout(toolbar)

        summary = QHBoxLayout()
        self._count_label = QLabel("")
        self._count_label.setObjectName("subtitle")
        self._cost_label = QLabel("")
        self._cost_label.setObjectName("subtitle")
        self._cost_label.setToolTip("Rough list-price estimate if left running — not your bill.")
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setFixedWidth(220)
        self._progress.setVisible(False)
        summary.addWidget(self._count_label)
        summary.addSpacing(12)
        summary.addWidget(self._cost_label)
        summary.addStretch()
        summary.addWidget(self._progress)
        main_layout.addLayout(summary)

        self._activity = QLabel("")
        self._activity.setObjectName("scanBanner")
        self._activity.setWordWrap(True)
        self._activity.setVisible(False)
        self._warning = QLabel("")
        self._warning.setObjectName("warningBanner")
        self._warning.setWordWrap(True)
        self._warning.setVisible(False)
        main_layout.addWidget(self._activity)
        main_layout.addWidget(self._warning)

        self._tabs = QTabBar()
        self._tabs.setObjectName("categoryTabs")
        self._tabs.setDrawBase(False)
        self._tabs.setExpanding(False)
        for category in CATEGORIES:
            self._tabs.addTab(category.replace("&", "&&"))
        self._tabs.currentChanged.connect(lambda _i: self._apply_filter())
        main_layout.addWidget(self._tabs)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_guide_page())
        self._stack.addWidget(self._build_ready_page())
        self._stack.addWidget(self._build_results_page())
        main_layout.addWidget(self._stack, stretch=1)
        splitter.addWidget(main)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([380, 1000])
        self._tabs.setVisible(False)

    def _build_guide_page(self) -> QWidget:
        label = QLabel(
            f"<h2>Get started with {self.provider.long_label}</h2>"
            "<p style='color:#5B6B82'>Connect on the left — the guide below explains every "
            "option.</p>" + guide_html(self.provider)
        )
        label.setObjectName("guide")
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setOpenExternalLinks(True)
        label.setAlignment(Qt.AlignmentFlag.AlignTop)
        label.setContentsMargins(22, 10, 22, 22)
        card = QFrame()
        card.setObjectName("card")
        lay = QVBoxLayout(card)
        lay.addWidget(label)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(card)
        return scroll

    def _build_ready_page(self) -> QWidget:
        page = QWidget()
        lay = QVBoxLayout(page)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame()
        card.setObjectName("welcomeCard")
        card.setMaximumWidth(620)
        inner = QVBoxLayout(card)
        inner.setContentsMargins(32, 28, 32, 28)
        inner.setSpacing(12)
        title = QLabel("You're connected 🎉")
        title.setObjectName("welcomeTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        body = QLabel(
            "Pick the regions you used in the panel on the left (one region is fastest), "
            "then scan. AI & ML services — like SageMaker, Bedrock, Azure OpenAI and Vertex AI "
            "— are included and get their own tab."
        )
        body.setObjectName("welcomeBody")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ready_scan_btn = QPushButton("▶  Scan")
        self._ready_scan_btn.setObjectName("primary")
        self._ready_scan_btn.setMinimumHeight(44)
        self._ready_scan_btn.clicked.connect(self._on_scan)
        inner.addWidget(title)
        inner.addWidget(body)
        inner.addWidget(self._ready_scan_btn)
        lay.addWidget(card)
        return page

    def _build_results_page(self) -> QWidget:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        self._table = QTableWidget(0, len(TABLE_COLUMNS))
        self._table.setHorizontalHeaderLabels(TABLE_COLUMNS)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.ExtendedSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSortingEnabled(True)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        for name, width in (("Region", 96), ("Service", 104), ("Type", 140), ("Name", 170),
                            ("Status", 110), ("Est. $/mo", 92), ("Linked", 60),
                            ("On delete", 84), ("Details", 260)):
            self._table.setColumnWidth(TABLE_COLUMNS.index(name), width)
        self._table.setItemDelegateForColumn(
            TABLE_COLUMNS.index("Est. $/mo"), _NumberDelegate(True, self._table))
        self._table.setItemDelegateForColumn(
            TABLE_COLUMNS.index("Linked"), _NumberDelegate(False, self._table))
        self._table.itemSelectionChanged.connect(self._on_selection)
        self._impact = ImpactPanel()
        self._impact.setMinimumWidth(300)
        splitter.addWidget(self._table)
        splitter.addWidget(self._impact)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 0)
        splitter.setSizes([760, 360])
        return splitter

    # ------------------------------------------------------------- connect
    def _start(self, worker, connections: dict) -> None:
        thread = run_in_thread(worker, self)
        for signal_name, slot in connections.items():
            getattr(worker, signal_name).connect(slot)
        self._threads[worker] = thread
        # Bound methods (not lambdas) so Qt delivers these on the UI thread.
        worker.finished.connect(self._forget_worker)
        thread.start()

    def _forget_worker(self) -> None:
        self._threads.pop(self.sender(), None)
        for worker, thread in list(self._threads.items()):
            try:
                if thread.isFinished():
                    self._threads.pop(worker, None)
            except RuntimeError:  # Qt already deleted it.
                self._threads.pop(worker, None)

    def _on_connect(self, config: AuthConfig) -> None:
        if self._busy:
            return
        browser = config.method == AuthMethod.BROWSER
        self.connect_panel.set_busy(
            "Opening your browser to sign in…" if browser else "Checking your credentials…"
        )
        self.status_message.emit(f"Connecting to {self.provider.label}…")
        worker = AuthWorker(config)
        self._auth_worker = worker
        self._start(worker, {
            "device_code": self.connect_panel.show_device_code,
            "connected": self._on_connected,
            "error": self._on_connect_error,
        })

    def _on_cancel_connect(self) -> None:
        if self._auth_worker:
            self._auth_worker.cancel()
        self.connect_panel.set_error("Sign-in cancelled.")

    def _on_connect_error(self, message: str) -> None:
        self._auth_worker = None
        self.connect_panel.set_error(message)
        self.status_message.emit(f"{self.provider.label}: sign-in failed")

    def _on_connected(self, result: ConnectResult) -> None:
        self._auth_worker = None
        self._connect_result = result
        self._set_session(result.session)
        self.connect_panel.set_connected(result)
        self._stack.setCurrentIndex(_PAGE_READY)
        self.state_changed.emit(self.provider, True)
        self.status_message.emit(
            f"Connected to {self.provider.label} — choose regions and press Scan"
        )

    def _set_session(self, session: ProviderSession) -> None:
        self._session = session
        regions = list_regions_for_provider(self.provider, session.session)
        panel = self.connect_panel.region_panel
        panel.set_provider(self.provider)
        panel.set_regions(regions, default_region=_DEFAULT_REGION[self.provider])
        self._clear_results()
        self._update_scan_label()

    def _on_switch(self, key: str) -> None:
        if not self._connect_result or self._busy:
            return
        self.connect_panel.update_session_label("Switching…")
        self._start(SwitchWorker(self._connect_result, key), {
            "switched": self._on_switched,
            "error": self._on_switch_error,
        })

    def _on_switch_error(self, message: str) -> None:
        QMessageBox.warning(self, "Could not switch", message)

    def _on_switched(self, session: ProviderSession) -> None:
        self._set_session(session)
        self.connect_panel.update_session_label(session.account_label)
        self._stack.setCurrentIndex(_PAGE_READY)
        self.status_message.emit(f"Now using {session.account_label}")

    def disconnect(self) -> None:
        if self._busy:
            return
        self._session = None
        self._connect_result = None
        self._clear_results()
        self.connect_panel.set_disconnected()
        self._scan_btn.setEnabled(False)
        self._stack.setCurrentIndex(_PAGE_GUIDE)
        self._tabs.setVisible(False)
        self.state_changed.emit(self.provider, False)

    @property
    def connected(self) -> bool:
        return self._session is not None

    # ---------------------------------------------------------------- scan
    def _update_scan_label(self) -> None:
        regions = self.connect_panel.region_panel.selected_regions()
        if not regions:
            label = "▶  Scan (pick regions first)"
        elif len(regions) == 1:
            label = f"▶  Scan {regions[0]}"
        else:
            label = f"▶  Scan {len(regions)} regions"
        enabled = bool(self._session) and bool(regions) and not self._busy
        for button in (self._scan_btn, self._ready_scan_btn):
            button.setText(label)
            button.setEnabled(enabled)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self._update_scan_label()
        self._progress.setVisible(busy)
        self.connect_panel.setEnabled(not busy)
        self._update_delete_button()

    def _clear_results(self) -> None:
        self._resources = []
        self._by_key.clear()
        self._table.setRowCount(0)
        self._impact.show_resources([])
        self._warning.setVisible(False)
        self._count_label.setText("")
        self._cost_label.setText("")
        self._export_btn.setEnabled(False)
        self._update_tab_counts()

    def _on_scan(self) -> None:
        if not self._session or self._busy:
            return
        regions = self.connect_panel.region_panel.selected_regions()
        if not regions:
            return
        self._clear_results()
        self._failed_checks = 0
        self._set_busy(True)
        self._progress.setValue(0)
        self._activity.setText(f"Scanning {len(regions)} region(s)…")
        self._activity.setVisible(True)
        self._tabs.setVisible(True)
        self._stack.setCurrentIndex(_PAGE_RESULTS)
        self.status_message.emit("Scanning — results appear as they are found")
        self._start(ScanWorker(self._session, regions), {
            "progress": self._on_scan_progress,
            "scanned": self._on_scan_finished,
            "error": self._on_scan_error,
        })

    def _on_scan_progress(self, progress: ScanProgress) -> None:
        self._activity.setText(progress.message)
        self.status_message.emit(progress.message)
        if progress.total:
            self._progress.setValue(int(progress.completed / progress.total * 100))
        self._failed_checks = progress.failed_checks
        if progress.failed_checks:
            self._warning.setText(
                f"⚠ {progress.failed_checks} check(s) couldn't run (often missing permissions "
                "or a service not used in that region). Results may be incomplete."
                + (f"\nLatest: {progress.last_error}" if progress.last_error else "")
            )
            self._warning.setVisible(True)
        if progress.new_resources:
            self._add_rows(progress.new_resources)

    def _on_scan_finished(self, resources: list[CloudResource]) -> None:
        # The final list carries cross-links (e.g. vector store ↔ knowledge base).
        self._clear_results_keep_banners()
        self._add_rows(resources)
        self._set_busy(False)
        self._activity.setVisible(False)
        found = len(resources)
        self.status_message.emit(
            f"Scan complete — {found} resource(s) found"
            + (f", {self._failed_checks} check(s) unavailable" if self._failed_checks else "")
        )
        if not found:
            self._count_label.setText("Nothing billable found in the selected regions 🎉")

    def _clear_results_keep_banners(self) -> None:
        self._resources = []
        self._by_key.clear()
        self._table.setRowCount(0)

    def _on_scan_error(self, message: str) -> None:
        self._set_busy(False)
        self._activity.setVisible(False)
        QMessageBox.critical(self, "Scan failed", message)

    # --------------------------------------------------------------- table
    def _add_rows(self, resources: list[CloudResource]) -> None:
        self._table.setSortingEnabled(False)
        for resource in resources:
            if resource.display_key in self._by_key:
                continue
            self._resources.append(resource)
            self._by_key[resource.display_key] = resource
            self._insert_row(resource)
        self._table.setSortingEnabled(True)
        self._export_btn.setEnabled(bool(self._resources))
        self._update_tab_counts()
        self._apply_filter()
        self._update_cost()

    def _insert_row(self, resource: CloudResource) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        cost = estimate_monthly_cost(resource)
        linked = sum(1 for _ in impact_tree(resource).walk()) - 1
        action = root_action(resource)
        values = [
            resource.region, resource.service, resource.resource_type,
            resource.name or resource.resource_id.rsplit("/", 1)[-1],
            resource.status,
            format_monthly_cost(cost),
            str(linked) if linked else "—",
            "🔒 Locked" if not resource.deletable else action.label.split(" ")[0],
            resource.details,
        ]
        for col, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setData(Qt.ItemDataRole.UserRole, resource.display_key)
            item.setToolTip(f"ID: {resource.resource_id}" if col == 3 else value)
            if col == TABLE_COLUMNS.index("Est. $/mo"):
                item.setData(Qt.ItemDataRole.DisplayRole, float(cost) if cost is not None else -1.0)
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if col == TABLE_COLUMNS.index("Linked"):
                item.setData(Qt.ItemDataRole.DisplayRole, linked)
            if col == TABLE_COLUMNS.index("On delete"):
                color = "#94A3B8" if not resource.deletable else ACTION_COLORS[action.value]
                item.setForeground(QBrush(QColor(color)))
            if not resource.deletable:
                item.setToolTip(resource.extra.get("impact_note") or "In use or protected")
            self._table.setItem(row, col, item)

    def _row_key(self, row: int) -> str | None:
        item = self._table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _update_tab_counts(self) -> None:
        counts = {category: 0 for category in CATEGORIES}
        for resource in self._resources:
            counts[ALL] += 1
            counts[resource.category] = counts.get(resource.category, 0) + 1
        for index, category in enumerate(CATEGORIES):
            n = counts.get(category, 0)
            label = category.replace("&", "&&")
            self._tabs.setTabText(index, f"{label}  {n}" if n else label)

    def _apply_filter(self, *_args) -> None:
        category = CATEGORIES[max(self._tabs.currentIndex(), 0)]
        text = self._search.text().lower().strip()
        visible = 0
        for row in range(self._table.rowCount()):
            resource = self._by_key.get(self._row_key(row) or "")
            show = resource is not None and (category == ALL or resource.category == category)
            if show and text:
                show = any(
                    text in (self._table.item(row, col).text().lower())
                    for col in range(self._table.columnCount())
                    if self._table.item(row, col)
                ) or text in resource.resource_id.lower()
            self._table.setRowHidden(row, not show)
            visible += show
        total = len(self._resources)
        if total:
            self._count_label.setText(
                f"{visible} of {total} resources shown" if visible != total
                else f"{total} resources"
            )

    def _update_cost(self) -> None:
        priced = [c for c in (estimate_monthly_cost(r) for r in self._resources) if c is not None]
        if priced:
            self._cost_label.setText(f"≈ ${sum(priced):,.2f}/month if everything keeps running")
        else:
            self._cost_label.setText("")

    def _selected(self) -> list[CloudResource]:
        keys: list[str] = []
        for index in self._table.selectionModel().selectedRows():
            key = self._row_key(index.row())
            if key and key not in keys and not self._table.isRowHidden(index.row()):
                keys.append(key)
        return [self._by_key[k] for k in keys if k in self._by_key]

    def _on_selection(self) -> None:
        self._impact.show_resources(self._selected())
        self._update_delete_button()

    def _update_delete_button(self) -> None:
        selected = self._selected() if hasattr(self, "_table") else []
        deletable = [r for r in selected if r.deletable]
        ok = bool(selected) and len(deletable) == len(selected) and not self._busy
        self._delete_btn.setEnabled(ok)
        only_stop = selected and all(root_action(r) == Action.STOP for r in selected)
        verb = "Stop" if only_stop else "Delete"
        self._delete_btn.setText(f"{verb} {len(selected)} selected" if selected
                                 else "Delete selected")
        self._delete_btn.setToolTip(
            "" if ok or not selected else "Some selected items are locked (in use or protected)."
        )

    # -------------------------------------------------------------- delete
    def _on_delete(self) -> None:
        selected = [r for r in self._selected() if r.deletable]
        if not selected or not self._session or self._busy:
            return
        if DeleteConfirmDialog(selected, self).exec() != DeleteConfirmDialog.DialogCode.Accepted:
            return
        self._set_busy(True)
        self._progress.setRange(0, 0)
        self._activity.setText("Deleting… long cascades (e.g. SageMaker domains) can take "
                               "several minutes.")
        self._activity.setVisible(True)
        self._failures: list[str] = []
        self._start(DeleteWorker(self._session, selected), {
            "progress": self._on_delete_progress,
            "resource_deleted": self._on_resource_deleted,
            "resource_failed": self._on_resource_failed,
            "finished": self._on_delete_finished,
        })

    def _on_delete_progress(self, message: str) -> None:
        self._activity.setText(message)
        self.status_message.emit(message)

    def _on_resource_deleted(self, key: str) -> None:
        self._resources = [r for r in self._resources if r.display_key != key]
        self._by_key.pop(key, None)
        for row in range(self._table.rowCount()):
            if self._row_key(row) == key:
                self._table.removeRow(row)
                break
        self._update_tab_counts()
        self._apply_filter()
        self._update_cost()

    def _on_resource_failed(self, key: str, error: str) -> None:
        resource = self._by_key.get(key)
        name = (resource.name or resource.resource_id) if resource else key
        self._failures.append(f"• {name}: {error}")

    def _on_delete_finished(self) -> None:
        self._progress.setRange(0, 100)
        self._set_busy(False)
        self._activity.setVisible(False)
        self._on_selection()
        if self._failures:
            QMessageBox.warning(
                self, "Some items were not deleted",
                "\n\n".join(self._failures[:10])
                + "\n\nTip: check permissions, or wait a minute and run Scan again.",
            )
            self.status_message.emit("Delete finished with errors")
        else:
            self.status_message.emit("Delete complete — scan again in a few minutes to confirm")

    # -------------------------------------------------------------- export
    def _on_export(self) -> None:
        if not self._resources:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export resources",
            str(Path.home() / f"orphanaut-{self.provider.value}.csv"), "CSV files (*.csv)",
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow([*CloudResource.COLUMNS, "Category", "Linked items", "Est. $/mo"])
            for r in self._resources:
                linked = [f"{n.action.label}: {n.kind} {n.name}"
                          for n in list(impact_tree(r).walk())[1:]]
                writer.writerow([*r.to_row(), r.category, "; ".join(linked),
                                 format_monthly_cost(estimate_monthly_cost(r))])
        self.status_message.emit(f"Exported to {path}")

    def shutdown(self) -> None:
        if self._auth_worker:
            self._auth_worker.cancel()
        for thread in list(self._threads.values()):
            try:
                if thread.isRunning():
                    thread.quit()
                    thread.wait(2000)
            except RuntimeError:
                pass
