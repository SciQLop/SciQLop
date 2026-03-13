from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable
from PySide6.QtGui import QIcon


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


class CommandRegistry:
    def __init__(self):
        self._commands: dict[str, PaletteCommand] = {}

    def register(self, command: PaletteCommand) -> None:
        self._commands[command.id] = command

    def unregister(self, command_id: str) -> None:
        self._commands.pop(command_id, None)

    def commands(self) -> list[PaletteCommand]:
        return list(self._commands.values())

    def get(self, command_id: str) -> PaletteCommand | None:
        return self._commands.get(command_id)
