"""Connected map of a resource and everything attached to it, drawn left to right."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QGraphicsItem,
    QGraphicsPathItem,
    QGraphicsScene,
    QGraphicsView,
    QStyleOptionGraphicsItem,
    QWidget,
)

from orphanaut.dependencies import Action, ImpactNode, impact_tree
from orphanaut.models import CloudResource
from orphanaut.ui.styles import ACTION_COLORS, COLORS

NODE_W, NODE_H = 168, 50
COL_GAP, ROW_GAP = 30, 10
MAX_NODES = 250
_ACTION_TEXT = {Action.DELETE: "deleted", Action.STOP: "stopped", Action.KEEP: "kept"}


class NodeItem(QGraphicsItem):
    def __init__(self, node: ImpactNode, root: bool) -> None:
        super().__init__()
        self.node = node
        self.root = root
        tip = f"{node.kind}\n{node.name}"
        if node.note:
            tip += f"\n\n{node.note}"
        self.setToolTip(tip)
        self.setAcceptHoverEvents(True)
        self._hover = False

    def boundingRect(self) -> QRectF:  # noqa: N802 - Qt API
        return QRectF(-1, -1, NODE_W + 2, NODE_H + 2)

    def hoverEnterEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._hover = True
        self.update()

    def hoverLeaveEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._hover = False
        self.update()

    def paint(self, p: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None):
        color = QColor(ACTION_COLORS[self.node.action.value])
        rect = QRectF(0, 0, NODE_W, NODE_H)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        border = QColor(COLORS["primary"]) if self.root else QColor(COLORS["border_strong"])
        if self._hover:
            border = QColor(COLORS["text"])
        p.setPen(QPen(border, 2 if self.root else 1))
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(rect, 9, 9)
        stripe = QPainterPath()
        stripe.addRoundedRect(QRectF(0, 0, 8, NODE_H), 4, 4)
        p.fillPath(stripe, color)

        small = QFont()
        small.setPixelSize(11)
        bold = QFont()
        bold.setPixelSize(13)
        bold.setBold(True)
        p.setFont(small)
        p.setPen(QColor(COLORS["muted"]))
        label = _ACTION_TEXT[self.node.action]
        pill_w = QFontMetrics(small).horizontalAdvance(label) + 12
        room = NODE_W - pill_w - 30
        kind = QFontMetrics(small).elidedText(self.node.kind, Qt.TextElideMode.ElideRight, room)
        p.drawText(QRectF(16, 6, room + 2, 16), Qt.AlignmentFlag.AlignLeft, kind)

        pill = QRectF(NODE_W - pill_w - 8, 6, pill_w, 15)
        p.setPen(Qt.PenStyle.NoPen)
        tint = QColor(color)
        tint.setAlpha(28)
        p.setBrush(tint)
        p.drawRoundedRect(pill, 7, 7)
        p.setPen(color)
        p.drawText(pill, Qt.AlignmentFlag.AlignCenter, label)

        p.setFont(bold)
        p.setPen(QColor(COLORS["text"]))
        name = QFontMetrics(bold).elidedText(self.node.name, Qt.TextElideMode.ElideMiddle,
                                             NODE_W - 26)
        p.drawText(QRectF(16, 26, NODE_W - 22, 20), Qt.AlignmentFlag.AlignLeft, name)


class ImpactGraph(QGraphicsView):
    def __init__(self) -> None:
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setFrameShape(QGraphicsView.Shape.NoFrame)
        self.setBackgroundBrush(QBrush(QColor(COLORS["surface_alt"])))
        self.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._count = 0

    def show_resources(self, resources: list[CloudResource]) -> None:
        scene = self.scene()
        scene.clear()
        self.resetTransform()
        self._count = 0
        y = 0.0
        for resource in resources:
            if self._count >= MAX_NODES:
                break
            y = self._place(impact_tree(resource), 0, y, root=True)[1] + ROW_GAP * 2
        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-12, -12, 12, 12))
        self._fit()

    def _place(self, node: ImpactNode, depth: int, top: float, root: bool = False):
        """Lay out a subtree; returns (this node's centre y, bottom y of the subtree)."""
        self._count += 1
        x = depth * (NODE_W + COL_GAP)
        child_centres = []
        bottom = top
        for child in node.children:
            if self._count >= MAX_NODES:
                break
            centre, bottom = self._place(child, depth + 1, bottom)
            child_centres.append(centre)
            bottom += ROW_GAP
        if child_centres:
            bottom -= ROW_GAP
            centre = (child_centres[0] + child_centres[-1]) / 2
            bottom = max(bottom, centre + NODE_H / 2)
        else:
            centre = top + NODE_H / 2
            bottom = top + NODE_H
        item = NodeItem(node, root)
        item.setPos(x, centre - NODE_H / 2)
        item.setZValue(1)
        self.scene().addItem(item)
        start = QPointF(x + NODE_W, centre)
        for child_centre in child_centres:
            end = QPointF(x + NODE_W + COL_GAP, child_centre)
            path = QPainterPath(start)
            mid = (start.x() + end.x()) / 2
            path.cubicTo(QPointF(mid, start.y()), QPointF(mid, end.y()), end)
            edge = QGraphicsPathItem(path)
            edge.setPen(QPen(QColor(COLORS["border_strong"]), 1.6))
            self.scene().addItem(edge)
        return centre, bottom

    def _fit(self) -> None:
        rect = self.sceneRect()
        if rect.isEmpty():
            return
        view = self.viewport().rect()
        # Shrink a little to fit, but never so much that the text becomes hard to read.
        scale = max(min(1.0, view.width() / rect.width()), 0.85)
        self.resetTransform()
        self.scale(scale, scale)

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._fit()

    def wheelEvent(self, event) -> None:  # noqa: N802 - Qt API
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self.scale(factor, factor)
        else:
            super().wheelEvent(event)
