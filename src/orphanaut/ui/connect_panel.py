"""Per-cloud sign-in panel: pick a method, connect, switch account, choose regions."""

from __future__ import annotations

import webbrowser
from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from orphanaut.auth.aws import (
    ENV_PROFILE,
    DeviceCode,
    list_local_profiles,
    list_sso_profiles,
    sso_settings_for_profile,
)
from orphanaut.auth.azure import detect_local_azure
from orphanaut.auth.gcp import GCLOUD_INSTALL_URL, detect_local_gcp, gcloud_path
from orphanaut.auth.router import ConnectResult
from orphanaut.aws.regions import COMMON_REGIONS
from orphanaut.models import AuthConfig, AuthMethod, CloudProvider
from orphanaut.ui.region_panel import RegionPanel
from orphanaut.ui.styles import PROVIDER_COLORS


@dataclass
class MethodInfo:
    method: AuthMethod
    title: str
    description: str
    button: str


METHODS: dict[CloudProvider, list[MethodInfo]] = {
    CloudProvider.AWS: [
        MethodInfo(AuthMethod.ACCESS_KEYS, "Access keys",
                   "Paste an Access Key ID and Secret Access Key", "Connect with keys"),
        MethodInfo(AuthMethod.BROWSER, "Sign in with browser",
                   "AWS IAM Identity Center (SSO) — no CLI needed", "Sign in with browser"),
        MethodInfo(AuthMethod.LOCAL, "This computer",
                   "Use a profile from aws configure / aws sso login", "Use this login"),
    ],
    CloudProvider.AZURE: [
        MethodInfo(AuthMethod.BROWSER, "Sign in with browser",
                   "Your Microsoft or university account", "Sign in with browser"),
        MethodInfo(AuthMethod.LOCAL, "This computer",
                   "Reuse az login / azd / Azure PowerShell", "Use this login"),
        MethodInfo(AuthMethod.SERVICE_PRINCIPAL, "Service principal",
                   "Tenant ID, Client ID and Client Secret", "Connect"),
    ],
    CloudProvider.GCP: [
        MethodInfo(AuthMethod.BROWSER, "Sign in with browser",
                   "Your Google account (uses the gcloud CLI)", "Sign in with browser"),
        MethodInfo(AuthMethod.LOCAL, "This computer",
                   "Reuse gcloud Application Default Credentials", "Use this login"),
        MethodInfo(AuthMethod.SERVICE_ACCOUNT, "Service account key",
                   "A JSON key file from IAM & Admin", "Connect"),
    ],
}


def _field(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("fieldLabel")
    label.setWordWrap(True)
    return label


def _section(text: str) -> QLabel:
    label = QLabel(text.upper())
    label.setObjectName("sectionHeader")
    return label


def _secret(placeholder: str) -> tuple[QLineEdit, QCheckBox]:
    edit = QLineEdit()
    edit.setPlaceholderText(placeholder)
    edit.setEchoMode(QLineEdit.EchoMode.Password)
    show = QCheckBox("Show")
    normal, hidden = QLineEdit.EchoMode.Normal, QLineEdit.EchoMode.Password
    show.toggled.connect(lambda on: edit.setEchoMode(normal if on else hidden))
    return edit, show


class MethodCard(QFrame):
    clicked = Signal()

    def __init__(self, info: MethodInfo) -> None:
        super().__init__()
        self.info = info
        self.setObjectName("methodCardFrame")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(2)
        top = QHBoxLayout()
        self._title = QLabel(info.title)
        self._title.setStyleSheet("font-weight: 700; font-size: 14px; background: transparent;")
        self._badge = QLabel("")
        self._badge.setObjectName("detectedBadge")
        self._badge.setVisible(False)
        top.addWidget(self._title)
        top.addStretch()
        top.addWidget(self._badge)
        desc = QLabel(info.description)
        desc.setObjectName("muted")
        desc.setWordWrap(True)
        desc.setStyleSheet("background: transparent;")
        layout.addLayout(top)
        layout.addWidget(desc)
        self.set_selected(False)

    def set_badge(self, text: str) -> None:
        self._badge.setText(text)
        self._badge.setVisible(bool(text))

    def set_selected(self, selected: bool) -> None:
        if selected:
            self.setStyleSheet(
                "QFrame#methodCardFrame { background: #EEEBFF; border: 2px solid #5B4BDB; "
                "border-radius: 12px; }"
            )
        else:
            self.setStyleSheet(
                "QFrame#methodCardFrame { background: #FFFFFF; border: 1px solid #E2E7F0; "
                "border-radius: 12px; } QFrame#methodCardFrame:hover { border-color: #CBD3E1; }"
            )

    def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.clicked.emit()
        super().mousePressEvent(event)


class ConnectPanel(QWidget):
    connect_requested = Signal(AuthConfig)
    cancel_requested = Signal()
    switch_requested = Signal(str)
    disconnect_requested = Signal()

    def __init__(self, provider: CloudProvider) -> None:
        super().__init__()
        self.provider = provider
        self._method = METHODS[provider][0].method
        self._cards: list[MethodCard] = []
        self._device_url = ""
        self._build_ui()
        self.refresh_detection(select_detected=True)

    # ------------------------------------------------------------------ UI
    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        accent = PROVIDER_COLORS[self.provider]
        title = QLabel(self.provider.long_label)
        title.setObjectName("title")
        title.setStyleSheet(f"border-left: 4px solid {accent}; padding-left: 8px;")
        layout.addWidget(title)

        self._status = QFrame()
        self._status.setObjectName("statusCard")
        status_layout = QVBoxLayout(self._status)
        status_layout.setContentsMargins(12, 10, 12, 10)
        self._status_title = QLabel("Not connected")
        self._status_title.setObjectName("statusTitle")
        self._status_detail = QLabel("Choose how you want to sign in below.")
        self._status_detail.setObjectName("statusDetail")
        self._status_detail.setWordWrap(True)
        self._status_detail.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        status_layout.addWidget(self._status_title)
        status_layout.addWidget(self._status_detail)
        layout.addWidget(self._status)

        # --- sign-in (hidden once connected)
        self._signin = QWidget()
        signin = QVBoxLayout(self._signin)
        signin.setContentsMargins(0, 0, 0, 0)
        signin.setSpacing(8)
        signin.addWidget(_section("Step 1 · Choose how to connect"))
        self._forms = QStackedWidget()
        for info in METHODS[self.provider]:
            card = MethodCard(info)
            card.clicked.connect(lambda m=info.method: self.select_method(m))
            self._cards.append(card)
            signin.addWidget(card)
            self._forms.addWidget(self._build_form(info.method))
        signin.addWidget(_section("Step 2 · Enter details"))
        signin.addWidget(self._forms)

        self._device_box = self._build_device_box()
        signin.addWidget(self._device_box)

        self._connect_btn = QPushButton("Connect")
        self._connect_btn.setObjectName("primary")
        self._connect_btn.setMinimumHeight(42)
        self._connect_btn.clicked.connect(self._on_connect)
        signin.addWidget(self._connect_btn)
        layout.addWidget(self._signin)

        self._error = QLabel("")
        self._error.setObjectName("errorText")
        self._error.setWordWrap(True)
        self._error.setVisible(False)
        self._error.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._error)

        # --- connected controls
        self._connected_box = QWidget()
        cbox = QVBoxLayout(self._connected_box)
        cbox.setContentsMargins(0, 0, 0, 0)
        self._choice_label = _field("Account")
        self._choice = QComboBox()
        self._choice.activated.connect(self._on_choice)
        cbox.addWidget(self._choice_label)
        cbox.addWidget(self._choice)
        disconnect = QPushButton("Disconnect")
        disconnect.clicked.connect(self.disconnect_requested.emit)
        cbox.addWidget(disconnect)
        self._connected_box.setVisible(False)
        layout.addWidget(self._connected_box)

        self.region_panel = RegionPanel()
        self.region_panel.setVisible(False)
        layout.addWidget(self.region_panel, stretch=1)
        layout.addStretch()
        self.select_method(self._method)

    def _build_device_box(self) -> QFrame:
        box = QFrame()
        box.setObjectName("card")
        lay = QVBoxLayout(box)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(6)
        self._device_text = QLabel("")
        self._device_text.setWordWrap(True)
        self._device_code = QLabel("")
        self._device_code.setObjectName("deviceCode")
        self._device_code.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._device_code.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        buttons = QHBoxLayout()
        reopen = QPushButton("Open page again")
        reopen.clicked.connect(lambda: self._device_url and webbrowser.open(self._device_url))
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.cancel_requested.emit)
        buttons.addWidget(reopen)
        buttons.addWidget(cancel)
        self._reopen_btn = reopen
        lay.addWidget(self._device_text)
        lay.addWidget(self._device_code)
        lay.addLayout(buttons)
        box.setVisible(False)
        return box

    def _build_form(self, method: AuthMethod) -> QWidget:
        form = QWidget()
        lay = QVBoxLayout(form)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(4)
        p = self.provider

        if p == CloudProvider.AWS and method == AuthMethod.ACCESS_KEYS:
            self._aws_key = QLineEdit()
            self._aws_key.setPlaceholderText("AKIA…")
            self._aws_secret, show = _secret("Secret Access Key")
            self._aws_token, _ = _secret("Only for temporary keys (ASIA…)")
            lay.addWidget(_field("Access Key ID"))
            lay.addWidget(self._aws_key)
            lay.addWidget(_field("Secret Access Key"))
            row = QHBoxLayout()
            row.addWidget(self._aws_secret, stretch=1)
            row.addWidget(show)
            lay.addLayout(row)
            lay.addWidget(_field("Session token (optional)"))
            lay.addWidget(self._aws_token)
            tip = QLabel("Find them in the AWS Console → your name (top right) → "
                         "Security credentials → Access keys.")
            tip.setObjectName("muted")
            tip.setWordWrap(True)
            lay.addWidget(tip)

        elif p == CloudProvider.AWS and method == AuthMethod.BROWSER:
            self._aws_sso_profile = QComboBox()
            self._aws_sso_profile.currentTextChanged.connect(self._fill_from_sso_profile)
            self._aws_sso_profile_label = _field("Fill in from a profile on this computer")
            lay.addWidget(self._aws_sso_profile_label)
            lay.addWidget(self._aws_sso_profile)
            self._aws_start_url = QLineEdit()
            self._aws_start_url.setPlaceholderText("https://my-org.awsapps.com/start")
            self._aws_sso_region = QComboBox()
            self._aws_sso_region.setEditable(True)
            self._aws_sso_region.addItems(sorted(set(COMMON_REGIONS) | {"eu-central-1"}))
            self._aws_sso_region.setCurrentText("us-east-1")
            lay.addWidget(_field("AWS access portal URL"))
            lay.addWidget(self._aws_start_url)
            lay.addWidget(_field("Identity Center region"))
            lay.addWidget(self._aws_sso_region)

        elif p == CloudProvider.AWS and method == AuthMethod.LOCAL:
            self._aws_profile = QComboBox()
            lay.addWidget(_field("AWS profile"))
            lay.addWidget(self._aws_profile)
            self._aws_local_note = QLabel("")
            self._aws_local_note.setObjectName("muted")
            self._aws_local_note.setWordWrap(True)
            lay.addWidget(self._aws_local_note)

        elif p == CloudProvider.AZURE and method == AuthMethod.BROWSER:
            self._az_browser_tenant = QLineEdit()
            self._az_browser_tenant.setPlaceholderText("Optional — only if you have several")
            lay.addWidget(_field("Tenant / directory ID"))
            lay.addWidget(self._az_browser_tenant)
            note = QLabel("A browser window opens for you to sign in. Afterwards you can pick "
                          "the subscription to scan.")
            note.setObjectName("muted")
            note.setWordWrap(True)
            lay.addWidget(note)

        elif p == CloudProvider.AZURE and method == AuthMethod.LOCAL:
            self._az_local_note = QLabel("")
            self._az_local_note.setWordWrap(True)
            lay.addWidget(self._az_local_note)

        elif p == CloudProvider.AZURE and method == AuthMethod.SERVICE_PRINCIPAL:
            self._az_tenant = QLineEdit()
            self._az_client = QLineEdit()
            self._az_secret, show = _secret("Client secret value")
            self._az_sub = QLineEdit()
            self._az_sub.setPlaceholderText("Optional — picked after sign-in")
            for label, widget in (("Tenant ID", self._az_tenant),
                                  ("Client (application) ID", self._az_client)):
                lay.addWidget(_field(label))
                lay.addWidget(widget)
            lay.addWidget(_field("Client secret"))
            row = QHBoxLayout()
            row.addWidget(self._az_secret, stretch=1)
            row.addWidget(show)
            lay.addLayout(row)
            lay.addWidget(_field("Subscription ID"))
            lay.addWidget(self._az_sub)

        elif p == CloudProvider.GCP and method == AuthMethod.BROWSER:
            self._gcp_browser_note = QLabel("")
            self._gcp_browser_note.setWordWrap(True)
            self._gcp_browser_note.setTextFormat(Qt.TextFormat.RichText)
            self._gcp_browser_note.setOpenExternalLinks(True)
            lay.addWidget(self._gcp_browser_note)
            self._gcp_browser_project = QLineEdit()
            self._gcp_browser_project.setPlaceholderText("Optional — picked after sign-in")
            lay.addWidget(_field("Project ID"))
            lay.addWidget(self._gcp_browser_project)

        elif p == CloudProvider.GCP and method == AuthMethod.LOCAL:
            self._gcp_local_note = QLabel("")
            self._gcp_local_note.setWordWrap(True)
            self._gcp_local_project = QLineEdit()
            self._gcp_local_project.setPlaceholderText("Optional — picked after sign-in")
            lay.addWidget(self._gcp_local_note)
            lay.addWidget(_field("Project ID"))
            lay.addWidget(self._gcp_local_project)

        elif p == CloudProvider.GCP and method == AuthMethod.SERVICE_ACCOUNT:
            pick = QPushButton("Choose JSON key file…")
            pick.clicked.connect(self._pick_key_file)
            self._gcp_key = QPlainTextEdit()
            self._gcp_key.setPlaceholderText("…or paste the JSON key here")
            self._gcp_key.setFixedHeight(110)
            self._gcp_sa_project = QLineEdit()
            self._gcp_sa_project.setPlaceholderText("Optional — defaults to the key's project")
            lay.addWidget(pick)
            lay.addWidget(self._gcp_key)
            lay.addWidget(_field("Project ID"))
            lay.addWidget(self._gcp_sa_project)
        lay.addStretch()
        return form

    # ------------------------------------------------------------ behaviour
    def refresh_detection(self, select_detected: bool = False) -> None:
        """Look for existing logins on this computer and update badges/hints."""
        detected = ""
        if self.provider == CloudProvider.AWS:
            profiles = list_local_profiles()
            self._aws_profile.clear()
            self._aws_profile.addItems(profiles)
            if profiles:
                detected = f"{len(profiles)} found"
                self._aws_local_note.setText(
                    "Profiles from ~/.aws/credentials and ~/.aws/config."
                    + (" Environment variables are set too." if ENV_PROFILE in profiles else "")
                )
            else:
                self._aws_local_note.setText(
                    "No AWS login found on this computer. Run 'aws configure' in a terminal, "
                    "or use Access keys / Sign in with browser."
                )
            sso = list_sso_profiles()
            self._aws_sso_profile.clear()
            self._aws_sso_profile.addItems(["(type the details below)", *sso])
            self._aws_sso_profile.setVisible(bool(sso))
            self._aws_sso_profile_label.setVisible(bool(sso))
        elif self.provider == CloudProvider.AZURE:
            found = detect_local_azure()
            detected = "found" if found else ""
            self._az_local_note.setText(
                f"Detected: <b>{found}</b>" if found else
                "No Azure login found. Run 'az login' in a terminal, or use Sign in with browser."
            )
        else:
            found = detect_local_gcp()
            detected = "found" if found else ""
            self._gcp_local_note.setText(
                f"Detected: {found}" if found else
                "No Google login found on this computer. Use Sign in with browser, or run "
                "'gcloud auth application-default login'."
            )
            if gcloud_path():
                self._gcp_browser_note.setText(
                    "gcloud CLI found ✓ — a browser window opens for you to sign in.")
            else:
                self._gcp_browser_note.setText(
                    "This needs the free gcloud CLI, which isn't installed. "
                    f"<a href='{GCLOUD_INSTALL_URL}'>Install it</a>, or use a service account "
                    "key instead.")

        for card in self._cards:
            card.set_badge(f"Detected · {detected}" if card.info.method == AuthMethod.LOCAL
                           and detected else "")
        if select_detected and detected:
            self.select_method(AuthMethod.LOCAL)

    def select_method(self, method: AuthMethod) -> None:
        self._method = method
        for index, card in enumerate(self._cards):
            selected = card.info.method == method
            card.set_selected(selected)
            if selected:
                self._forms.setCurrentIndex(index)
                self._connect_btn.setText(card.info.button)
        self._error.setVisible(False)

    def _fill_from_sso_profile(self, profile: str) -> None:
        settings = sso_settings_for_profile(profile) if profile else None
        if settings:
            self._aws_start_url.setText(settings.start_url)
            self._aws_sso_region.setCurrentText(settings.region)

    def _pick_key_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose service account key", str(Path.home()), "JSON key (*.json)")
        if path:
            try:
                self._gcp_key.setPlainText(Path(path).read_text(encoding="utf-8"))
            except OSError as exc:
                self.set_error(f"Could not read the key file: {exc}")

    def build_config(self) -> AuthConfig:
        config = AuthConfig(provider=self.provider, method=self._method)
        match (self.provider, self._method):
            case (CloudProvider.AWS, AuthMethod.ACCESS_KEYS):
                config.access_key_id = self._aws_key.text()
                config.secret_access_key = self._aws_secret.text()
                config.session_token = self._aws_token.text()
            case (CloudProvider.AWS, AuthMethod.BROWSER):
                config.sso_start_url = self._aws_start_url.text()
                config.sso_region = self._aws_sso_region.currentText()
                settings = sso_settings_for_profile(self._aws_sso_profile.currentText())
                if settings:
                    config.sso_account_id = settings.account_id
                    config.sso_role_name = settings.role_name
            case (CloudProvider.AWS, AuthMethod.LOCAL):
                config.profile_name = self._aws_profile.currentText()
            case (CloudProvider.AZURE, AuthMethod.BROWSER):
                config.tenant_id = self._az_browser_tenant.text()
            case (CloudProvider.AZURE, AuthMethod.SERVICE_PRINCIPAL):
                config.tenant_id = self._az_tenant.text()
                config.client_id = self._az_client.text()
                config.client_secret = self._az_secret.text()
                config.subscription_id = self._az_sub.text()
            case (CloudProvider.GCP, AuthMethod.BROWSER):
                config.project_id = self._gcp_browser_project.text()
            case (CloudProvider.GCP, AuthMethod.LOCAL):
                config.project_id = self._gcp_local_project.text()
            case (CloudProvider.GCP, AuthMethod.SERVICE_ACCOUNT):
                config.service_account_json = self._gcp_key.toPlainText()
                config.project_id = self._gcp_sa_project.text()
        return config

    def _on_connect(self) -> None:
        self._error.setVisible(False)
        self.connect_requested.emit(self.build_config())

    def _on_choice(self, index: int) -> None:
        key = self._choice.itemData(index)
        if key:
            self.switch_requested.emit(key)

    # ----------------------------------------------------------- state API
    def _set_status(self, state: str, title: str, detail: str) -> None:
        self._status.setProperty("state", state)
        self._status.style().unpolish(self._status)
        self._status.style().polish(self._status)
        self._status_title.setText(title)
        self._status_detail.setText(detail)

    def set_busy(self, message: str) -> None:
        self._connect_btn.setEnabled(False)
        self._connect_btn.setText("Connecting…")
        self._set_status("", "Connecting…", message)

    def show_device_code(self, code: DeviceCode) -> None:
        self._device_url = code.verification_url
        self._device_text.setText(
            "A browser page opened. Check that it shows this code, then click "
            "<b>Confirm and continue</b> and <b>Allow</b>:")
        self._device_code.setText(code.user_code)
        self._device_box.setVisible(True)
        self._set_status("", "Waiting for you in the browser…", "Approve the sign-in to continue.")

    def set_error(self, message: str) -> None:
        self._device_box.setVisible(False)
        self._connect_btn.setEnabled(True)
        self.select_method(self._method)
        self._error.setText(message)
        self._error.setVisible(True)
        self._set_status("error", "Not connected", "Fix the problem below and try again.")

    def set_connected(self, result: ConnectResult) -> None:
        session = result.session
        self._device_box.setVisible(False)
        self._error.setVisible(False)
        self._signin.setVisible(False)
        self._set_status("connected", f"✓ Connected to {self.provider.label}",
                         session.account_label)
        self._choice.clear()
        for choice in result.choices:
            self._choice.addItem(choice.label, choice.key)
        current = next((i for i, c in enumerate(result.choices) if c.key.split("|")[0]
                        == session.account_id), 0)
        self._choice.setCurrentIndex(current)
        many = len(result.choices) > 1
        self._choice_label.setText(result.choice_title or "Account")
        self._choice_label.setVisible(many)
        self._choice.setVisible(many)
        self._connected_box.setVisible(True)
        self.region_panel.setVisible(True)

    def update_session_label(self, label: str) -> None:
        self._status_detail.setText(label)

    def set_disconnected(self) -> None:
        self._signin.setVisible(True)
        self._connected_box.setVisible(False)
        self.region_panel.setVisible(False)
        self.region_panel.clear()
        self._device_box.setVisible(False)
        self._connect_btn.setEnabled(True)
        self.select_method(self._method)
        self._set_status("", "Not connected", "Choose how you want to sign in below.")
        self.refresh_detection()
