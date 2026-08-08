"""Tests for screenshot-automation helpers in SciQLop.user_api."""
import pytest


@pytest.fixture
def panel(qtbot, main_window):
    from SciQLop.user_api.plot import create_plot_panel
    p = create_plot_panel()
    yield p
    try:
        p.close()
    except Exception:
        pass


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


def test_capture_panel_creates_png(qtbot, panel, tmp_path):
    from SciQLop.user_api.screenshot import capture_panel

    path = tmp_path / "panel.png"
    result = capture_panel(panel, path)
    assert result == path
    assert path.exists()
    assert path.stat().st_size > 0
