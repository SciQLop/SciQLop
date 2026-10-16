"""Quickstart shortcuts on the welcome page: the sciqlop.quickstart extension point (Tier 3 spec §3.1)."""
from __future__ import annotations

from dataclasses import dataclass
from operator import attrgetter
from typing import Any, Callable

from SciQLop.core.extensions import ExtensionPoint, declare


@dataclass(frozen=True)
class QuickstartShortcut:
    name: str
    description: str
    icon: Any  # QIcon, QPixmap or None
    callback: Callable[[], Any]

    def as_dict(self) -> dict:
        return {"name": self.name, "description": self.description, "icon": self.icon, "callback": self.callback}


QUICKSTART = declare(ExtensionPoint("sciqlop.quickstart", QuickstartShortcut, what="quickstart shortcut",
                                    key=attrgetter("name"), doc="Welcome-page quickstart shortcuts by name."))


def contribute_shortcut(shortcut: QuickstartShortcut, owner: str) -> None:
    """From any thread: the owner is captured by the caller, since the owner context does not cross threads."""
    from SciQLop.user_api.threading import on_main_thread
    on_main_thread(QUICKSTART.contribute)(shortcut, owner=owner)
