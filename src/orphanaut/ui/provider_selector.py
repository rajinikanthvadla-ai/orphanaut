"""Cloud provider pill selector (AWS / Azure / GCP)."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QWidget

from orphanaut.models import CloudProvider


class ProviderSelector(QWidget):
    provider_changed = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._provider = CloudProvider.AWS
        self._buttons: dict[CloudProvider, QPushButton] = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        for provider in CloudProvider:
            button = QPushButton(provider.label)
            button.setObjectName("providerBtn")
            button.setCheckable(True)
            button.setMinimumHeight(34)
            button.clicked.connect(lambda checked, p=provider: self._select(p))
            self._buttons[provider] = button
            layout.addWidget(button, stretch=1)

        self._select(CloudProvider.AWS, emit=False)

    def _select(self, provider: CloudProvider, *, emit: bool = True) -> None:
        self._provider = provider
        for cloud, button in self._buttons.items():
            active = cloud == provider
            button.setChecked(active)
            button.setProperty("active", active)
            button.style().unpolish(button)
            button.style().polish(button)
        if emit:
            self.provider_changed.emit(provider)

    def provider(self) -> CloudProvider:
        return self._provider

    def set_provider(self, provider: CloudProvider) -> None:
        self._select(provider, emit=False)
