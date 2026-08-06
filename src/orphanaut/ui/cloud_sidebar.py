"""Unified multi-cloud connection sidebar."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from orphanaut.auth.aws import list_sso_profiles
from orphanaut.models import AuthConfig, AuthMethod, CloudProvider
from orphanaut.ui.provider_selector import ProviderSelector
from orphanaut.ui.region_panel import RegionPanel


class CloudSidebar(QWidget):
    connect_requested = Signal(AuthConfig)
    connection_changed = Signal(bool)
    provider_changed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._connected = False
        self._editing_credentials = False
        self._provider = CloudProvider.AWS
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(10)

        title = QLabel("Cloud connection")
        title.setObjectName("title")
        subtitle = QLabel("Pick a provider, connect, then choose regions")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        outer.addWidget(title)
        outer.addWidget(subtitle)

        self._provider_selector = ProviderSelector()
        self._provider_selector.provider_changed.connect(self._on_provider_changed)
        outer.addWidget(self._provider_selector)

        self._status_card = self._build_status_card()
        outer.addWidget(self._status_card)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll, stretch=1)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 4, 0)
        content_layout.setSpacing(12)
        scroll.setWidget(content)

        self._auth_stack = QStackedWidget()
        self._auth_stack.addWidget(self._build_aws_auth())
        self._auth_stack.addWidget(self._build_azure_auth())
        self._auth_stack.addWidget(self._build_gcp_auth())
        content_layout.addWidget(self._auth_stack)

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setObjectName("primary")
        self._connect_btn.setMinimumHeight(42)
        self._connect_btn.clicked.connect(self._on_connect)
        content_layout.addWidget(self._connect_btn)

        self._region_panel = RegionPanel()
        content_layout.addWidget(self._region_panel)

        self._error_label = QLabel("")
        self._error_label.setObjectName("errorText")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        outer.addWidget(self._error_label)

    def _build_status_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("statusCard")
        row = QHBoxLayout(card)
        row.setContentsMargins(12, 10, 12, 10)
        self._status_dot = QLabel("●")
        self._status_dot.setObjectName("statusDot")
        self._status_dot.setProperty("connected", False)
        text = QVBoxLayout()
        self._status_title = QLabel("Not connected")
        self._status_title.setObjectName("statusTitle")
        self._status_detail = QLabel("Enter credentials and click Connect")
        self._status_detail.setObjectName("statusDetail")
        self._status_detail.setWordWrap(True)
        text.addWidget(self._status_title)
        text.addWidget(self._status_detail)
        row.addWidget(self._status_dot)
        row.addLayout(text, stretch=1)
        return card

    def _build_aws_auth(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        tip = QLabel(
            "Paste your <b>Access Key ID</b> and <b>Secret Access Key</b>. "
            "No AWS CLI required."
        )
        tip.setObjectName("infoBanner")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        tabs = QTabWidget()
        tabs.addTab(self._build_aws_keys_tab(), "Access Keys")
        tabs.addTab(self._build_aws_sso_tab(), "SSO")
        self._aws_tabs = tabs
        layout.addWidget(tabs)
        return widget

    def _build_aws_keys_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(8)

        self._access_key_input = QLineEdit()
        self._access_key_input.setPlaceholderText("AKIA...")
        self._secret_key_input = QLineEdit()
        self._secret_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._show_secret_cb = QCheckBox("Show")
        self._show_secret_cb.toggled.connect(
            lambda show: self._secret_key_input.setEchoMode(
                QLineEdit.EchoMode.Normal if show else QLineEdit.EchoMode.Password
            )
        )
        secret_row = QHBoxLayout()
        secret_row.addWidget(self._secret_key_input, stretch=1)
        secret_row.addWidget(self._show_secret_cb)
        self._session_token_input = QLineEdit()
        self._session_token_input.setPlaceholderText("Optional session token")

        form.addRow("Access Key ID", self._access_key_input)
        form.addRow("Secret Key", secret_row)
        form.addRow("Session Token", self._session_token_input)
        return widget

    def _build_aws_sso_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        self._sso_profile_combo = QComboBox()
        self._sso_profile_combo.setEditable(True)
        refresh = QPushButton("Refresh profiles")
        refresh.clicked.connect(self._refresh_sso_profiles)
        layout.addWidget(QLabel("SSO profile name"))
        layout.addWidget(self._sso_profile_combo)
        layout.addWidget(refresh)
        self._refresh_sso_profiles()
        layout.addStretch()
        return widget

    def _build_azure_auth(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        form.setContentsMargins(8, 8, 8, 8)
        form.setSpacing(8)

        tip = QLabel(
            "Use an Azure <b>App Registration</b> (service principal) with "
            "Contributor on your subscription."
        )
        tip.setObjectName("infoBanner")
        tip.setWordWrap(True)
        form.addRow(tip)

        self._azure_tenant = QLineEdit()
        self._azure_client_id = QLineEdit()
        self._azure_client_secret = QLineEdit()
        self._azure_client_secret.setEchoMode(QLineEdit.EchoMode.Password)
        self._azure_subscription = QLineEdit()

        self._azure_tenant.setPlaceholderText("xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
        self._azure_client_id.setPlaceholderText("Application (client) ID")
        self._azure_client_secret.setPlaceholderText("Client secret value")
        self._azure_subscription.setPlaceholderText("Subscription ID")

        form.addRow("Tenant ID", self._azure_tenant)
        form.addRow("Client ID", self._azure_client_id)
        form.addRow("Client Secret", self._azure_client_secret)
        form.addRow("Subscription ID", self._azure_subscription)
        return widget

    def _build_gcp_auth(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        tip = QLabel(
            "Paste a GCP <b>service account JSON key</b> with Viewer + "
            "resource deletion permissions on your project."
        )
        tip.setObjectName("infoBanner")
        tip.setWordWrap(True)
        layout.addWidget(tip)

        self._gcp_project = QLineEdit()
        self._gcp_project.setPlaceholderText("my-lab-project-123")
        layout.addWidget(QLabel("Project ID"))
        layout.addWidget(self._gcp_project)

        self._gcp_key_input = QPlainTextEdit()
        self._gcp_key_input.setPlaceholderText('{"type": "service_account", ...}')
        self._gcp_key_input.setMaximumHeight(140)
        layout.addWidget(QLabel("Service account JSON"))
        layout.addWidget(self._gcp_key_input)

        browse = QPushButton("Load JSON file…")
        browse.clicked.connect(self._load_gcp_key_file)
        layout.addWidget(browse)
        return widget

    def region_panel(self) -> RegionPanel:
        return self._region_panel

    def provider(self) -> CloudProvider:
        return self._provider

    def _on_provider_changed(self, provider: CloudProvider) -> None:
        if self._connected and provider != self._provider:
            self._reset_connection()
        self._provider = provider
        self._auth_stack.setCurrentIndex(
            {CloudProvider.AWS: 0, CloudProvider.AZURE: 1, CloudProvider.GCP: 2}[provider]
        )
        self._connect_btn.setText(f"Connect to {provider.label}")
        self._region_panel.set_provider(provider)
        self.provider_changed.emit(provider)

    def _reset_connection(self) -> None:
        self._connected = False
        self._status_dot.setProperty("connected", False)
        self._status_dot.style().unpolish(self._status_dot)
        self._status_dot.style().polish(self._status_dot)
        self._status_title.setText("Not connected")
        self._status_detail.setText("Switching provider — connect again")
        self._region_panel.clear()
        self.connection_changed.emit(False)

    def _refresh_sso_profiles(self) -> None:
        current = self._sso_profile_combo.currentText()
        self._sso_profile_combo.clear()
        profiles = list_sso_profiles()
        if profiles:
            self._sso_profile_combo.addItems(profiles)
        if current:
            self._sso_profile_combo.setCurrentText(current)

    def _load_gcp_key_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open service account JSON", "", "JSON (*.json)"
        )
        if path:
            self._gcp_key_input.setPlainText(Path(path).read_text(encoding="utf-8"))

    def _build_config(self) -> AuthConfig:
        match self._provider:
            case CloudProvider.AWS:
                if self._aws_tabs.currentIndex() == 0:
                    return AuthConfig(
                        provider=CloudProvider.AWS,
                        method=AuthMethod.ACCESS_KEYS,
                        access_key_id=self._access_key_input.text(),
                        secret_access_key=self._secret_key_input.text(),
                        session_token=self._session_token_input.text(),
                    )
                return AuthConfig(
                    provider=CloudProvider.AWS,
                    method=AuthMethod.SSO_PROFILE,
                    profile_name=self._sso_profile_combo.currentText(),
                )
            case CloudProvider.AZURE:
                return AuthConfig(
                    provider=CloudProvider.AZURE,
                    method=AuthMethod.SERVICE_PRINCIPAL,
                    tenant_id=self._azure_tenant.text(),
                    client_id=self._azure_client_id.text(),
                    client_secret=self._azure_client_secret.text(),
                    subscription_id=self._azure_subscription.text(),
                )
            case CloudProvider.GCP:
                return AuthConfig(
                    provider=CloudProvider.GCP,
                    method=AuthMethod.SERVICE_ACCOUNT,
                    project_id=self._gcp_project.text(),
                    service_account_json=self._gcp_key_input.toPlainText(),
                )
            case _:
                return AuthConfig(provider=self._provider)

    def _on_connect(self) -> None:
        self._error_label.setVisible(False)
        self.connect_requested.emit(self._build_config())

    def set_connecting(self) -> None:
        self._status_title.setText("Connecting...")
        self._status_detail.setText(f"Verifying {self._provider.label} credentials")
        self._connect_btn.setEnabled(False)

    def set_connect_enabled(self, enabled: bool) -> None:
        self._connect_btn.setEnabled(enabled)

    def set_connected(self, provider: CloudProvider, account_id: str, label: str) -> None:
        self._connected = True
        self._provider = provider
        self._provider_selector.set_provider(provider)
        self._status_dot.setProperty("connected", True)
        self._status_dot.style().unpolish(self._status_dot)
        self._status_dot.style().polish(self._status_dot)
        self._status_title.setText(f"Connected to {provider.label}")
        self._status_detail.setText(f"{account_id}\n{label}")
        self._connect_btn.setText(f"Reconnect to {provider.label}")
        self._error_label.setVisible(False)
        self.connection_changed.emit(True)

    def set_error(self, message: str) -> None:
        self._connected = False
        self._status_dot.setProperty("connected", False)
        self._status_dot.style().unpolish(self._status_dot)
        self._status_dot.style().polish(self._status_dot)
        self._status_title.setText("Connection failed")
        self._status_detail.setText("Check credentials and try again")
        self._error_label.setText(message)
        self._error_label.setVisible(True)
        self.connection_changed.emit(False)

    def set_scan_complete(self) -> None:
        pass
