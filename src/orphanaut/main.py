"""Application entry point."""

import sys

from PySide6.QtWidgets import QApplication

from orphanaut.ui.main_window import MainWindow
from orphanaut.ui.styles import STYLESHEET


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("Orphanaut")
    app.setOrganizationName("Orphanaut")
    app.setStyleSheet(STYLESHEET)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
