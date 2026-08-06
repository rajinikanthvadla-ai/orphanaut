"""Application stylesheet."""

STYLESHEET = """
QMainWindow, QDialog {
    background-color: #1a1d23;
    color: #e4e6eb;
}

QWidget {
    font-family: "Segoe UI", "SF Pro Text", system-ui, sans-serif;
    font-size: 13px;
    color: #e4e6eb;
}

QLabel#title {
    font-size: 20px;
    font-weight: 700;
    color: #ffffff;
}

QLabel#appTitle {
    font-size: 26px;
    font-weight: 800;
    color: #ffffff;
}

QLabel#privacyBadge {
    background-color: #16362d;
    border: 1px solid #256d56;
    border-radius: 14px;
    color: #86efac;
    padding: 7px 12px;
    font-size: 12px;
    font-weight: 600;
}

QLabel#subtitle {
    font-size: 12px;
    color: #9ca3af;
}

QLabel#sectionHeader {
    font-size: 14px;
    font-weight: 700;
    color: #f3f4f6;
    margin-top: 4px;
}

QLabel#fieldLabel {
    font-size: 12px;
    font-weight: 600;
    color: #d1d5db;
}

QLabel#infoBanner {
    background-color: #1e3a5f;
    border: 1px solid #2563eb;
    border-radius: 8px;
    padding: 10px 12px;
    color: #dbeafe;
    font-size: 12px;
}

QLabel#helpPanel {
    background-color: #252a33;
    border: 1px solid #3d4450;
    border-radius: 8px;
    padding: 12px;
    color: #d1d5db;
    font-size: 12px;
}

QLabel#errorText {
    color: #fca5a5;
    font-size: 12px;
    padding: 4px 0;
}

QLabel#warningBanner {
    background-color: #3b2f16;
    border: 1px solid #a16207;
    border-radius: 8px;
    color: #fde68a;
    padding: 10px 12px;
    font-size: 12px;
}

QLabel#scanBanner {
    background-color: #172f52;
    border: 1px solid #2563eb;
    border-radius: 8px;
    color: #bfdbfe;
    padding: 10px 12px;
    font-size: 12px;
    font-weight: 600;
}

QFrame#stepsCard {
    background-color: #252a33;
    border: 1px solid #2d3340;
    border-radius: 8px;
}

QLabel#stepLabel {
    color: #6b7280;
    font-size: 12px;
    font-weight: 600;
}

QLabel#stepLabel[active="true"] {
    color: #60a5fa;
}

QLabel#stepLabel[done="true"] {
    color: #34d399;
}

QLabel#stepArrow {
    color: #4b5563;
    font-size: 11px;
}

QLabel#stepLabel .stepNum {
    font-weight: 700;
}

QFrame#statusCard {
    background-color: #1f2329;
    border: 1px solid #2d3340;
    border-radius: 8px;
}

QLabel#statusDot {
    color: #6b7280;
    font-size: 18px;
    padding-right: 4px;
}

QLabel#statusDot[connected="true"] {
    color: #34d399;
}

QLabel#statusTitle {
    font-weight: 700;
    color: #f3f4f6;
    font-size: 13px;
}

QLabel#statusDetail {
    color: #9ca3af;
    font-size: 11px;
}

QFrame#welcomeCard {
    background-color: #1f2329;
    border: 1px solid #2d3340;
    border-radius: 12px;
}

QSplitter::handle {
    background-color: #2d3340;
    width: 1px;
    margin: 0 8px;
}

QLabel#welcomeTitle {
    font-size: 22px;
    font-weight: 700;
    color: #ffffff;
}

QLabel#welcomeBody {
    font-size: 14px;
    color: #9ca3af;
    line-height: 1.5;
}

QLabel#welcomeSteps {
    font-size: 14px;
    color: #d1d5db;
}

QLabel#welcomeSteps .bigStep {
    display: inline-block;
    background-color: #2563eb;
    color: #ffffff;
    font-weight: 700;
    font-size: 14px;
    border-radius: 50%;
    min-width: 28px;
    min-height: 28px;
    text-align: center;
    padding: 4px;
}

QLabel#welcomeNote {
    font-size: 12px;
    color: #6b7280;
    font-style: italic;
}

QLabel#readyIcon {
    font-size: 48px;
    color: #34d399;
    font-weight: 700;
}

QGroupBox {
    border: 1px solid #2d3340;
    border-radius: 8px;
    margin-top: 12px;
    padding: 16px 12px 12px 12px;
    font-weight: 600;
    color: #d1d5db;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}

QLineEdit, QComboBox, QPlainTextEdit {
    background-color: #252a33;
    border: 1px solid #3d4450;
    border-radius: 6px;
    padding: 8px 10px;
    color: #f3f4f6;
    selection-background-color: #3b82f6;
}

QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {
    border-color: #3b82f6;
}

QLineEdit[error="true"] {
    border-color: #ef4444;
    background-color: #2d1f1f;
}

QPushButton {
    background-color: #2d3340;
    border: 1px solid #3d4450;
    border-radius: 6px;
    padding: 8px 16px;
    color: #f3f4f6;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #3d4450;
}

QPushButton:pressed {
    background-color: #252a33;
}

QPushButton:disabled {
    color: #6b7280;
    background-color: #1f2329;
}

QPushButton#primary {
    background-color: #2563eb;
    border-color: #2563eb;
    color: #ffffff;
}

QPushButton#primary:hover {
    background-color: #1d4ed8;
}

QPushButton#danger {
    background-color: #dc2626;
    border-color: #dc2626;
    color: #ffffff;
}

QPushButton#danger:hover {
    background-color: #b91c1c;
}

QPushButton#danger:disabled {
    background-color: #3d2020;
    border-color: #3d2020;
    color: #6b7280;
}

QToolButton#helpToggle {
    background: transparent;
    border: none;
    color: #60a5fa;
    font-size: 12px;
    font-weight: 600;
    text-align: left;
    padding: 4px 0;
}

QToolButton#helpToggle:hover {
    color: #93c5fd;
}

QCheckBox {
    color: #9ca3af;
    font-size: 12px;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
}

QScrollArea {
    background: transparent;
    border: none;
}

QTableWidget {
    background-color: #1f2329;
    alternate-background-color: #252a33;
    border: 1px solid #2d3340;
    border-radius: 8px;
    gridline-color: #2d3340;
    selection-background-color: #1e3a5f;
    selection-color: #ffffff;
}

QTableWidget::item {
    padding: 6px;
}

QHeaderView::section {
    background-color: #252a33;
    color: #9ca3af;
    padding: 8px;
    border: none;
    border-bottom: 1px solid #2d3340;
    font-weight: 600;
}

QTabWidget::pane {
    border: 1px solid #2d3340;
    border-radius: 8px;
    background-color: #1a1d23;
}

QTabBar::tab {
    background-color: #252a33;
    color: #9ca3af;
    padding: 10px 20px;
    margin-right: 2px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}

QTabBar::tab:selected {
    background-color: #1a1d23;
    color: #ffffff;
    border-bottom: 2px solid #3b82f6;
}

QStatusBar {
    background-color: #14171c;
    color: #9ca3af;
    border-top: 1px solid #2d3340;
}

QLabel#creditLabel {
    color: #4b5563;
    font-size: 11px;
    font-style: italic;
    padding-right: 6px;
}

QProgressBar {
    border: 1px solid #3d4450;
    border-radius: 6px;
    background-color: #252a33;
    text-align: center;
    color: #e4e6eb;
    min-height: 18px;
    max-height: 18px;
    font-size: 11px;
}

QProgressBar::chunk {
    background-color: #3b82f6;
    border-radius: 4px;
}

QListWidget#regionList {
    background-color: #1f2329;
    border: 1px solid #2d3340;
    border-radius: 8px;
    padding: 4px;
}

QListWidget#regionList::item {
    padding: 4px 2px;
}

QPushButton#providerBtn {
    background-color: #252a33;
    border: 1px solid #3d4450;
    border-radius: 8px;
    padding: 6px 10px;
    font-weight: 700;
    color: #9ca3af;
}

QPushButton#providerBtn:hover {
    background-color: #2d3340;
    color: #e4e6eb;
}

QPushButton#providerBtn:checked,
QPushButton#providerBtn[active="true"] {
    background-color: #1e3a5f;
    border-color: #3b82f6;
    color: #ffffff;
}

QLineEdit#search {
    min-width: 240px;
}
"""
