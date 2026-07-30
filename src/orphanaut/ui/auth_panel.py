"""Authentication panel widget."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTabWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from orphanaut.auth.credentials import list_sso_profiles
from orphanaut.models import AuthConfig, AuthMethod


class AuthPanel(QWidget):
    connect_requested = Signal(AuthConfig)
    connection_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self._connected = False
        self._editing_credentials = False
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll, stretch=1)

        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 4, 0)
        layout.setSpacing(14)
        scroll.setWidget(content)

        title = QLabel("AWS connection")
        title.setObjectName("title")
        subtitle = QLabel("Connect securely, then choose where to scan")
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(subtitle)

        self._steps_frame = self._build_steps_guide()
        layout.addWidget(self._steps_frame)

        self._status_card = self._build_status_card()
        layout.addWidget(self._status_card)

        self._keys_header = QLabel("Step 1 — Enter your AWS keys")
        self._keys_header.setObjectName("sectionHeader")
        layout.addWidget(self._keys_header)

        self._student_tip = QLabel(
            "Most students only need an <b>Access Key ID</b> and <b>Secret Access Key</b> "
            "from their instructor or the AWS Console. You do <b>not</b> need AWS CLI or SSO."
        )
        self._student_tip.setObjectName("infoBanner")
        self._student_tip.setWordWrap(True)
        layout.addWidget(self._student_tip)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_access_keys_tab(), "Access Keys")
        self._tabs.addTab(self._build_sso_tab(), "SSO (Advanced)")
        self._tabs.currentChanged.connect(self._on_tab_changed)
        layout.addWidget(self._tabs)

        self._connect_btn = QPushButton("Connect to AWS")
        self._connect_btn.setObjectName("primary")
        self._connect_btn.setMinimumHeight(42)
        self._connect_btn.clicked.connect(self._on_connect)
        layout.addWidget(self._connect_btn)

        self._help_toggle = QToolButton()
        self._help_toggle.setText("Where do I find my Access Keys?")
        self._help_toggle.setCheckable(True)
        self._help_toggle.setObjectName("helpToggle")
        self._help_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._help_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self._help_toggle.toggled.connect(self._toggle_help)
        layout.addWidget(self._help_toggle)

        self._help_panel = QLabel(
            "<b>In the AWS Console:</b><br>"
            "1. Sign in at <i>console.aws.amazon.com</i><br>"
            "2. Click your name (top-right) → <b>Security credentials</b><br>"
            "3. Scroll to <b>Access keys</b> → Create or view your keys<br>"
            "4. Copy the <b>Access Key ID</b> (starts with AKIA...) and "
            "<b>Secret Access Key</b><br><br>"
            "<b>From your instructor:</b><br>"
            "Paste the Access Key ID and Secret Access Key they gave you. "
            "Leave Session Token empty unless they also provided one."
        )
        self._help_panel.setObjectName("helpPanel")
        self._help_panel.setWordWrap(True)
        self._help_panel.setVisible(False)
        layout.addWidget(self._help_panel)

        layout.addStretch()

        self._error_label = QLabel("")
        self._error_label.setObjectName("errorText")
        self._error_label.setWordWrap(True)
        self._error_label.setVisible(False)
        outer.addWidget(self._error_label)

    def _build_steps_guide(self) -> QFrame:
        frame = QFrame()
        frame.setObjectName("stepsCard")
        row = QHBoxLayout(frame)
        row.setContentsMargins(12, 10, 12, 10)
        row.setSpacing(8)

        self._step_labels: list[QLabel] = []
        steps = [
            ("1", "Connect"),
            ("2", "Scan"),
            ("3", "Clean up"),
        ]
        for index, (number, label) in enumerate(steps):
            if index > 0:
                arrow = QLabel("→")
                arrow.setObjectName("stepArrow")
                row.addWidget(arrow)

            step = QLabel(f'<span class="stepNum">{number}</span> {label}')
            step.setObjectName("stepLabel")
            step.setProperty("active", index == 0)
            self._step_labels.append(step)
            row.addWidget(step)

        row.addStretch()
        return frame

    def _build_status_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("statusCard")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(12, 10, 12, 10)

        self._status_dot = QLabel("●")
        self._status_dot.setObjectName("statusDot")
        self._status_dot.setProperty("connected", False)

        status_text = QVBoxLayout()
        self._status_title = QLabel("Not connected")
        self._status_title.setObjectName("statusTitle")
        self._status_detail = QLabel("Enter your keys and click Connect")
        self._status_detail.setObjectName("statusDetail")
        self._status_detail.setWordWrap(True)
        status_text.addWidget(self._status_title)
        status_text.addWidget(self._status_detail)

        card_layout.addWidget(self._status_dot)
        card_layout.addLayout(status_text, stretch=1)
        return card

    def _build_access_keys_tab(self) -> QWidget:
        widget = QWidget()
        form = QFormLayout(widget)
        form.setContentsMargins(12, 12, 12, 8)
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self._access_key_input = QLineEdit()
        self._access_key_input.setPlaceholderText("AKIAIOSFODNN7EXAMPLE")
        self._access_key_input.textChanged.connect(self._clear_field_error)
        self._access_key_input.setToolTip("Your AWS Access Key ID — usually starts with AKIA")

        secret_row = QHBoxLayout()
        self._secret_key_input = QLineEdit()
        self._secret_key_input.setPlaceholderText("Paste your secret access key here")
        self._secret_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._secret_key_input.textChanged.connect(self._clear_field_error)
        self._show_secret_cb = QCheckBox("Show")
        self._show_secret_cb.toggled.connect(self._toggle_secret_visibility)
        secret_row.addWidget(self._secret_key_input, stretch=1)
        secret_row.addWidget(self._show_secret_cb)

        self._advanced_toggle = QToolButton()
        self._advanced_toggle.setText("Session Token (optional)")
        self._advanced_toggle.setCheckable(True)
        self._advanced_toggle.setObjectName("helpToggle")
        self._advanced_toggle.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._advanced_toggle.setArrowType(Qt.ArrowType.RightArrow)
        self._advanced_toggle.toggled.connect(self._toggle_advanced)

        self._session_token_input = QLineEdit()
        self._session_token_input.setPlaceholderText(
            "Only if your instructor gave you a session token"
        )
        self._session_token_input.setVisible(False)

        form.addRow("Access Key ID", self._access_key_input)
        form.addRow("Secret Access Key", secret_row)
        form.addRow(self._advanced_toggle)
        form.addRow("", self._session_token_input)
        return widget

    def _build_sso_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        info = QLabel(
            "<b>For users with AWS CLI already set up.</b><br><br>"
            "1. Run <b>aws configure sso</b> once to create a profile<br>"
            "2. Run <b>aws sso login --profile YOUR_PROFILE</b> before connecting<br>"
            "3. Select your profile below and click Connect"
        )
        info.setObjectName("helpPanel")
        info.setWordWrap(True)
        layout.addWidget(info)

        profile_label = QLabel("SSO Profile name")
        profile_label.setObjectName("fieldLabel")
        layout.addWidget(profile_label)

        row = QHBoxLayout()
        self._sso_profile_combo = QComboBox()
        self._sso_profile_combo.setEditable(True)
        self._sso_profile_combo.setPlaceholderText("e.g. my-sso-profile")
        self._refresh_profiles_btn = QPushButton("Refresh")
        self._refresh_profiles_btn.clicked.connect(self._refresh_sso_profiles)
        row.addWidget(self._sso_profile_combo, stretch=1)
        row.addWidget(self._refresh_profiles_btn)
        layout.addLayout(row)

        self._refresh_sso_profiles()
        layout.addStretch()
        return widget

    def _toggle_help(self, expanded: bool) -> None:
        self._help_panel.setVisible(expanded)
        self._help_toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )

    def _toggle_advanced(self, expanded: bool) -> None:
        self._session_token_input.setVisible(expanded)
        self._advanced_toggle.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow
        )

    def _toggle_secret_visibility(self, show: bool) -> None:
        mode = QLineEdit.EchoMode.Normal if show else QLineEdit.EchoMode.Password
        self._secret_key_input.setEchoMode(mode)

    def _on_tab_changed(self, index: int) -> None:
        is_keys = index == 0
        self._help_toggle.setVisible(is_keys)
        if not is_keys:
            self._help_toggle.setChecked(False)
            self._help_panel.setVisible(False)

    def _refresh_sso_profiles(self) -> None:
        current = self._sso_profile_combo.currentText()
        self._sso_profile_combo.clear()
        profiles = list_sso_profiles()
        if profiles:
            self._sso_profile_combo.addItems(profiles)
        elif not current:
            self._sso_profile_combo.setPlaceholderText("No SSO profiles found — type profile name")
        if current:
            self._sso_profile_combo.setCurrentText(current)

    def _clear_field_error(self) -> None:
        self._access_key_input.setProperty("error", False)
        self._secret_key_input.setProperty("error", False)
        self._access_key_input.style().unpolish(self._access_key_input)
        self._access_key_input.style().polish(self._access_key_input)
        self._secret_key_input.style().unpolish(self._secret_key_input)
        self._secret_key_input.style().polish(self._secret_key_input)
        self._error_label.setVisible(False)

    def _validate_access_keys(self) -> bool:
        missing_access = not self._access_key_input.text().strip()
        missing_secret = not self._secret_key_input.text().strip()
        if missing_access:
            self._access_key_input.setProperty("error", True)
            self._access_key_input.style().unpolish(self._access_key_input)
            self._access_key_input.style().polish(self._access_key_input)
        if missing_secret:
            self._secret_key_input.setProperty("error", True)
            self._secret_key_input.style().unpolish(self._secret_key_input)
            self._secret_key_input.style().polish(self._secret_key_input)
        if missing_access or missing_secret:
            self._show_error("Please enter both your Access Key ID and Secret Access Key.")
            return False
        return True

    def _show_error(self, message: str) -> None:
        self._error_label.setText(message)
        self._error_label.setVisible(True)

    def _on_connect(self) -> None:
        if self._connected and not self._editing_credentials:
            self._set_credentials_expanded(True)
            return

        self._clear_field_error()
        if self._tabs.currentIndex() == 0 and not self._validate_access_keys():
            return

        if self._tabs.currentIndex() == 0:
            config = AuthConfig(
                method=AuthMethod.ACCESS_KEYS,
                access_key_id=self._access_key_input.text(),
                secret_access_key=self._secret_key_input.text(),
                session_token=self._session_token_input.text(),
            )
        else:
            config = AuthConfig(
                method=AuthMethod.SSO_PROFILE,
                profile_name=self._sso_profile_combo.currentText(),
            )
        self.connect_requested.emit(config)

    def set_connected(self, account_id: str, arn: str) -> None:
        self._connected = True
        self._editing_credentials = False
        self._status_dot.setProperty("connected", True)
        self._status_dot.style().unpolish(self._status_dot)
        self._status_dot.style().polish(self._status_dot)
        self._status_title.setText("Connected to AWS")
        self._status_detail.setText(f"Account {account_id}\n{arn}")
        self._set_credentials_expanded(False)
        self._error_label.setVisible(False)
        self._set_active_step(1)
        self.connection_changed.emit(True)

    def set_error(self, message: str) -> None:
        self._connected = False
        self._editing_credentials = True
        self._status_dot.setProperty("connected", False)
        self._status_dot.style().unpolish(self._status_dot)
        self._status_dot.style().polish(self._status_dot)
        self._status_title.setText("Connection failed")
        self._status_detail.setText("Check your keys and try again")
        self._show_error(message)
        self._set_active_step(0)
        self.connection_changed.emit(False)

    def _set_credentials_expanded(self, expanded: bool) -> None:
        self._editing_credentials = expanded
        self._keys_header.setVisible(expanded)
        self._student_tip.setVisible(expanded)
        self._tabs.setVisible(expanded)
        self._help_toggle.setVisible(expanded and self._tabs.currentIndex() == 0)
        if not expanded:
            self._help_toggle.setChecked(False)
            self._help_panel.setVisible(False)
        self._connect_btn.setText("Reconnect to AWS" if expanded else "Change credentials")

    def set_connecting(self) -> None:
        self._status_title.setText("Connecting...")
        self._status_detail.setText("Verifying your AWS credentials")
        self._connect_btn.setEnabled(False)
        self._error_label.setVisible(False)

    def set_connect_enabled(self, enabled: bool) -> None:
        self._connect_btn.setEnabled(enabled)

    def set_scan_complete(self) -> None:
        self._set_active_step(2)

    def reset_workflow(self) -> None:
        self._set_active_step(0 if not self._connected else 1)

    def _set_active_step(self, index: int) -> None:
        for step_index, label in enumerate(self._step_labels):
            label.setProperty("active", step_index == index)
            label.setProperty("done", step_index < index)
            label.style().unpolish(label)
            label.style().polish(label)
