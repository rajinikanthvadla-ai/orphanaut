"""Delete impact map: shows associated resources affected by deleting a selection."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHeaderView,
    QLabel,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from orphanaut.dependencies import Action, ImpactNode, impact_counts, impact_tree
from orphanaut.models import CloudResource
from orphanaut.providers.pricing import estimate_monthly_cost
from orphanaut.ui.styles import ACTION_COLORS


def _summary_html(resources: list[CloudResource]) -> str:
    counts = impact_counts(resources)
    parts = []
    for action, word in ((Action.DELETE, "deleted"), (Action.STOP, "stopped"),
                         (Action.KEEP, "kept")):
        if counts[action]:
            parts.append(
                f"<span style='color:{ACTION_COLORS[action.value]}'><b>{counts[action]}</b> "
                f"{word}</span>"
            )
    savings = sum(estimate_monthly_cost(r) or 0.0 for r in resources)
    text = " · ".join(parts)
    if savings:
        text += f"<br><span style='color:#067647'>Saves ≈ <b>${savings:,.2f}</b>/month</span>"
    return text


class ImpactTree(QTreeWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("impactTree")
        self.setColumnCount(2)
        self.setHeaderLabels(["Item", "What happens"])
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.header().setStretchLastSection(False)
        self.setRootIsDecorated(True)
        self.setUniformRowHeights(False)
        self.setWordWrap(True)

    def show_resources(self, resources: list[CloudResource]) -> None:
        self.clear()
        for resource in resources:
            self.addTopLevelItem(self._item(impact_tree(resource), top=True))
        self.expandAll()

    def _item(self, node: ImpactNode, top: bool = False) -> QTreeWidgetItem:
        item = QTreeWidgetItem([f"{node.kind}: {node.name}", node.action.label])
        tooltip = f"{node.kind}: {node.name}" + (f"\n{node.note}" if node.note else "")
        item.setToolTip(0, tooltip)
        item.setToolTip(1, node.note or node.action.label)
        color = QColor(ACTION_COLORS[node.action.value])
        item.setForeground(1, QBrush(color))
        bold = QFont()
        bold.setBold(True)
        item.setFont(1, bold)
        if top:
            item.setFont(0, bold)
        if node.note:
            note = QTreeWidgetItem([f"↳ {node.note}", ""])
            note.setForeground(0, QBrush(QColor("#5B6B82")))
            note.setFlags(Qt.ItemFlag.ItemIsEnabled)
            item.addChild(note)
        for child in node.children:
            item.addChild(self._item(child))
        return item


class ImpactPanel(QFrame):
    """Side panel next to the results table."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(8)
        title = QLabel("Delete impact map")
        title.setObjectName("title")
        hint = QLabel("Everything that is deleted, stopped or kept with your selection.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        self._summary = QLabel("")
        self._summary.setWordWrap(True)
        self._summary.setTextFormat(Qt.TextFormat.RichText)
        self._empty = QLabel(
            "Select one or more rows to see what else goes with them — for example, "
            "deleting a SageMaker domain also removes its user profiles, spaces, apps and "
            "home EFS volume."
        )
        self._empty.setObjectName("infoBanner")
        self._empty.setWordWrap(True)
        self._tree = ImpactTree()
        legend = QLabel(
            f"<span style='color:{ACTION_COLORS['delete']}'>■ Deleted</span> &nbsp; "
            f"<span style='color:{ACTION_COLORS['stop']}'>■ Stopped</span> &nbsp; "
            f"<span style='color:{ACTION_COLORS['keep']}'>■ Kept — review</span>"
        )
        legend.setObjectName("muted")
        layout.addWidget(title)
        layout.addWidget(hint)
        layout.addWidget(self._summary)
        layout.addWidget(self._empty)
        layout.addWidget(self._tree, stretch=1)
        layout.addWidget(legend)
        self.show_resources([])

    def show_resources(self, resources: list[CloudResource]) -> None:
        has = bool(resources)
        self._empty.setVisible(not has)
        self._tree.setVisible(has)
        self._summary.setVisible(has)
        if has:
            self._summary.setText(_summary_html(resources))
            self._tree.show_resources(resources)


class DeleteConfirmDialog(QDialog):
    """Final confirmation listing every associated item, with an explicit checkbox."""

    def __init__(self, resources: list[CloudResource], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirm deletion")
        self.resize(640, 560)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        counts = impact_counts(resources)
        heading = QLabel(
            f"Delete {len(resources)} selected resource(s)?"
            if counts[Action.STOP] < len(resources)
            else f"Stop {len(resources)} selected job(s)/model(s)?"
        )
        heading.setObjectName("title")
        intro = QLabel(
            "This is the full map of what will happen, including associated resources. "
            "Deleted items cannot be recovered."
        )
        intro.setWordWrap(True)
        intro.setObjectName("subtitle")
        summary = QLabel(_summary_html(resources))
        summary.setTextFormat(Qt.TextFormat.RichText)
        tree = ImpactTree()
        tree.show_resources(resources)
        self._check = QCheckBox("I understand this permanently deletes the items marked Deleted")
        buttons = QDialogButtonBox()
        self._ok = buttons.addButton("Delete now", QDialogButtonBox.ButtonRole.AcceptRole)
        self._ok.setObjectName("danger")
        self._ok.setEnabled(False)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self._check.toggled.connect(self._ok.setEnabled)
        for widget in (heading, intro, summary):
            layout.addWidget(widget)
        layout.addWidget(tree, stretch=1)
        layout.addWidget(self._check)
        layout.addWidget(buttons)
