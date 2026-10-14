"""Menu entries (spec §4.3): a registered command placed at a menu location, filtered by when(context)."""
import pytest
from PySide6.QtWidgets import QMenu

from SciQLop.components.command_palette.arg_types import PanelArg, ProductArg
from SciQLop.components.command_palette.backend.registry import COMMANDS, PaletteCommand
from SciQLop.components.command_palette.menu_entries import add_menu_entries
from SciQLop.core.extensions import owned_by
from SciQLop.core.menus import MENUS, PANEL, PANEL_EXPORT, PRODUCT_TREE, MenuEntry


@pytest.fixture
def demo(qapp):
    calls = []
    with owned_by("mn_demo"):
        COMMANDS.contribute(PaletteCommand(id="mn_demo.zoom", name="Zoom to event", description="",
                                           callback=lambda panel="": calls.append(panel), args=[PanelArg("panel")]))
    yield calls
    MENUS.remove_owner("mn_demo")
    COMMANDS.remove_owner("mn_demo")


def _texts(actions):
    return [a.text() for a in actions]


def test_an_entry_runs_its_command_with_the_context_values_it_names(demo):
    with owned_by("mn_demo"):
        MENUS.contribute(MenuEntry("mn_demo.zoom_entry", PANEL, "mn_demo.zoom"))
    menu = QMenu()
    actions = add_menu_entries(menu, PANEL, {"panel": "Panel 1", "unused": 3})
    assert _texts(actions) == ["Zoom to event"]
    actions[0].trigger()
    assert demo == ["Panel 1"]


def test_label_order_and_location(demo):
    with owned_by("mn_demo"):
        MENUS.contribute(MenuEntry("mn_demo.b", PANEL, "mn_demo.zoom", label="Second", order=2))
        MENUS.contribute(MenuEntry("mn_demo.a", PANEL, "mn_demo.zoom", label="First", order=1))
        MENUS.contribute(MenuEntry("mn_demo.c", PRODUCT_TREE, "mn_demo.zoom", label="Elsewhere"))
    assert _texts(add_menu_entries(QMenu(), PANEL, {})) == ["First", "Second"]


def test_when_filters_and_a_raising_when_is_skipped(demo):
    def boom(context):
        raise RuntimeError("bad predicate")

    with owned_by("mn_demo"):
        MENUS.contribute(MenuEntry("mn_demo.only_p1", PANEL, "mn_demo.zoom", label="Only P1",
                                   when=lambda c: c.get("panel") == "P1"))
        MENUS.contribute(MenuEntry("mn_demo.broken", PANEL, "mn_demo.zoom", label="Broken", when=boom))
    assert _texts(add_menu_entries(QMenu(), PANEL, {"panel": "P2"})) == []
    assert _texts(add_menu_entries(QMenu(), PANEL, {"panel": "P1"})) == ["Only P1"]


def test_an_entry_whose_command_is_gone_is_left_out(demo):
    with owned_by("mn_demo"):
        MENUS.contribute(MenuEntry("mn_demo.orphan", PANEL, "mn_gone.command", label="Orphan"))
    assert _texts(add_menu_entries(QMenu(), PANEL, {})) == []


def test_the_panel_context_menu_shows_entries(qtbot, demo):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    with owned_by("mn_demo"):
        MENUS.contribute(MenuEntry("mn_demo.in_panel", PANEL, "mn_demo.zoom", label="From a plugin"))
    panel = TimeSyncPanel("mn_panel", show_search_overlay=False)
    qtbot.addWidget(panel)
    menu = panel._build_context_menu()
    assert "From a plugin" in [a.text() for a in menu.actions()]


def test_the_export_submenu_shows_entries_with_the_panel_name(qtbot, demo):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    with owned_by("mn_demo"):
        MENUS.contribute(MenuEntry("mn_demo.in_export", PANEL_EXPORT, "mn_demo.zoom", label="Export extra"))
    panel = TimeSyncPanel("mn_panel_export", show_search_overlay=False)
    qtbot.addWidget(panel)
    menu = QMenu()
    panel._build_export_share_menu(menu)
    export = next(a.menu() for a in menu.actions() if a.text() == "Export")
    extra = next(a for a in export.actions() if a.text() == "Export extra")
    extra.trigger()
    assert demo == [panel.windowTitle()]


def test_the_product_menu_shows_entries_with_the_product_path(qtbot, demo):
    from SciQLop.components.products.product_context_menu import build_product_menu

    class _NoWindow:
        def plot_panels(self):
            return []

    with owned_by("mn_demo"):
        COMMANDS.contribute(PaletteCommand(id="mn_demo.prod", name="Prod cmd", description="",
                                           callback=lambda product="": demo.append(product),
                                           args=[ProductArg()]))
        MENUS.contribute(MenuEntry("mn_demo.in_tree", PRODUCT_TREE, "mn_demo.prod"))
    menu = build_product_menu(None, ["amda", "ace", "b"], _NoWindow())
    next(a for a in menu.actions() if a.text() == "Prod cmd").trigger()
    assert demo == ["amda//ace//b"]


def test_the_panel_value_follows_a_rename(qtbot, demo):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    with owned_by("mn_demo"):
        MENUS.contribute(MenuEntry("mn_demo.renamed", PANEL, "mn_demo.zoom", label="After rename"))
    panel = TimeSyncPanel("mn_panel_old", show_search_overlay=False)
    qtbot.addWidget(panel)
    panel.setObjectName("Renamed")
    menu = panel._build_context_menu()
    next(a for a in menu.actions() if a.text() == "After rename").trigger()
    assert demo == ["Renamed"]
