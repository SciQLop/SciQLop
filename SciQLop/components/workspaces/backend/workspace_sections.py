"""Plugin-owned tables of a .sciqlop workspace file: the sciqlop.workspace_sections extension point.

Lives apart from workspace_manifest because declaring an extension point imports Qt, and the thin
launcher imports the manifest without it. The manifest imports this module lazily.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from operator import attrgetter

from pydantic import BaseModel

from SciQLop.core.extensions import ExtensionPoint, declare

_BARE_KEY = re.compile(r"[A-Za-z0-9_-]+")


@dataclass(frozen=True)
class WorkspaceSection:
    table: str
    model: type[BaseModel]

    def __post_init__(self):
        from SciQLop.components.workspaces.backend.workspace_manifest import _KNOWN_TABLES
        if self.table in _KNOWN_TABLES:
            raise ValueError(f"workspace section {self.table!r}: that table belongs to SciQLop")
        if not _BARE_KEY.fullmatch(self.table):
            raise ValueError(f"workspace section {self.table!r}: not a valid bare TOML key ([A-Za-z0-9_-]+)")


WORKSPACE_SECTIONS = declare(ExtensionPoint("sciqlop.workspace_sections", WorkspaceSection,
                                            what="workspace section", key=attrgetter("table"),
                                            doc="Plugin-owned tables of a .sciqlop workspace file."))
