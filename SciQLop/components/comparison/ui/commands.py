"""Palette commands and menu entries that open the Compare dialog."""
from __future__ import annotations

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.menus import CATALOG_EVENTS, MAIN_TOOLS, MENUS, PANEL, MenuEntry

log = getLogger(__name__)

COMPARE, COMPARE_EVENTS = "sciqlop.compare", "sciqlop.compare_events"


def _main_window():
    from SciQLop.core.sciqlop_application import sciqlop_app
    return sciqlop_app().main_window


def open_compare_dialog(panel: str = ""):
    from SciQLop.components.comparison.ui.wizard import CompareDialog
    dialog = CompareDialog(_main_window(), base_panel=panel or None)
    dialog.show()
    return dialog


def _picked_events(catalog, events: str) -> list:
    wanted = set(filter(None, events.split(",")))
    return sorted((e for e in catalog.provider.events(catalog) if e.uuid in wanted), key=lambda e: e.start)


def _base_of(showing: list[str]) -> dict:
    """One panel shows the catalog: it is the base; several: the user picks among them; none: among all panels."""
    if len(showing) == 1:
        return {"base_panel": showing[0]}
    return {"base_choices": showing} if showing else {}


def open_compare_events(catalog: str = "", events: str = ""):
    """The first event (by start) is the base time range, the others are the variants (spec §3.3)."""
    from SciQLop.components.catalogs.backend.panel_manager import panels_showing
    from SciQLop.components.command_palette.arg_types import resolve_catalog_arg
    from SciQLop.components.comparison.ui.pickers import time_variant
    from SciQLop.components.comparison.ui.wizard import CompareDialog
    resolved = resolve_catalog_arg(catalog)
    picked = _picked_events(resolved, events) if resolved is not None and resolved.provider is not None else []
    if len(picked) < 2:
        log.warning("select at least two events to compare")
        return None
    win = _main_window()
    showing = [p.name for p in panels_showing(win, resolved.provider.name, resolved.uuid)]
    first = picked[0]
    dialog = CompareDialog(win, preset=("time", [time_variant(e) for e in picked[1:]]),
                           base_range=(first.start.timestamp(), first.stop.timestamp()), **_base_of(showing))
    dialog.show()
    return dialog


def _open_time_panel(context: dict) -> bool:
    win = _main_window()
    return win is not None and win.plot_panel(context.get("panel", "")) is not None


def _two_events(context: dict) -> bool:
    return len(context.get("events", "").split(",")) >= 2


def _entries() -> list[MenuEntry]:
    return [MenuEntry("sciqlop.compare.tools", MAIN_TOOLS, COMPARE, label="Compare…"),
            MenuEntry("sciqlop.compare.panel", PANEL, COMPARE, label="Compare with…", when=_open_time_panel),
            MenuEntry("sciqlop.compare_events.catalog", CATALOG_EVENTS, COMPARE_EVENTS, label="Compare",
                      when=_two_events)]


def register_comparison_commands(registry) -> None:
    from SciQLop.components.command_palette.arg_types import CatalogArg, EventsArg, PanelArg
    from SciQLop.components.command_palette.backend.registry import PaletteCommand
    import SciQLop.components.comparison.ui.panel_kind  # noqa: F401  the core dimensions the dialog lists
    registry.register(PaletteCommand(
        id=COMPARE, name="Compare plots", description="Compare a panel across events, products or settings.",
        callback=open_compare_dialog, args=[PanelArg()], keywords=["comparison", "overlay", "difference"]))
    registry.register(PaletteCommand(
        id=COMPARE_EVENTS, name="Compare catalog events",
        description="Compare a panel across catalog events: the first event is the base.",
        callback=open_compare_events, args=[CatalogArg(), EventsArg()], keywords=["comparison"]))
    for entry in _entries():
        MENUS.contribute(entry, owner="sciqlop", replace=True)
