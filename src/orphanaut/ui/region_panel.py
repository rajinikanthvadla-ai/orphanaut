"""Region selection panel for targeted scans."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from orphanaut.aws.regions import COMMON_REGIONS, region_display_name


class RegionPanel(QWidget):
    selection_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._all_regions: list[str] = []
        self._build_ui()
        self.setEnabled(False)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        header = QLabel("Step 2 — Choose regions to scan")
        header.setObjectName("sectionHeader")
        layout.addWidget(header)

        tip = QLabel("Pick only the regions you used in class. Fewer regions = much faster scans.")
        tip.setObjectName("infoBanner")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        buttons = QHBoxLayout()
        self._common_btn = QPushButton("Common 5")
        self._common_btn.clicked.connect(self._select_common)
        self._all_btn = QPushButton("All")
        self._all_btn.clicked.connect(self._select_all)
        self._none_btn = QPushButton("None")
        self._none_btn.clicked.connect(self._select_none)
        buttons.addWidget(self._common_btn)
        buttons.addWidget(self._all_btn)
        buttons.addWidget(self._none_btn)
        layout.addLayout(buttons)

        self._list = QListWidget()
        self._list.setObjectName("regionList")
        self._list.setMinimumHeight(210)
        self._list.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._list, stretch=1)

        self._summary = QLabel("No regions selected")
        self._summary.setObjectName("subtitle")
        layout.addWidget(self._summary)

    def set_regions(self, regions: list[str]) -> None:
        self._all_regions = sorted(regions)
        self._list.blockSignals(True)
        self._list.clear()
        for region in self._all_regions:
            item = QListWidgetItem(region_display_name(region))
            item.setData(Qt.ItemDataRole.UserRole, region)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                Qt.CheckState.Checked if region == "us-east-1" else Qt.CheckState.Unchecked
            )
            self._list.addItem(item)
        self._list.blockSignals(False)
        self.setEnabled(True)
        self._update_summary()

    def selected_regions(self) -> list[str]:
        selected: list[str] = []
        for index in range(self._list.count()):
            item = self._list.item(index)
            if item and item.checkState() == Qt.CheckState.Checked:
                region = item.data(Qt.ItemDataRole.UserRole)
                if region:
                    selected.append(region)
        return selected

    def _select_common(self) -> None:
        self._set_checks(lambda region: region in COMMON_REGIONS)

    def _select_all(self) -> None:
        self._set_checks(lambda _region: True)

    def _select_none(self) -> None:
        self._set_checks(lambda _region: False)

    def _set_checks(self, predicate) -> None:
        self._list.blockSignals(True)
        for index in range(self._list.count()):
            item = self._list.item(index)
            if not item:
                continue
            region = item.data(Qt.ItemDataRole.UserRole)
            checked = predicate(region)
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self._list.blockSignals(False)
        self._update_summary()
        self.selection_changed.emit()

    def _on_item_changed(self, _item: QListWidgetItem) -> None:
        self._update_summary()
        self.selection_changed.emit()

    def _update_summary(self) -> None:
        count = len(self.selected_regions())
        if count == 0:
            self._summary.setText("No regions selected — check at least one")
        elif count == len(self._all_regions):
            self._summary.setText(f"All {count} regions selected")
        else:
            self._summary.setText(f"{count} region(s) selected")

    def clear(self) -> None:
        self._all_regions = []
        self._list.clear()
        self._summary.setText("Connect to AWS to load regions")
        self.setEnabled(False)
