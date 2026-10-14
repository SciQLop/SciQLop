"""Where commands appear in menus: the sciqlop.menus extension point (spec §4.3; menus follow VS Code)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from SciQLop.core.extensions import ExtensionPoint, declare

PANEL, PANEL_EXPORT, GRAPH = "panel", "panel.export", "graph"
PRODUCT_TREE, CATALOG_TREE, MAIN_TOOLS = "product_tree", "catalog_tree", "main.tools"


def _always(context: dict) -> bool:
    return True


@dataclass(frozen=True)
class MenuEntry:
    id: str
    location: str                      # one of the location constants above
    command: str                       # a sciqlop.commands id
    label: Optional[str] = None        # None: the command's name
    when: Callable[[dict], bool] = _always
    order: int = 0

    def __post_init__(self):
        if not isinstance(self.order, int):
            raise TypeError(f"menu entry {self.id}: order must be an int, got {self.order!r}")


MENUS = declare(ExtensionPoint("sciqlop.menus", MenuEntry, what="menu entry",
                               doc="Commands placed in menus: location, label, order and a when(context) predicate."))
