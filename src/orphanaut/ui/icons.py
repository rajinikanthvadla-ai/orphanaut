"""Icons drawn in code, so the app needs no image files at runtime."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QIcon, QLinearGradient, QPainter, QPen, QPixmap

from orphanaut.models import CloudProvider
from orphanaut.ui.styles import COLORS, PROVIDER_COLORS

_LETTERS = {CloudProvider.AWS: "aws", CloudProvider.AZURE: "Az", CloudProvider.GCP: "G"}


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
    """Provider-coloured tile with its initials and a status dot."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(PROVIDER_COLORS[provider])
    if provider == CloudProvider.AWS:
        color = QColor("#232F3E")
    p.setBrush(color)
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRoundedRect(QRectF(0, 0, size * 0.86, size * 0.86), size * 0.2, size * 0.2)
    font = QFont()
    font.setBold(True)
    font.setPixelSize(int(size * (0.30 if provider == CloudProvider.AWS else 0.38)))
    p.setFont(font)
    p.setPen(QColor("#FF9900") if provider == CloudProvider.AWS else QColor("#FFFFFF"))
    p.drawText(QRectF(0, 0, size * 0.86, size * 0.86), Qt.AlignmentFlag.AlignCenter,
               _LETTERS[provider])
    dot = size * 0.34
    p.setBrush(QColor(COLORS["success"] if connected else "#B9C2D0"))
    p.setPen(QPen(QColor("#FFFFFF"), size * 0.06))
    p.drawEllipse(QRectF(size - dot, size - dot, dot - 1, dot - 1))
    p.end()
    return QIcon(pixmap)
