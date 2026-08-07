"""Re-opening the JupyterLab dock must go back through jupyqt.

Lab's File menu can shut its own server down ("Shut Down") or navigate the view
to a non-existent /logout page ("Log Out"). jupyqt relaunches the server and
reloads the page when the widget is requested again, so an early return that
merely raises the existing dock leaves the user stuck on a dead panel with no
way to recover — SciQLop/jupyqt#10.
"""
import pytest
from PySide6.QtWidgets import QWidget

from tests.fixtures import *  # noqa: F401,F403 — pytest fixtures


class _FakeWorkspacesManager:
    """Counts widget() calls; hands back one stable widget like jupyqt does."""

    def __init__(self):
        self.widget_calls = 0
        self._widget = QWidget()
        self._widget.setWindowTitle("SciQLop JupyterLab")

    def widget(self):
        self.widget_calls += 1
        return self._widget


@pytest.fixture
def fake_wm(monkeypatch):
    wm = _FakeWorkspacesManager()
    monkeypatch.setattr(
        "SciQLop.core.ui.mainwindow.workspaces_manager_instance", lambda: wm,
    )
    return wm


def test_first_open_docks_the_lab_widget(qtbot, main_window, fake_wm):
    main_window.open_jupyterlab_widget()

    assert fake_wm.widget_calls == 1
    assert main_window.dock_manager.findDockWidget("SciQLop JupyterLab") is not None


def test_reopening_an_existing_dock_still_asks_jupyqt_for_the_widget(
    qtbot, main_window, fake_wm,
):
    main_window.open_jupyterlab_widget()
    main_window.open_jupyterlab_widget()

    assert fake_wm.widget_calls == 2, (
        "re-opening must reach jupyqt so a shut-down server is relaunched"
    )
    assert main_window.dock_manager.findDockWidget("SciQLop JupyterLab") is not None
