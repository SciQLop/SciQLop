from tests.fixtures import *  # noqa: F401,F403 — qapp/main_window/qtbot fixtures


def test_panel_close_removes_panel(qtbot, main_window):
    from SciQLop.user_api.plot import create_plot_panel, plot_panel

    panel = create_plot_panel()
    name = panel.name
    assert plot_panel(name) is not None

    panel.close()
    qtbot.waitUntil(lambda: plot_panel(name) is None, timeout=2000)
