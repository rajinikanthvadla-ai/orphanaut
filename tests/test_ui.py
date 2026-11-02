"""Offscreen UI tests: the window builds, cloud tabs switch, results filter, impact map shows."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

from orphanaut.auth.router import Choice, ConnectResult  # noqa: E402
from orphanaut.dependencies import dep  # noqa: E402
from orphanaut.models import AuthMethod, CloudProvider, CloudResource  # noqa: E402
from orphanaut.providers.session import ProviderSession  # noqa: E402
from orphanaut.ui.main_window import MainWindow  # noqa: E402
from orphanaut.ui.styles import apply_theme  # noqa: E402


@pytest.fixture(scope="module")
def app():
    instance = QApplication.instance() or QApplication([])
    apply_theme(instance)
    return instance


@pytest.fixture
def window(app):
    win = MainWindow()
    win.show()
    app.processEvents()
    yield win
    win.close()


def _resources():
    return [
        CloudResource("d-1", "domain", "SageMaker", "Studio Domain", "us-east-1", "InService",
                      "", extra={"dependents": [dep("User profile", "alice")],
                                 "monthly_cost": 10.0}),
        CloudResource("i-1", "web", "EC2", "Instance", "us-east-1", "running", "Type: t3.micro"),
        CloudResource("arn", "pt", "Bedrock", "Provisioned Throughput", "us-east-1", "", "",
                      deletable=False),
    ]


def test_window_has_one_workspace_per_cloud(window):
    for provider in CloudProvider:
        assert window.workspace(provider).provider == provider
    window._select(CloudProvider.GCP)
    assert window._stack.currentWidget() is window.workspace(CloudProvider.GCP)


@pytest.mark.parametrize("provider", list(CloudProvider))
def test_connect_panel_builds_config_for_each_method(window, provider):
    panel = window.workspace(provider).connect_panel
    for card in panel._cards:
        panel.select_method(card.info.method)
        config = panel.build_config()
        assert config.provider == provider
        assert config.method == card.info.method


def test_aws_keys_form_fills_config(window):
    panel = window.workspace(CloudProvider.AWS).connect_panel
    panel.select_method(AuthMethod.ACCESS_KEYS)
    panel._aws_key.setText("AKIAEXAMPLE")
    panel._aws_secret.setText("secret")
    config = panel.build_config()
    assert (config.access_key_id, config.secret_access_key) == ("AKIAEXAMPLE", "secret")


def test_results_filter_by_category_and_impact_map(window, app):
    ws = window.workspace(CloudProvider.AWS)
    session = ProviderSession(CloudProvider.AWS, object(), "1", "student")
    ws._session = session
    ws.connect_panel.set_connected(ConnectResult(session, "Account", [Choice("1|r", "one")]))
    ws._tabs.setVisible(True)
    ws._stack.setCurrentIndex(2)
    ws._add_rows(_resources())
    assert ws._table.rowCount() == 3

    ws._tabs.setCurrentIndex(1)  # AI & ML
    visible = [r for r in range(ws._table.rowCount()) if not ws._table.isRowHidden(r)]
    assert len(visible) == 2
    assert "AI && ML  2" == ws._tabs.tabText(1)

    for row in visible:
        if ws._table.item(row, 3).text() == "domain":
            ws._table.selectRow(row)
    app.processEvents()
    assert ws._delete_btn.isEnabled()
    assert ws._impact._tree.topLevelItemCount() == 1
    assert ws._impact._tree.topLevelItem(0).childCount() == 1

    ws._table.selectAll()
    app.processEvents()
    assert not ws._delete_btn.isEnabled()  # locked provisioned throughput is selected

    ws._search.setText("web")
    ws._tabs.setCurrentIndex(0)
    visible = [r for r in range(ws._table.rowCount()) if not ws._table.isRowHidden(r)]
    assert len(visible) == 1


def test_disconnect_resets_workspace(window):
    ws = window.workspace(CloudProvider.AZURE)
    session = ProviderSession(CloudProvider.AZURE, object(), "sub", "Subscription: x")
    ws._session = session
    ws.connect_panel.set_connected(ConnectResult(session))
    ws.disconnect()
    assert not ws.connected
    assert ws._stack.currentIndex() == 0
