"""Orphanaut visual theme — one light theme that looks the same on Windows and macOS."""

from __future__ import annotations

import tempfile
from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPalette, QPen, QPixmap
from PySide6.QtWidgets import QApplication

from orphanaut.models import CloudProvider

COLORS = {
    "bg": "#F3F5FB",
    "surface": "#FFFFFF",
    "surface_alt": "#F8FAFD",
    "border": "#E2E7F0",
    "border_strong": "#CBD3E1",
    "text": "#0F172A",
    "muted": "#5B6B82",
    "faint": "#94A3B8",
    "primary": "#5B4BDB",
    "primary_hover": "#4A3BC4",
    "primary_soft": "#EEEBFF",
    "header_from": "#16123A",
    "header_to": "#3A2E8F",
    "danger": "#D92D20",
    "danger_hover": "#B42318",
    "danger_soft": "#FEF3F2",
    "warning": "#B54708",
    "warning_soft": "#FFFAEB",
    "success": "#067647",
    "success_soft": "#ECFDF3",
    "info_soft": "#EFF6FF",
}

# Accent colour per cloud, used on the cloud tabs and connect panel.
PROVIDER_COLORS = {
    CloudProvider.AWS: "#FF9900",
    CloudProvider.AZURE: "#0078D4",
    CloudProvider.GCP: "#1A73E8",
}

# Colour per delete-impact action (dependencies.Action values).
ACTION_COLORS = {
    "delete": COLORS["danger"],
    "stop": COLORS["warning"],
    "keep": COLORS["success"],
}

_QSS = """
* { outline: none; }
QWidget { color: @text; font-size: 13px; }
QMainWindow, QWidget#root { background: @bg; }
QToolTip { background: @text; color: white; border: none; padding: 6px 8px; border-radius: 6px; }

/* ---------- Header ---------- */
QFrame#header {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 @header_from, stop:1 @header_to);
    border: none;
}
QLabel#appTitle { color: white; font-size: 22px; font-weight: 800; }
QLabel#appTagline { color: #C9C3FF; font-size: 13px; }
QLabel#privacyBadge {
    color: #E7E4FF; background: rgba(255,255,255,0.10); border: 1px solid rgba(255,255,255,0.18);
    border-radius: 13px; padding: 4px 12px; font-size: 12px;
}
QPushButton#headerButton {
    color: white; background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.25);
    border-radius: 8px; padding: 7px 14px; font-weight: 600;
}
QPushButton#headerButton:hover { background: rgba(255,255,255,0.22); }

/* ---------- Update banner ---------- */
QFrame#updateBanner { background: @success_soft; border-bottom: 1px solid #ABEFC6; }
QLabel#updateText { color: @success; font-size: 13px; }

/* ---------- Cloud tabs ---------- */
QFrame#cloudBar { background: @surface; border-bottom: 1px solid @border; }
QPushButton#cloudTab {
    background: transparent; border: none; border-bottom: 3px solid transparent;
    padding: 12px 22px 10px 22px; font-size: 15px; font-weight: 600; color: @muted;
    text-align: left;
}
QPushButton#cloudTab:hover { color: @text; background: @surface_alt; }
QPushButton#cloudTab:checked { color: @text; }

/* ---------- Cards & text ---------- */
QFrame#card, QFrame#welcomeCard {
    background: @surface; border: 1px solid @border; border-radius: 14px;
}
QFrame#sidePanel { background: @surface; border: 1px solid @border; border-radius: 14px; }
QLabel#title { font-size: 18px; font-weight: 800; }
QLabel#subtitle { color: @muted; }
QLabel#muted { color: @muted; font-size: 12px; }
QLabel#sectionHeader {
    font-size: 11px; font-weight: 800; color: @muted;
    padding-top: 6px;
}
QLabel#fieldLabel { font-weight: 600; font-size: 12px; color: @text; padding-top: 4px; }
QLabel#welcomeTitle { font-size: 22px; font-weight: 800; }
QLabel#welcomeBody { color: @muted; font-size: 14px; }
QLabel#infoBanner {
    background: @info_soft; border: 1px solid #D1E3FF; border-radius: 10px; padding: 9px 11px;
    color: #1E3A8A;
}
QLabel#warningBanner {
    background: @warning_soft; border: 1px solid #FEDF89; border-radius: 10px; padding: 9px 11px;
    color: @warning;
}
QLabel#scanBanner {
    background: @primary_soft; border: 1px solid #D9D3FF; border-radius: 10px; padding: 9px 11px;
    color: @primary_hover; font-weight: 600;
}
QLabel#errorText {
    background: @danger_soft; border: 1px solid #FECDCA; border-radius: 10px; padding: 9px 11px;
    color: @danger;
}
QLabel#detectedBadge {
    background: @success_soft; color: @success; border: 1px solid #ABEFC6; border-radius: 10px;
    padding: 2px 8px; font-size: 11px; font-weight: 700;
}
QLabel#deviceCode {
    font-family: "Consolas", "Menlo", monospace; font-size: 26px; font-weight: 800;
    color: @primary; background: @primary_soft; border-radius: 10px;
    padding: 10px;
}
QLabel#guide { font-size: 13px; color: @text; }
QLabel#watermark { color: @muted; font-size: 12px; }
QFrame#footer { background: transparent; }

/* Status card */
QFrame#statusCard { background: @surface_alt; border: 1px solid @border; border-radius: 12px; }
QFrame#statusCard[state="connected"] { background: @success_soft; border-color: #ABEFC6; }
QFrame#statusCard[state="error"] { background: @danger_soft; border-color: #FECDCA; }
QLabel#statusTitle { font-weight: 800; font-size: 14px; }
QLabel#statusDetail { color: @muted; font-size: 12px; }

/* Method cards */
QPushButton#methodCard {
    background: @surface; border: 1px solid @border; border-radius: 12px; padding: 10px 12px;
    text-align: left; font-size: 13px;
}
QPushButton#methodCard:hover { border-color: @border_strong; background: @surface_alt; }
QPushButton#methodCard:checked { border: 2px solid @primary; background: @primary_soft; }

/* ---------- Inputs ---------- */
QLineEdit, QPlainTextEdit, QComboBox {
    background: @surface; border: 1px solid @border_strong; border-radius: 8px; padding: 7px 9px;
    selection-background-color: @primary;
}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 2px solid @primary; padding: 6px 8px;
}
QLineEdit#search { padding-left: 10px; min-width: 240px; }
QComboBox::drop-down { border: none; width: 22px; }
QComboBox QAbstractItemView {
    background: @surface; border: 1px solid @border; selection-background-color: @primary_soft;
    selection-color: @text;
}

/* ---------- Buttons ---------- */
QPushButton {
    background: @surface; border: 1px solid @border_strong; border-radius: 8px; padding: 8px 14px;
    font-weight: 600;
}
QPushButton:hover { background: @surface_alt; border-color: @faint; }
QPushButton:disabled { color: @faint; background: @surface_alt; border-color: @border; }
QPushButton#primary { background: @primary; color: white; border: none; padding: 10px 16px; }
QPushButton#primary:hover { background: @primary_hover; }
QPushButton#primary:disabled { background: #C9C3F5; color: white; }
QPushButton#danger { background: @danger; color: white; border: none; padding: 10px 16px; }
QPushButton#danger:hover { background: @danger_hover; }
QPushButton#danger:disabled { background: #F4C7C3; color: white; }
QPushButton#link {
    background: transparent; border: none; color: @primary; padding: 2px; text-align: left;
}
QPushButton#link:hover { text-decoration: underline; }
QToolButton#helpToggle { border: none; color: @primary; font-weight: 600; padding: 2px; }

/* ---------- Category tabs ---------- */
QTabBar#categoryTabs::tab {
    background: transparent; border: 1px solid transparent; border-radius: 15px;
    padding: 6px 14px; margin-right: 4px; color: @muted; font-weight: 600;
}
QTabBar#categoryTabs::tab:hover { background: @surface; border-color: @border; color: @text; }
QTabBar#categoryTabs::tab:selected { background: @text; color: white; }

QTabWidget::pane {
    border: 1px solid @border; border-radius: 10px; background: @surface; top: -1px;
}
QTabBar::tab {
    background: @surface_alt; border: 1px solid @border; padding: 7px 14px;
    border-top-left-radius: 8px; border-top-right-radius: 8px; margin-right: 2px; color: @muted;
}
QTabBar::tab:selected { background: @surface; color: @text; font-weight: 700; }

/* ---------- Table & tree ---------- */
QTableWidget, QTreeWidget, QListWidget {
    background: @surface; alternate-background-color: @surface_alt; border: 1px solid @border;
    border-radius: 12px; gridline-color: transparent; selection-background-color: @primary_soft;
    selection-color: @text;
}
QTableWidget::item, QTreeWidget::item { padding: 6px 6px; border: none; }
QListWidget::item { padding: 5px 6px; }
QListWidget::item:selected { background: @primary_soft; color: @text; }
QHeaderView::section {
    background: @surface_alt; color: @muted; border: none; border-bottom: 1px solid @border;
    padding: 8px 6px; font-weight: 700; font-size: 12px;
}
QTreeWidget#impactTree { border-radius: 10px; }

/* ---------- Progress & scrollbars ---------- */
QProgressBar {
    background: @border; border: none; border-radius: 5px; height: 10px; text-align: center;
    color: transparent;
}
QProgressBar::chunk { background: @primary; border-radius: 5px; }
QScrollArea { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 2px; }
QScrollBar::handle:vertical { background: @border_strong; border-radius: 4px; min-height: 30px; }
QScrollBar:horizontal { background: transparent; height: 10px; margin: 2px; }
QScrollBar::handle:horizontal { background: @border_strong; border-radius: 4px; min-width: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }
QSplitter::handle { background: transparent; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator, QListWidget::indicator {
    width: 15px; height: 15px; border: 1px solid @border_strong; border-radius: 4px;
    background: @surface;
}
QCheckBox::indicator:checked, QListWidget::indicator:checked {
    background: @primary; border-color: @primary;
}
QStatusBar { background: @surface; border-top: 1px solid @border; color: @muted; }
"""


def build_stylesheet() -> str:
    qss = _QSS
    # Longest names first so "@primary_hover" isn't eaten by "@primary".
    for key in sorted(COLORS, key=len, reverse=True):
        qss = qss.replace(f"@{key}", COLORS[key])
    return qss


STYLESHEET = build_stylesheet()


def _check_mark_qss() -> str:
    """Draw a white tick for checked boxes (QSS needs an image file for it)."""
    try:
        path = Path(tempfile.gettempdir()) / "orphanaut-check.png"
        pixmap = QPixmap(30, 30)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor("#FFFFFF"), 4.5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.drawPolyline([QPointF(7, 15.5), QPointF(12.5, 21), QPointF(23, 9)])
        painter.end()
        pixmap.save(str(path))
        url = path.as_posix()
        return (
            "QCheckBox::indicator:checked, QListWidget::indicator:checked "
            f'{{ image: url("{url}"); }}'
        )
    except Exception:
        return ""


def apply_theme(app: QApplication) -> None:
    """Fusion + our palette + stylesheet, so Windows and macOS render identically."""
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(COLORS["bg"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(COLORS["surface"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLORS["surface_alt"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(COLORS["surface"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(COLORS["primary"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(COLORS["faint"]))
    palette.setColor(QPalette.ColorRole.Link, QColor(COLORS["primary"]))
    app.setPalette(palette)
    font = QFont(app.font())
    font.setPointSizeF(max(font.pointSizeF(), 9.5))
    app.setFont(font)
    app.setStyleSheet(STYLESHEET + _check_mark_qss())
