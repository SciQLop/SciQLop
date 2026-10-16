"""Kinds of panels a main window can open: the sciqlop.panel_kinds extension point (plan 2g)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtWidgets import QWidget

from SciQLop.core.extensions import ExtensionPoint, declare

KIND_PROPERTY = "sciqlop_panel_kind"
# The description of the template a panel was opened from, so saving the panel again keeps it.
DESCRIPTION_PROPERTY = "sciqlop_panel_description"


@dataclass(frozen=True)
class PanelKind:
    id: str
    label: str
    create: Callable[[str, dict], QWidget]                  # (name, config) -> widget; config is {} for a new panel
    to_config: Optional[Callable[[QWidget], dict]] = None   # None: this kind cannot be saved
    icon: Optional[str] = None                              # registered icon name or file path
    in_new_menu: bool = True

    def __post_init__(self):
        if not self.id or not self.label:
            raise ValueError(f"a panel kind needs an id and a label, got id={self.id!r}, label={self.label!r}")


PANEL_KINDS = declare(ExtensionPoint("sciqlop.panel_kinds", PanelKind, what="panel kind",
                                     doc="Kinds of panels a main window can open, save and restore."))


def panel_kind_of(widget: QWidget) -> Optional[str]:
    return widget.property(KIND_PROPERTY)
