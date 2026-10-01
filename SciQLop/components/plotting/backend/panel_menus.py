"""Submenus that plugins add to the plot panel's context menu."""
from typing import Callable

from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)

# (user_api PlotPanel) -> [(label, callback), ...], called each time the menu opens
PanelMenuEntries = Callable[[object], list]

_menus: dict[str, PanelMenuEntries] = {}


def register(title: str, entries: PanelMenuEntries) -> None:
    _menus[title] = entries


def unregister(title: str) -> None:
    _menus.pop(title, None)


def add_plugin_menus(menu, panel) -> None:
    from PySide6.QtWidgets import QMenu
    from SciQLop.user_api.plot import PlotPanel

    wrapper = PlotPanel(panel)
    for title, entries in list(_menus.items()):
        try:
            items = list(entries(wrapper))
        except Exception:
            log.error("Panel menu %r failed to list its entries", title, exc_info=True)
            continue
        if not items:
            continue
        sub = QMenu(title, menu)
        menu.addMenu(sub)
        for label, callback in items:
            sub.addAction(label, callback)
