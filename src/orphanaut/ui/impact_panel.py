"""Side panel and confirm dialog that show what a delete will touch."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from orphanaut.dependencies import Action, impact_counts
from orphanaut.models import CloudResource
from orphanaut.providers.pricing import estimate_monthly_cost
from orphanaut.ui.impact_graph import ImpactGraph
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
    text = " &nbsp;·&nbsp; ".join(parts)
    savings = sum(estimate_monthly_cost(r) or 0.0 for r in resources)
    if savings:
        text += f" &nbsp;·&nbsp; saves about <b>${savings:,.0f}/mo</b>"
    return text


def _legend() -> QLabel:
    label = QLabel(
        f"<span style='color:{ACTION_COLORS['delete']}'>■</span> deleted &nbsp; "
        f"<span style='color:{ACTION_COLORS['stop']}'>■</span> stopped &nbsp; "
        f"<span style='color:{ACTION_COLORS['keep']}'>■</span> kept"
    )
    label.setObjectName("muted")
    return label


class ImpactPanel(QFrame):
    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("card")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(8)
        header = QHBoxLayout()
        title = QLabel("Resource map")
        title.setObjectName("title")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(_legend())
        self._summary = QLabel("")
        self._summary.setTextFormat(Qt.TextFormat.RichText)
        self._empty = QLabel("Tick a resource to see what it's connected to.")
        self._empty.setObjectName("muted")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._graph = ImpactGraph()
        layout.addLayout(header)
        layout.addWidget(self._summary)
        layout.addWidget(self._empty, stretch=1)
        layout.addWidget(self._graph, stretch=1)
        self.show_resources([])

    def show_resources(self, resources: list[CloudResource]) -> None:
        has = bool(resources)
        self._empty.setVisible(not has)
        self._graph.setVisible(has)
        self._summary.setVisible(has)
        if has:
            self._summary.setText(_summary_html(resources))
            self._graph.show_resources(resources)


class DeleteConfirmDialog(QDialog):
    def __init__(self, resources: list[CloudResource], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Confirm delete")
        self.resize(820, 560)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        only_stop = all(impact_counts([r])[Action.STOP] for r in resources)
        heading = QLabel(
            f"Stop {len(resources)} item(s)?" if only_stop
            else f"Delete {len(resources)} resource(s)?"
        )
        heading.setObjectName("title")
        summary = QLabel(_summary_html(resources))
        summary.setTextFormat(Qt.TextFormat.RichText)
        graph = ImpactGraph()
        graph.show_resources(resources)
        self._check = QCheckBox("I understand deleted items can't be recovered")
        buttons = QDialogButtonBox()
        ok = buttons.addButton("Delete", QDialogButtonBox.ButtonRole.AcceptRole)
        ok.setObjectName("danger")
        ok.setEnabled(False)
        buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self._check.toggled.connect(ok.setEnabled)
        row = QHBoxLayout()
        row.addWidget(summary)
        row.addStretch()
        row.addWidget(_legend())
        layout.addWidget(heading)
        layout.addLayout(row)
        layout.addWidget(graph, stretch=1)
        layout.addWidget(self._check)
        layout.addWidget(buttons)
