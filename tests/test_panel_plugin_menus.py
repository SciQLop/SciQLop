"""Plugins add their own submenus to the plot panel's context menu."""
from .fixtures import *  # noqa: F401, F403

import pytest


@pytest.fixture
def panel(qtbot, qapp):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    return TimeSyncPanel("plugin-menu-panel")


@pytest.fixture
def registered():
    from SciQLop.user_api.plot import unregister_panel_menu
    titles = []
    yield titles
    for title in titles:
        unregister_panel_menu(title)


def _submenu(menu, title):
    return next((a.menu() for a in menu.actions() if a.menu() is not None and a.text() == title), None)


def test_registered_menu_lists_its_entries_and_runs_them_on_this_panel(panel, registered):
    from SciQLop.user_api.plot import register_panel_menu
    picked = []
    register_panel_menu("Flybys", lambda p: [("Mercury 1", lambda: picked.append(p))])
    registered.append("Flybys")

    menu = panel._build_context_menu()
    flybys = _submenu(menu, "Flybys")

    (entry,) = flybys.actions()
    assert entry.text() == "Mercury 1"
    entry.trigger()
    assert picked[0]._get_impl_or_raise() is panel


def test_a_failing_plugin_menu_does_not_break_the_others(panel, registered):
    from SciQLop.user_api.plot import register_panel_menu

    def broken(p):
        raise RuntimeError("plugin bug")

    register_panel_menu("Broken", broken)
    register_panel_menu("Fine", lambda p: [("ok", lambda: None)])
    registered.extend(["Broken", "Fine"])

    menu = panel._build_context_menu()

    assert _submenu(menu, "Broken") is None
    assert _submenu(menu, "Fine") is not None


def test_unregistered_or_empty_menus_are_not_shown(panel, registered):
    from SciQLop.user_api.plot import register_panel_menu, unregister_panel_menu
    register_panel_menu("Gone", lambda p: [("x", lambda: None)])
    register_panel_menu("Empty", lambda p: [])
    registered.append("Empty")
    unregister_panel_menu("Gone")

    menu = panel._build_context_menu()

    assert _submenu(menu, "Gone") is None
    assert _submenu(menu, "Empty") is None
