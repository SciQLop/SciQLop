"""Sections plugins add to the inspector of panels, plots and graphs: the sciqlop.inspector_sections extension point."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from SciQLop.core.extensions import ExtensionPoint, declare

PANEL_TARGET, PLOT_TARGET, GRAPH_TARGET = "panel", "plot", "graph"
TARGETS = (PANEL_TARGET, PLOT_TARGET, GRAPH_TARGET)


def _always(obj: Any) -> bool:
    return True


@dataclass(frozen=True)
class InspectorSection:
    id: str
    title: str
    target: str                                  # one of TARGETS
    build: Callable[[Any, Any], Any]             # build(user_api object, parent QWidget) -> QWidget
    applies: Callable[[Any], bool] = _always     # applies(user_api object)
    priority: int = 0

    def __post_init__(self):
        if self.target not in TARGETS:
            raise ValueError(f"inspector section {self.id}: target must be one of {TARGETS}, got {self.target!r}")
        if not isinstance(self.priority, int):
            raise TypeError(f"inspector section {self.id}: priority must be an int, got {self.priority!r}")


INSPECTOR_SECTIONS = declare(ExtensionPoint(
    "sciqlop.inspector_sections", InspectorSection, what="inspector section",
    doc="Sections in the inspector of panels, plots or graphs: build(obj, parent), applies(obj) and priority."))
