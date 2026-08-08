"""Tests for screenshot-automation helpers in SciQLop.user_api."""
import pytest
from tests.fixtures import *  # noqa: F401, F403


@pytest.fixture
def panel(qtbot, main_window):
    from SciQLop.user_api.plot import create_plot_panel
    p = create_plot_panel()
    yield p
    try:
        p.close()
    except ValueError as exc:
        if "The plot panel does not exist anymore." not in str(exc):
            raise


def test_panel_close_removes_panel(qtbot, main_window):
    from SciQLop.user_api.plot import create_plot_panel, plot_panel

    p = create_plot_panel()
    name = p.name
    assert plot_panel(name) is not None

    p.close()
    qtbot.waitUntil(lambda: plot_panel(name) is None, timeout=2000)


def test_panel_is_busy_false_when_idle(panel):
    assert not panel.is_busy()


def test_wait_for_data_returns_true_when_idle(panel):
    assert panel.wait_for_data(timeout=1.0) is True


def test_show_product_tree_raises_dock(qtbot, main_window):
    from SciQLop.user_api.gui import show_product_tree

    show_product_tree()
    qtbot.wait(50)
    dw = main_window.dock_manager.findDockWidget("Products")
    assert dw is not None
    assert dw.isVisible()


def test_show_inspector_raises_dock(qtbot, main_window):
    from SciQLop.user_api.gui import show_inspector

    show_inspector()
    qtbot.wait(50)
    dw = main_window.dock_manager.findDockWidget("Properties")
    assert dw is not None
    assert dw.isVisible()


def test_capture_window_creates_png(qtbot, main_window, tmp_path):
    from SciQLop.user_api.screenshot import capture_window

    path = tmp_path / "window.png"
    result = capture_window(path)
    assert result == path
    assert path.exists()
    assert path.stat().st_size > 0


def test_capture_panel_creates_png(panel, tmp_path):
    from SciQLop.user_api.screenshot import capture_panel

    path = tmp_path / "panel.png"
    result = capture_panel(panel, path)
    assert result == path
    assert path.exists()
    assert path.stat().st_size > 0


class _GraphMock:
    def __init__(self, busy: bool = False):
        self._busy = busy

    def property(self, name: str):
        if name == "busy":
            return self._busy
        return None


class _PlotMock:
    def __init__(self, graphs):
        self._graphs = graphs

    def plottables(self):
        return self._graphs


class _ImplMock:
    def __init__(self, plots):
        self._plots = plots

    def plots(self):
        return self._plots


@pytest.fixture
def busy_panel():
    """A PlotPanel whose single graph reports busy=True (Qt-free)."""
    from SciQLop.user_api.plot import PlotPanel

    panel = PlotPanel.__new__(PlotPanel)
    panel._impl = _ImplMock([_PlotMock([_GraphMock(busy=True)])])
    return panel


def test_panel_is_busy_true_when_graph_busy(busy_panel):
    assert busy_panel.is_busy() is True


def test_wait_for_data_returns_false_when_busy_timeout(busy_panel, monkeypatch):
    from PySide6.QtCore import QCoreApplication

    monkeypatch.setattr(QCoreApplication, "processEvents", lambda *args, **kwargs: None)
    assert busy_panel.wait_for_data(timeout=0.05, poll_interval=0.001) is False
