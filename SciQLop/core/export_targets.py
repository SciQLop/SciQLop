"""File formats a panel can be saved to: the sciqlop.export_targets extension point (spec §4.3)."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Optional

from SciQLop.core.extensions import ExtensionPoint, declare


@dataclass(frozen=True)
class ExportTarget:
    id: str
    label: str
    suffixes: tuple
    write: Callable  # (user_api PlotPanel, path, width, height, scale or None) -> None; raises on failure
    scalable: bool = True

    def __post_init__(self):
        if not self.suffixes or any(not s.startswith(".") or s != s.lower() for s in self.suffixes):
            raise ValueError(f"export target {self.id}: suffixes must be lowercase and start with '.', "
                             f"got {self.suffixes!r}")


EXPORT_TARGETS = declare(ExtensionPoint("sciqlop.export_targets", ExportTarget, what="export target",
                                        doc="File formats for PlotPanel.save and the panel Export menu."))


def _precedence(target: ExportTarget):
    return EXPORT_TARGETS.owner_of(target.id) != "sciqlop", target.id


def target_for(path: str) -> Optional[ExportTarget]:
    suffix = os.path.splitext(path)[1].lower()
    claimants = sorted((t for t in EXPORT_TARGETS.list() if suffix in t.suffixes), key=_precedence)
    return claimants[0] if claimants else None


def known_suffixes() -> list:
    return sorted({s for t in EXPORT_TARGETS.list() for s in t.suffixes})
