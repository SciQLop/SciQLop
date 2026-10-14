from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable
from PySide6.QtGui import QIcon

from SciQLop.core.extensions import ExtensionPoint, declare
from SciQLop.user_api.threading import on_main_thread


@dataclass
class Completion:
    value: str
    display: str
    description: str | None = None
    icon: QIcon | None = None


@dataclass
class CommandArg(ABC):
    name: str

    @abstractmethod
    def completions(self, context: dict) -> list[Completion]: ...

    def filtered_completions(self, query: str, context: dict, max_results: int) -> list[Completion] | None:
        """Return pre-filtered completions, or None to use default Python fuzzy matching."""
        return None


@dataclass
class PaletteCommand:
    id: str
    name: str
    description: str
    callback: Callable
    args: list[CommandArg] = field(default_factory=list)
    icon: QIcon | None = None
    keywords: list[str] = field(default_factory=list)
    replaces_qaction: str | None = None


COMMANDS = declare(ExtensionPoint("sciqlop.commands", PaletteCommand, what="command",
                                  doc="Commands of the command palette; menu entries place them in menus."))


class CommandRegistry:
    """The published registry API, a view onto sciqlop.commands: every instance sees the same commands."""

    @on_main_thread
    def register(self, command: PaletteCommand) -> None:
        COMMANDS.contribute(command, replace=True)

    @on_main_thread
    def unregister(self, command_id: str) -> None:
        if command_id in COMMANDS:
            COMMANDS.remove(command_id)

    def commands(self) -> list[PaletteCommand]:
        return COMMANDS.list()

    def get(self, command_id: str) -> PaletteCommand | None:
        return COMMANDS.get(command_id) if command_id in COMMANDS else None
