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

from orphanaut.aws.regions import COMMON_REGIONS as AWS_COMMON
from orphanaut.aws.regions import region_display_name as aws_region_display_name
from orphanaut.models import CloudProvider
from orphanaut.providers.azure_regions import AZURE_COMMON_REGIONS, azure_region_display_name
from orphanaut.providers.gcp_regions import GCP_COMMON_REGIONS, gcp_region_display_name


class RegionPanel(QWidget):
    selection_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._provider = CloudProvider.AWS
        self._all_regions: list[str] = []
        self._default_region = "us-east-1"
        self._build_ui()
        self.setEnabled(False)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 8, 0, 0)
        layout.setSpacing(8)

        self._header = QLabel("Regions to scan")
        self._header.setObjectName("sectionHeader")
        layout.addWidget(self._header)

        self._tip = QLabel("Pick only the regions you used. Fewer regions = faster scans.")
        self._tip.setObjectName("infoBanner")
        self._tip.setWordWrap(True)
        layout.addWidget(self._tip)

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
        self._list.setMinimumHeight(180)
        self._list.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self._list, stretch=1)

        self._summary = QLabel("No regions selected")
        self._summary.setObjectName("subtitle")
        layout.addWidget(self._summary)

    def set_provider(self, provider: CloudProvider) -> None:
        self._provider = provider
        self._header.setText(f"{provider.label} regions to scan")

    def _display_name(self, region: str) -> str:
        match self._provider:
            case CloudProvider.AWS:
                return aws_region_display_name(region)
            case CloudProvider.AZURE:
                return azure_region_display_name(region)
            case CloudProvider.GCP:
                return gcp_region_display_name(region)
            case _:
                return region

    def _common_set(self) -> frozenset[str]:
        match self._provider:
            case CloudProvider.AWS:
                return AWS_COMMON
            case CloudProvider.AZURE:
                return AZURE_COMMON_REGIONS
            case CloudProvider.GCP:
                return GCP_COMMON_REGIONS
            case _:
                return frozenset()

    def set_regions(self, regions: list[str], *, default_region: str | None = None) -> None:
        self._all_regions = sorted(regions)
        if default_region:
            self._default_region = default_region
        self._list.blockSignals(True)
        self._list.clear()
        for region in self._all_regions:
            item = QListWidgetItem(self._display_name(region))
            item.setData(Qt.ItemDataRole.UserRole, region)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = region == self._default_region
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
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
        common = self._common_set()
        self._set_checks(lambda region: region in common)

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
        self._summary.setText("Connect to load regions")
        self.setEnabled(False)
