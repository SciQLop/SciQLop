"""Docks and side panes: the sciqlop.docks extension point (spec §4). Every main window follows it."""
from __future__ import annotations

import weakref
from dataclasses import dataclass
from typing import Callable, Optional

import shiboken6

from SciQLop.core.extensions import ExtensionPoint, declare

PLACEMENTS = ("center", "left", "right", "bottom")


@dataclass(frozen=True)
class Dock:
    id: str
    title: str
    build: Callable  # () -> QWidget, called once per main window that places the dock
    placement: str = "center"
    icon: Optional[str] = None  # a registered icon name or an image file path
    visible: bool = True
    toolbar: bool = False

    def __post_init__(self):
        if self.placement not in PLACEMENTS:
            raise ValueError(f"dock {self.id}: placement must be one of {PLACEMENTS}, got {self.placement!r}")


class _ExistingWidget:
    """The `build` of a dock made by `SciQLopMainWindow.add_side_pan`: a widget that already exists,
    placed only in the window (`host`) that docked it."""

    def __init__(self, widget, host):
        self.widget, self.host = widget, weakref.ref(host)

    def __call__(self):
        return self.widget

    def alive(self) -> bool:
        return shiboken6.isValid(self.widget)


DOCKS = declare(ExtensionPoint("sciqlop.docks", Dock, what="dock", doc="Docks and side panes by id."))
