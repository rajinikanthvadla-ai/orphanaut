"""Icons drawn in code, so the app needs no image files at runtime."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QIcon, QLinearGradient, QPainter, QPen, QPixmap

from orphanaut.models import CloudProvider
from orphanaut.ui.logos import render_logo
from orphanaut.ui.styles import COLORS


def app_pixmap(size: int = 256) -> QPixmap:
    """The Orphanaut mark: an indigo tile with a magnifier ring and a spark."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0, QColor(COLORS["header_to"]))
    gradient.setColorAt(1, QColor(COLORS["header_from"]))
    p.setBrush(QBrush(gradient))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(0, 0, size, size), size * 0.22, size * 0.22)
    ring = QPen(QColor("#FFFFFF"), size * 0.085)
    ring.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(ring)
    p.setBrush(Qt.BrushStyle.NoBrush)
    r = size * 0.24
    cx, cy = size * 0.44, size * 0.44
    p.drawEllipse(QRectF(cx - r, cy - r, 2 * r, 2 * r))
    p.drawLine(int(cx + r * 0.72), int(cy + r * 0.72), int(size * 0.76), int(size * 0.76))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#FFB020"))
    s = size * 0.075
    p.drawEllipse(QRectF(cx - s, cy - s, 2 * s, 2 * s))
    p.end()
    return pixmap


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(app_pixmap(size))
    return icon


def cloud_icon(provider: CloudProvider, connected: bool, size: int = 40) -> QIcon:
    """Provider logo with a small green (connected) or grey status dot."""
    pixmap = render_logo(provider, size, size)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    dot = size * 0.3
    p.setBrush(QColor(COLORS["success"] if connected else "#C3CAD6"))
    p.setPen(QPen(QColor("#FFFFFF"), size * 0.06))
    p.drawEllipse(QRectF(size - dot - 1, size - dot - 1, dot, dot))
    p.end()
    return QIcon(pixmap)
