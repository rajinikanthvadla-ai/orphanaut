"""Main application window: header, cloud tabs, one workspace per cloud, and footer."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from orphanaut import __version__
from orphanaut.models import CloudProvider
from orphanaut.ui.guide import GuideDialog
from orphanaut.ui.icons import app_icon, cloud_icon
from orphanaut.ui.styles import PROVIDER_COLORS
from orphanaut.ui.update_banner import UpdateBanner
from orphanaut.ui.workspace import CloudWorkspace

_TAB_LABELS = {
    CloudProvider.AWS: "AWS",
    CloudProvider.AZURE: "Azure",
    CloudProvider.GCP: "Google Cloud",
}


class MainWindow(QMainWindow):
    def __init__(self, check_updates: bool = True) -> None:
        super().__init__()
        self.setWindowTitle("Orphanaut — find & clean up forgotten cloud and AI resources")
        self.setWindowIcon(app_icon())
        self.setMinimumSize(1180, 740)
        self.resize(1440, 900)
        self._workspaces: dict[CloudProvider, CloudWorkspace] = {}
        self._tab_buttons: dict[CloudProvider, QPushButton] = {}
        self._build_ui()
        QShortcut(QKeySequence("F1"), self, activated=self._open_guide)
        if check_updates:
            # Quietly ask GitHub for a newer release shortly after the window appears.
            QTimer.singleShot(2500, self._update_banner.check)

    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("root")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())
        root.addWidget(self._build_cloud_bar())
        self._update_banner = UpdateBanner()
        root.addWidget(self._update_banner)

        self._stack = QStackedWidget()
        for provider in CloudProvider:
            workspace = CloudWorkspace(provider)
            workspace.state_changed.connect(self._on_state_changed)
            workspace.status_message.connect(
                lambda msg, p=provider: self._show_status(p, msg)
            )
            self._workspaces[provider] = workspace
            self._stack.addWidget(workspace)
        root.addWidget(self._stack, stretch=1)
        root.addWidget(self._build_footer())

        status = QStatusBar()
        self.setStatusBar(status)
        status.showMessage("Pick a cloud above, then connect on the left. Press F1 for the guide.")
        self._select(CloudProvider.AWS)

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("header")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(22, 14, 22, 14)
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(QSize(40, 40)))
        brand = QVBoxLayout()
        brand.setSpacing(0)
        title = QLabel("Orphanaut")
        title.setObjectName("appTitle")
        tagline = QLabel("Find and clean up forgotten cloud & AI resources before they cost you")
        tagline.setObjectName("appTagline")
        brand.addWidget(title)
        brand.addWidget(tagline)
        privacy = QLabel("🔒 Keys never leave this computer")
        privacy.setObjectName("privacyBadge")
        guide = QPushButton("?  Guide")
        guide.setObjectName("headerButton")
        guide.setCursor(Qt.CursorShape.PointingHandCursor)
        guide.clicked.connect(self._open_guide)
        layout.addWidget(logo)
        layout.addSpacing(10)
        layout.addLayout(brand)
        layout.addStretch()
        updates = QPushButton("⟳  Check for updates")
        updates.setObjectName("headerButton")
        updates.setCursor(Qt.CursorShape.PointingHandCursor)
        updates.clicked.connect(lambda: self._update_banner.check(manual=True))
        layout.addWidget(privacy)
        layout.addSpacing(10)
        layout.addWidget(updates)
        layout.addWidget(guide)
        return header

    def _build_cloud_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("cloudBar")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(4)
        group = QButtonGroup(self)
        group.setExclusive(True)
        for provider in CloudProvider:
            button = QPushButton(f"  {_TAB_LABELS[provider]}")
            button.setObjectName("cloudTab")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setIconSize(QSize(26, 26))
            button.setIcon(cloud_icon(provider, False))
            button.setToolTip(f"{provider.long_label} — not connected")
            button.setStyleSheet(
                f"QPushButton#cloudTab:checked {{ border-bottom: 3px solid "
                f"{PROVIDER_COLORS[provider]}; }}"
            )
            button.clicked.connect(lambda _c=False, p=provider: self._select(p))
            group.addButton(button)
            self._tab_buttons[provider] = button
            layout.addWidget(button)
        layout.addStretch()
        hint = QLabel("Each cloud has its own connection, regions and results")
        hint.setObjectName("muted")
        layout.addWidget(hint)
        return bar

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("footer")
        layout = QHBoxLayout(footer)
        layout.setContentsMargins(22, 2, 22, 6)
        version = QLabel(f"v{__version__} · open source (MIT)")
        version.setObjectName("watermark")
        mark = QLabel("Made with <span style='color:#D92D20'>♥</span> by <b>Rajinikanth Vadla</b>")
        mark.setObjectName("watermark")
        mark.setAlignment(Qt.AlignmentFlag.AlignCenter)
        repo = QLabel(
            "<a style='color:#94A3B8; text-decoration:none' "
            "href='https://github.com/rajinikanthvadla-ai/orphanaut'>github.com/"
            "rajinikanthvadla-ai/orphanaut</a>"
        )
        repo.setObjectName("watermark")
        repo.setOpenExternalLinks(True)
        layout.addWidget(version, stretch=1)
        layout.addWidget(mark, stretch=1)
        layout.addWidget(repo, stretch=1, alignment=Qt.AlignmentFlag.AlignRight)
        return footer

    def _select(self, provider: CloudProvider) -> None:
        self._tab_buttons[provider].setChecked(True)
        self._stack.setCurrentWidget(self._workspaces[provider])
        self._current = provider

    def _on_state_changed(self, provider: CloudProvider, connected: bool) -> None:
        button = self._tab_buttons[provider]
        button.setIcon(cloud_icon(provider, connected))
        button.setToolTip(
            f"{provider.long_label} — {'connected' if connected else 'not connected'}"
        )

    def _show_status(self, provider: CloudProvider, message: str) -> None:
        if provider == getattr(self, "_current", provider):
            self.statusBar().showMessage(message)

    def _open_guide(self) -> None:
        GuideDialog(self, getattr(self, "_current", None)).exec()

    def workspace(self, provider: CloudProvider) -> CloudWorkspace:
        return self._workspaces[provider]

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt API
        self._update_banner.shutdown()
        for workspace in self._workspaces.values():
            workspace.shutdown()
        super().closeEvent(event)
