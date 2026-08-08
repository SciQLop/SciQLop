from tests.fixtures import *  # noqa: F401,F403 — qapp/main_window/qtbot fixtures


def test_panel_close_removes_panel(qtbot, main_window):
    from SciQLop.user_api.plot import create_plot_panel, plot_panel

    panel = create_plot_panel()
    name = panel.name
    assert plot_panel(name) is not None

    panel.close()
    qtbot.waitUntil(lambda: plot_panel(name) is None, timeout=2000)


def test_panel_is_busy_false_when_idle(qtbot, main_window):
    from SciQLop.user_api.plot import create_plot_panel

    panel = create_plot_panel()
    assert not panel.is_busy()


def test_wait_for_data_returns_true_when_idle(qtbot, main_window):
    from SciQLop.user_api.plot import create_plot_panel

    panel = create_plot_panel()
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
