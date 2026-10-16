"""Code run on every open and future panel of some kinds: the sciqlop.panel_extensions extension point (plan 2g)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from PySide6.QtWidgets import QWidget

from SciQLop.core.extensions import ExtensionPoint, declare


@dataclass(frozen=True)
class PanelExtension:
    id: str
    attach: Callable[[QWidget], Optional[Callable[[], None]]]  # (panel) -> its clean-up, or None
    kinds: tuple[str, ...] = ()                                # () = every panel kind


PANEL_EXTENSIONS = declare(ExtensionPoint("sciqlop.panel_extensions", PanelExtension, what="panel extension",
                                          doc="Code run on every open and future panel of some kinds, "
                                              "with a clean-up."))
