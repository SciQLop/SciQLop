# Command Palette Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a keyboard-driven command palette (Ctrl+K) to SciQLop with fuzzy search, multi-step argument chains, LRU history, and QAction auto-harvest.

**Architecture:** Pure Qt widget overlay (QLineEdit + QListView) parented to main window. Central `CommandRegistry` on `SciQLopApp` stores commands. Plugins register rich commands; QActions are auto-harvested as argless commands. LRU history persisted to JSON.

**Tech Stack:** PySide6 (QWidget, QLineEdit, QListView, QStyledItemDelegate, QShortcut, QGraphicsDropShadowEffect), Pydantic (ConfigEntry for settings), JSON (history persistence).

**Spec:** `docs/superpowers/specs/2026-03-13-command-palette-design.md`

---

## Chunk 1: Backend Core (Data Model + Registry + Fuzzy + History)

### Task 1: Data Model — PaletteCommand, Completion, CommandArg

**Files:**
- Create: `SciQLop/components/command_palette/__init__.py`
- Create: `SciQLop/components/command_palette/backend/__init__.py`
- Create: `SciQLop/components/command_palette/backend/registry.py`
- Test: `tests/test_command_palette_registry.py`

- [ ] **Step 1: Write failing test for PaletteCommand and Completion**

```python
# tests/test_command_palette_registry.py
from tests.fixtures import *


def test_palette_command_creation():
    from SciQLop.components.command_palette.backend.registry import (
        PaletteCommand, Completion, CommandArg,
    )

    called_with = {}

    def callback(**kwargs):
        called_with.update(kwargs)

    cmd = PaletteCommand(
        id="test.cmd",
        name="Test Command",
        description="A test",
        callback=callback,
        args=[],
    )
    assert cmd.id == "test.cmd"
    assert cmd.name == "Test Command"
    assert cmd.args == []
    assert cmd.icon is None
    assert cmd.keywords == []
    assert cmd.replaces_qaction is None


def test_completion_creation():
    from SciQLop.components.command_palette.backend.registry import Completion

    c = Completion(value="v1", display="Value 1", description="desc")
    assert c.value == "v1"
    assert c.display == "Value 1"
    assert c.description == "desc"
    assert c.icon is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_command_palette_registry.py -v`
Expected: FAIL with ImportError (module doesn't exist yet)

- [ ] **Step 3: Create package structure and data model**

```python
# SciQLop/components/command_palette/__init__.py
```

```python
# SciQLop/components/command_palette/backend/__init__.py
```

```python
# SciQLop/components/command_palette/backend/registry.py
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
    def completions(self, context: dict) -> list[Completion]:
        ...


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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_command_palette_registry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/command_palette/ tests/test_command_palette_registry.py
git commit -m "feat(command_palette): add data model — PaletteCommand, Completion, CommandArg"
```

---

### Task 2: CommandRegistry — register, unregister, commands

**Files:**
- Modify: `SciQLop/components/command_palette/backend/registry.py`
- Test: `tests/test_command_palette_registry.py`

- [ ] **Step 1: Write failing tests for registry**

Append to `tests/test_command_palette_registry.py`:

```python
def test_registry_register_and_list():
    from SciQLop.components.command_palette.backend.registry import (
        CommandRegistry, PaletteCommand,
    )

    registry = CommandRegistry()
    cmd = PaletteCommand(
        id="test.hello", name="Hello", description="Say hello",
        callback=lambda: None, args=[],
    )
    registry.register(cmd)
    assert "test.hello" in [c.id for c in registry.commands()]


def test_registry_unregister():
    from SciQLop.components.command_palette.backend.registry import (
        CommandRegistry, PaletteCommand,
    )

    registry = CommandRegistry()
    cmd = PaletteCommand(
        id="test.bye", name="Bye", description="Say bye",
        callback=lambda: None, args=[],
    )
    registry.register(cmd)
    registry.unregister("test.bye")
    assert "test.bye" not in [c.id for c in registry.commands()]


def test_registry_duplicate_id_raises():
    from SciQLop.components.command_palette.backend.registry import (
        CommandRegistry, PaletteCommand,
    )

    registry = CommandRegistry()
    cmd = PaletteCommand(
        id="test.dup", name="Dup", description="dup",
        callback=lambda: None,
    )
    registry.register(cmd)
    import pytest
    with pytest.raises(ValueError):
        registry.register(cmd)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_command_palette_registry.py::test_registry_register_and_list tests/test_command_palette_registry.py::test_registry_unregister tests/test_command_palette_registry.py::test_registry_duplicate_id_raises -v`
Expected: FAIL with AttributeError (CommandRegistry doesn't exist)

- [ ] **Step 3: Implement CommandRegistry**

Add to the bottom of `SciQLop/components/command_palette/backend/registry.py`:

```python
class CommandRegistry:
    def __init__(self):
        self._commands: dict[str, PaletteCommand] = {}

    def register(self, command: PaletteCommand) -> None:
        if command.id in self._commands:
            raise ValueError(f"Command already registered: {command.id}")
        self._commands[command.id] = command

    def unregister(self, command_id: str) -> None:
        self._commands.pop(command_id, None)

    def commands(self) -> list[PaletteCommand]:
        return list(self._commands.values())

    def get(self, command_id: str) -> PaletteCommand | None:
        return self._commands.get(command_id)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_command_palette_registry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/command_palette/backend/registry.py tests/test_command_palette_registry.py
git commit -m "feat(command_palette): add CommandRegistry with register/unregister/commands"
```

---

### Task 3: Fuzzy Matching

**Files:**
- Create: `SciQLop/components/command_palette/backend/fuzzy.py`
- Test: `tests/test_command_palette_fuzzy.py`

- [ ] **Step 1: Write failing tests for fuzzy scoring**

```python
# tests/test_command_palette_fuzzy.py
from tests.fixtures import *


def test_exact_match_scores_highest():
    from SciQLop.components.command_palette.backend.fuzzy import fuzzy_score

    score_exact = fuzzy_score("plot", "plot")
    score_partial = fuzzy_score("plot", "plot product")
    assert score_exact > score_partial


def test_prefix_match_scores_higher_than_middle():
    from SciQLop.components.command_palette.backend.fuzzy import fuzzy_score

    score_prefix = fuzzy_score("plot", "plot product in panel")
    score_middle = fuzzy_score("plot", "new plot panel")
    assert score_prefix > score_middle


def test_word_boundary_bonus():
    from SciQLop.components.command_palette.backend.fuzzy import fuzzy_score

    score_boundary = fuzzy_score("np", "new panel")
    score_no_boundary = fuzzy_score("np", "snap")
    assert score_boundary > score_no_boundary


def test_no_match_returns_zero():
    from SciQLop.components.command_palette.backend.fuzzy import fuzzy_score

    assert fuzzy_score("xyz", "plot product") == 0


def test_case_insensitive():
    from SciQLop.components.command_palette.backend.fuzzy import fuzzy_score

    assert fuzzy_score("PLOT", "plot product") > 0


def test_fuzzy_match_positions():
    from SciQLop.components.command_palette.backend.fuzzy import fuzzy_match

    score, positions = fuzzy_match("np", "new panel")
    assert score > 0
    assert 0 in positions  # 'n' in 'new'
    assert 4 in positions  # 'p' in 'panel'


def test_empty_query_matches_everything():
    from SciQLop.components.command_palette.backend.fuzzy import fuzzy_score

    assert fuzzy_score("", "anything") > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_command_palette_fuzzy.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement fuzzy matching**

```python
# SciQLop/components/command_palette/backend/fuzzy.py
from __future__ import annotations


def _is_word_boundary(text: str, i: int) -> bool:
    if i == 0:
        return True
    prev = text[i - 1]
    curr = text[i]
    return prev in " _/-." or (prev.islower() and curr.isupper())


def fuzzy_match(query: str, text: str) -> tuple[int, list[int]]:
    if not query:
        return 1, []

    lower_query = query.lower()
    lower_text = text.lower()
    positions: list[int] = []
    score = 0
    qi = 0
    prev_match_idx = -2

    for ti in range(len(lower_text)):
        if qi < len(lower_query) and lower_text[ti] == lower_query[qi]:
            positions.append(ti)
            score += 1
            if _is_word_boundary(lower_text, ti):
                score += 5
            if ti == prev_match_idx + 1:
                score += 3
            if ti == qi:
                score += 2
            prev_match_idx = ti
            qi += 1

    if qi < len(lower_query):
        return 0, []

    return score, positions


def fuzzy_score(query: str, text: str) -> int:
    score, _ = fuzzy_match(query, text)
    return score
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_command_palette_fuzzy.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/command_palette/backend/fuzzy.py tests/test_command_palette_fuzzy.py
git commit -m "feat(command_palette): add fuzzy matching with word boundary and consecutive bonuses"
```

---

### Task 4: LRU History

**Files:**
- Create: `SciQLop/components/command_palette/backend/history.py`
- Test: `tests/test_command_palette_history.py`

- [ ] **Step 1: Write failing tests for LRU history**

```python
# tests/test_command_palette_history.py
import json
from tests.fixtures import *


def test_history_add_and_list(tmp_path):
    from SciQLop.components.command_palette.backend.history import LRUHistory

    h = LRUHistory(path=str(tmp_path / "history.json"), max_size=5)
    h.add("cmd.a", {"arg": "val"})
    h.add("cmd.b", {})
    entries = h.entries()
    assert len(entries) == 2
    assert entries[0].command_id == "cmd.b"  # most recent first
    assert entries[1].command_id == "cmd.a"


def test_history_lru_promotes_existing(tmp_path):
    from SciQLop.components.command_palette.backend.history import LRUHistory

    h = LRUHistory(path=str(tmp_path / "history.json"), max_size=5)
    h.add("cmd.a", {"arg": "1"})
    h.add("cmd.b", {})
    h.add("cmd.a", {"arg": "1"})  # same command+args, should promote
    entries = h.entries()
    assert len(entries) == 2
    assert entries[0].command_id == "cmd.a"  # promoted to front


def test_history_evicts_oldest(tmp_path):
    from SciQLop.components.command_palette.backend.history import LRUHistory

    h = LRUHistory(path=str(tmp_path / "history.json"), max_size=3)
    h.add("cmd.1", {})
    h.add("cmd.2", {})
    h.add("cmd.3", {})
    h.add("cmd.4", {})
    entries = h.entries()
    assert len(entries) == 3
    ids = [e.command_id for e in entries]
    assert "cmd.1" not in ids


def test_history_persists_to_disk(tmp_path):
    from SciQLop.components.command_palette.backend.history import LRUHistory

    path = str(tmp_path / "history.json")
    h1 = LRUHistory(path=path, max_size=5)
    h1.add("cmd.a", {"x": "1"})

    h2 = LRUHistory(path=path, max_size=5)
    entries = h2.entries()
    assert len(entries) == 1
    assert entries[0].command_id == "cmd.a"
    assert entries[0].resolved_args == {"x": "1"}


def test_history_handles_missing_file(tmp_path):
    from SciQLop.components.command_palette.backend.history import LRUHistory

    h = LRUHistory(path=str(tmp_path / "nonexistent.json"), max_size=5)
    assert h.entries() == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_command_palette_history.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement LRUHistory**

```python
# SciQLop/components/command_palette/backend/history.py
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field


@dataclass
class HistoryEntry:
    command_id: str
    resolved_args: dict[str, str] = field(default_factory=dict)
    timestamp: float = 0.0

    def _key(self) -> tuple:
        return (self.command_id, tuple(sorted(self.resolved_args.items())))


class LRUHistory:
    def __init__(self, path: str, max_size: int = 50):
        self._path = path
        self._max_size = max_size
        self._entries: list[HistoryEntry] | None = None

    def _load(self) -> list[HistoryEntry]:
        if self._entries is not None:
            return self._entries
        self._entries = []
        if os.path.exists(self._path):
            try:
                with open(self._path) as f:
                    raw = json.load(f)
                self._entries = [
                    HistoryEntry(
                        command_id=e["command_id"],
                        resolved_args=e.get("resolved_args", {}),
                        timestamp=e.get("timestamp", 0.0),
                    )
                    for e in raw
                ]
            except (json.JSONDecodeError, KeyError, TypeError):
                self._entries = []
        return self._entries

    def _save(self):
        entries = self._load()
        with open(self._path, "w") as f:
            json.dump(
                [
                    {
                        "command_id": e.command_id,
                        "resolved_args": e.resolved_args,
                        "timestamp": e.timestamp,
                    }
                    for e in entries
                ],
                f,
            )

    def add(self, command_id: str, resolved_args: dict[str, str]) -> None:
        entries = self._load()
        entry = HistoryEntry(
            command_id=command_id,
            resolved_args=resolved_args,
            timestamp=time.time(),
        )
        key = entry._key()
        entries[:] = [e for e in entries if e._key() != key]
        entries.insert(0, entry)
        if len(entries) > self._max_size:
            entries[:] = entries[: self._max_size]
        self._save()

    def entries(self) -> list[HistoryEntry]:
        return list(self._load())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_command_palette_history.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/command_palette/backend/history.py tests/test_command_palette_history.py
git commit -m "feat(command_palette): add LRU history with JSON persistence"
```

---

### Task 5: QAction Harvester

**Files:**
- Create: `SciQLop/components/command_palette/backend/harvester.py`
- Test: `tests/test_command_palette_harvester.py`

- [ ] **Step 1: Write failing tests for harvester**

```python
# tests/test_command_palette_harvester.py
from tests.fixtures import *


def test_harvest_menu_actions(qtbot, qapp):
    from PySide6.QtWidgets import QMainWindow, QMenu
    from PySide6.QtGui import QAction
    from SciQLop.components.command_palette.backend.registry import CommandRegistry
    from SciQLop.components.command_palette.backend.harvester import harvest_qactions

    win = QMainWindow()
    menu = QMenu("File", win)
    win.menuBar().addMenu(menu)
    action = QAction("Save", win)
    menu.addAction(action)

    registry = CommandRegistry()
    harvest_qactions(registry, win)

    ids = [c.id for c in registry.commands()]
    assert any("Save" in cid for cid in ids)


def test_harvest_skips_already_registered(qtbot, qapp):
    from PySide6.QtWidgets import QMainWindow, QMenu
    from PySide6.QtGui import QAction
    from SciQLop.components.command_palette.backend.registry import (
        CommandRegistry, PaletteCommand,
    )
    from SciQLop.components.command_palette.backend.harvester import harvest_qactions

    win = QMainWindow()
    menu = QMenu("File", win)
    win.menuBar().addMenu(menu)
    action = QAction("Save", win)
    menu.addAction(action)

    registry = CommandRegistry()
    registry.register(PaletteCommand(
        id="qaction.File.Save",
        name="Save (rich)",
        description="rich version",
        callback=lambda: None,
    ))
    harvest_qactions(registry, win)

    names = [c.name for c in registry.commands()]
    assert names.count("Save (rich)") == 1
    assert "Save" not in names


def test_harvest_skips_replaces_qaction(qtbot, qapp):
    from PySide6.QtWidgets import QMainWindow, QMenu
    from PySide6.QtGui import QAction
    from SciQLop.components.command_palette.backend.registry import (
        CommandRegistry, PaletteCommand,
    )
    from SciQLop.components.command_palette.backend.harvester import harvest_qactions

    win = QMainWindow()
    menu = QMenu("Tools", win)
    win.menuBar().addMenu(menu)
    action = QAction("Start jupyter console", win)
    menu.addAction(action)

    registry = CommandRegistry()
    registry.register(PaletteCommand(
        id="jupyter.console",
        name="Jupyter Console",
        description="Start console",
        callback=lambda: None,
        replaces_qaction="Start jupyter console",
    ))
    harvest_qactions(registry, win)

    names = [c.name for c in registry.commands()]
    assert "Start jupyter console" not in names
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_command_palette_harvester.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement harvester**

```python
# SciQLop/components/command_palette/backend/harvester.py
from __future__ import annotations

from PySide6.QtWidgets import QMainWindow, QMenu

from SciQLop.components.command_palette.backend.registry import (
    CommandRegistry,
    PaletteCommand,
)


def _collect_menu_actions(menu: QMenu, path: str) -> list[tuple[str, str, callable]]:
    results = []
    for action in menu.actions():
        if action.isSeparator():
            continue
        submenu = action.menu()
        if submenu:
            results.extend(_collect_menu_actions(submenu, f"{path}.{submenu.title()}"))
        elif action.text():
            action_id = f"qaction.{path}.{action.text()}"
            results.append((action_id, action.text(), action.trigger))
    return results


def _suppressed_texts(registry: CommandRegistry) -> set[str]:
    return {
        cmd.replaces_qaction
        for cmd in registry.commands()
        if cmd.replaces_qaction
    }


def harvest_qactions(registry: CommandRegistry, main_window: QMainWindow) -> None:
    suppressed = _suppressed_texts(registry)
    existing_ids = {cmd.id for cmd in registry.commands()}

    for action in main_window.menuBar().actions():
        menu = action.menu()
        if not menu:
            continue
        for action_id, text, trigger in _collect_menu_actions(menu, menu.title()):
            if action_id in existing_ids:
                continue
            if text in suppressed:
                continue
            registry.register(PaletteCommand(
                id=action_id,
                name=text,
                description=f"Menu: {menu.title()}",
                callback=trigger,
            ))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_command_palette_harvester.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/command_palette/backend/harvester.py tests/test_command_palette_harvester.py
git commit -m "feat(command_palette): add QAction harvester with dedup and replaces_qaction"
```

---

### Task 6: Settings — CommandPaletteSettings

**Files:**
- Create: `SciQLop/components/command_palette/settings.py`
- Test: `tests/test_command_palette_settings.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_command_palette_settings.py
from tests.fixtures import *


def test_command_palette_settings_defaults(tmp_path, monkeypatch):
    import SciQLop.components.settings.backend.entry as entry_mod
    monkeypatch.setattr(entry_mod, "SCIQLOP_CONFIG_DIR", str(tmp_path))

    from SciQLop.components.command_palette.settings import CommandPaletteSettings
    s = CommandPaletteSettings()
    assert s.keybinding == "Ctrl+K"
    assert s.max_history_size == 50
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_command_palette_settings.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement settings**

```python
# SciQLop/components/command_palette/settings.py
from typing import ClassVar

from SciQLop.components.settings.backend.entry import ConfigEntry, SettingsCategory


class CommandPaletteSettings(ConfigEntry):
    category: ClassVar[str] = SettingsCategory.APPLICATION
    subcategory: ClassVar[str] = "Command Palette"

    keybinding: str = "Ctrl+K"
    max_history_size: int = 50
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_command_palette_settings.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/command_palette/settings.py tests/test_command_palette_settings.py
git commit -m "feat(command_palette): add CommandPaletteSettings (keybinding, max_history_size)"
```

---

## Chunk 2: UI (Palette Widget + Delegate)

### Task 7: Item Delegate — rendering command/completion/history rows

**Files:**
- Create: `SciQLop/components/command_palette/ui/__init__.py`
- Create: `SciQLop/components/command_palette/ui/delegate.py`
- Test: `tests/test_command_palette_delegate.py`

- [ ] **Step 1: Write failing test for delegate**

```python
# tests/test_command_palette_delegate.py
from tests.fixtures import *


def test_delegate_instantiates(qtbot, qapp):
    from SciQLop.components.command_palette.ui.delegate import PaletteItemDelegate
    delegate = PaletteItemDelegate()
    assert delegate is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_command_palette_delegate.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement delegate**

The delegate renders each row with: icon (left) | name + highlighted match chars (bold) | description (dimmed, right-aligned) | category tag (small pill).

Data is passed via Qt.UserRole on the model items. The delegate reads:
- `Qt.DisplayRole` → name text
- `Qt.UserRole` → dict with keys: `description`, `match_positions` (list[int]), `category` (str, e.g. "Recent" or "Command")

```python
# SciQLop/components/command_palette/ui/__init__.py
```

```python
# SciQLop/components/command_palette/ui/delegate.py
from __future__ import annotations

from PySide6 import QtCore, QtGui, QtWidgets

ITEM_HEIGHT = 36
PADDING = 8


class PaletteItemDelegate(QtWidgets.QStyledItemDelegate):
    def sizeHint(self, option, index):
        return QtCore.QSize(option.rect.width(), ITEM_HEIGHT)

    def paint(self, painter: QtGui.QPainter, option, index):
        painter.save()
        self.initStyleOption(option, index)

        is_selected = option.state & QtWidgets.QStyle.StateFlag.State_Selected
        bg = option.palette.highlight() if is_selected else option.palette.base()
        painter.fillRect(option.rect, bg)

        data = index.data(QtCore.Qt.ItemDataRole.UserRole) or {}
        name = index.data(QtCore.Qt.ItemDataRole.DisplayRole) or ""
        description = data.get("description", "")
        match_positions = set(data.get("match_positions", []))
        category = data.get("category", "")

        text_color = option.palette.highlightedText() if is_selected else option.palette.text()
        dim_color = option.palette.placeholderText()

        icon = index.data(QtCore.Qt.ItemDataRole.DecorationRole)
        x = option.rect.left() + PADDING
        y = option.rect.top()
        h = option.rect.height()

        if icon and not icon.isNull():
            icon_size = h - 2 * PADDING
            icon.paint(painter, x, y + PADDING, icon_size, icon_size)
            x += icon_size + PADDING

        font = painter.font()
        bold_font = QtGui.QFont(font)
        bold_font.setBold(True)
        fm = QtGui.QFontMetrics(font)

        for i, ch in enumerate(name):
            if i in match_positions:
                painter.setFont(bold_font)
                painter.setPen(text_color.color())
            else:
                painter.setFont(font)
                painter.setPen(text_color.color())
            painter.drawText(x, y, 500, h, QtCore.Qt.AlignmentFlag.AlignVCenter, ch)
            x += QtGui.QFontMetrics(painter.font()).horizontalAdvance(ch)

        if category:
            painter.setFont(font)
            painter.setPen(dim_color.color())
            cat_rect = QtCore.QRect(
                option.rect.right() - fm.horizontalAdvance(category) - 2 * PADDING,
                y, fm.horizontalAdvance(category) + 2 * PADDING, h,
            )
            painter.drawText(cat_rect, QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignRight, category)

        if description:
            painter.setFont(font)
            painter.setPen(dim_color.color())
            desc_x = x + PADDING
            desc_rect = QtCore.QRect(desc_x, y, option.rect.right() - desc_x - (fm.horizontalAdvance(category) + 3 * PADDING if category else PADDING), h)
            elided = fm.elidedText(description, QtCore.Qt.TextElideMode.ElideRight, desc_rect.width())
            painter.drawText(desc_rect, QtCore.Qt.AlignmentFlag.AlignVCenter, elided)

        painter.restore()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_command_palette_delegate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/command_palette/ui/ tests/test_command_palette_delegate.py
git commit -m "feat(command_palette): add PaletteItemDelegate with fuzzy highlight rendering"
```

---

### Task 8: Palette Widget — core UI with state machine

**Files:**
- Create: `SciQLop/components/command_palette/ui/palette_widget.py`
- Test: `tests/test_command_palette_widget.py`

- [ ] **Step 1: Write failing tests for widget**

```python
# tests/test_command_palette_widget.py
from PySide6 import QtCore
from tests.fixtures import *


def test_palette_opens_and_closes(qtbot, qapp):
    from PySide6.QtWidgets import QMainWindow
    from SciQLop.components.command_palette.backend.registry import (
        CommandRegistry, PaletteCommand,
    )
    from SciQLop.components.command_palette.backend.history import LRUHistory
    from SciQLop.components.command_palette.ui.palette_widget import CommandPalette

    win = QMainWindow()
    win.resize(800, 600)
    registry = CommandRegistry()
    registry.register(PaletteCommand(
        id="test.cmd", name="Test Command", description="test",
        callback=lambda: None,
    ))
    history = LRUHistory(path="/dev/null", max_size=5)
    palette = CommandPalette(win, registry, history)

    palette.toggle()
    assert palette.isVisible()

    palette.toggle()
    assert not palette.isVisible()


def test_palette_filters_commands(qtbot, qapp):
    from PySide6.QtWidgets import QMainWindow
    from SciQLop.components.command_palette.backend.registry import (
        CommandRegistry, PaletteCommand,
    )
    from SciQLop.components.command_palette.backend.history import LRUHistory
    from SciQLop.components.command_palette.ui.palette_widget import CommandPalette

    win = QMainWindow()
    win.resize(800, 600)
    registry = CommandRegistry()
    registry.register(PaletteCommand(
        id="plot.new", name="New plot panel", description="create panel",
        callback=lambda: None,
    ))
    registry.register(PaletteCommand(
        id="view.logs", name="Toggle logs", description="show/hide logs",
        callback=lambda: None,
    ))
    history = LRUHistory(path="/dev/null", max_size=5)
    palette = CommandPalette(win, registry, history)
    palette.toggle()

    qtbot.keyClicks(palette._input, "plot")
    qtbot.wait(50)
    assert palette._list.model().rowCount() >= 1
    first_name = palette._list.model().index(0, 0).data(QtCore.Qt.ItemDataRole.DisplayRole)
    assert "plot" in first_name.lower()


def test_palette_executes_argless_command(qtbot, qapp):
    from PySide6.QtWidgets import QMainWindow
    from SciQLop.components.command_palette.backend.registry import (
        CommandRegistry, PaletteCommand,
    )
    from SciQLop.components.command_palette.backend.history import LRUHistory
    from SciQLop.components.command_palette.ui.palette_widget import CommandPalette

    win = QMainWindow()
    win.resize(800, 600)
    executed = []
    registry = CommandRegistry()
    registry.register(PaletteCommand(
        id="test.exec", name="Execute Me", description="test",
        callback=lambda: executed.append(True),
    ))
    history = LRUHistory(path="/dev/null", max_size=5)
    palette = CommandPalette(win, registry, history)
    palette.toggle()

    palette._list.setCurrentIndex(palette._list.model().index(0, 0))
    qtbot.keyClick(palette._input, QtCore.Qt.Key.Key_Return)
    assert len(executed) == 1
    assert not palette.isVisible()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_command_palette_widget.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement palette widget**

```python
# SciQLop/components/command_palette/ui/palette_widget.py
from __future__ import annotations

from enum import Enum, auto

from PySide6 import QtCore, QtGui, QtWidgets

from SciQLop.components.command_palette.backend.fuzzy import fuzzy_match
from SciQLop.components.command_palette.backend.history import LRUHistory, HistoryEntry
from SciQLop.components.command_palette.backend.registry import (
    CommandRegistry,
    PaletteCommand,
)
from SciQLop.components.command_palette.ui.delegate import PaletteItemDelegate

HISTORY_SCORE_BONUS = 10


class _State(Enum):
    COMMAND_SELECT = auto()
    ARG_SELECT = auto()


class CommandPalette(QtWidgets.QWidget):
    def __init__(
        self,
        parent: QtWidgets.QWidget,
        registry: CommandRegistry,
        history: LRUHistory,
    ):
        super().__init__(parent)
        self._registry = registry
        self._history = history
        self._state = _State.COMMAND_SELECT
        self._selected_command: PaletteCommand | None = None
        self._arg_step = 0
        self._resolved_args: dict[str, str] = {}

        self.setWindowFlags(QtCore.Qt.WindowType.Widget)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.hide()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._input = QtWidgets.QLineEdit(self)
        self._input.setPlaceholderText("Search commands...")
        self._input.textChanged.connect(self._on_text_changed)
        self._input.installEventFilter(self)
        layout.addWidget(self._input)

        self._list = QtWidgets.QListView(self)
        self._model = QtGui.QStandardItemModel(self)
        self._list.setModel(self._model)
        self._list.setItemDelegate(PaletteItemDelegate())
        self._list.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        layout.addWidget(self._list)

        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setOffset(0, 4)
        shadow.setColor(QtGui.QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

        self.setStyleSheet(
            "CommandPalette { border: 1px solid palette(mid); border-radius: 6px; }"
        )

    def toggle(self):
        if self.isVisible():
            self._close()
        else:
            self._open()

    def _open(self):
        self._reset_state()
        self._reposition()
        self.show()
        self.raise_()
        self._input.setFocus()
        self._refresh_list()

    def _close(self):
        self.hide()
        self._input.clear()

    def _reset_state(self):
        self._state = _State.COMMAND_SELECT
        self._selected_command = None
        self._arg_step = 0
        self._resolved_args = {}
        self._input.clear()
        self._input.setPlaceholderText("Search commands...")

    def _reposition(self):
        parent = self.parentWidget()
        if parent is None:
            return
        pw = parent.width()
        w = int(pw * 0.55)
        x = (pw - w) // 2
        y = 60
        max_h = min(400, parent.height() - y - 20)
        self.setGeometry(x, y, w, max_h)

    def _refresh_list(self):
        query = self._input.text()
        self._model.clear()

        if self._state == _State.COMMAND_SELECT:
            self._populate_command_list(query)
        elif self._state == _State.ARG_SELECT:
            self._populate_arg_list(query)

        if self._model.rowCount() > 0:
            self._list.setCurrentIndex(self._model.index(0, 0))

    def _populate_command_list(self, query: str):
        scored_items: list[tuple[int, str, dict]] = []

        for entry in self._history.entries():
            cmd = self._registry.get(entry.command_id)
            if cmd is None:
                continue
            chain_parts = [cmd.name] + list(entry.resolved_args.values())
            display = " → ".join(chain_parts)
            score, positions = fuzzy_match(query, display)
            if score > 0:
                scored_items.append((
                    score + HISTORY_SCORE_BONUS,
                    display,
                    {
                        "description": cmd.description,
                        "match_positions": positions,
                        "category": "Recent",
                        "command_id": cmd.id,
                        "history_args": entry.resolved_args,
                    },
                ))

        for cmd in self._registry.commands():
            match_text = " ".join([cmd.name] + cmd.keywords)
            score, positions = fuzzy_match(query, match_text)
            if score > 0:
                scored_items.append((
                    score,
                    cmd.name,
                    {
                        "description": cmd.description,
                        "match_positions": positions,
                        "category": "Command",
                        "command_id": cmd.id,
                    },
                ))

        scored_items.sort(key=lambda t: t[0], reverse=True)
        for _, display, data in scored_items:
            item = QtGui.QStandardItem(display)
            item.setData(data, QtCore.Qt.ItemDataRole.UserRole)
            cmd = self._registry.get(data["command_id"])
            if cmd and cmd.icon:
                item.setIcon(cmd.icon)
            item.setEditable(False)
            self._model.appendRow(item)

    def _populate_arg_list(self, query: str):
        if self._selected_command is None:
            return
        arg = self._selected_command.args[self._arg_step]
        completions = arg.completions(self._resolved_args)
        scored = []
        for c in completions:
            score, positions = fuzzy_match(query, c.display)
            if score > 0:
                scored.append((score, c, positions))
        scored.sort(key=lambda t: t[0], reverse=True)
        for _, c, positions in scored:
            item = QtGui.QStandardItem(c.display)
            item.setData(
                {
                    "description": c.description or "",
                    "match_positions": positions,
                    "category": arg.name,
                    "completion_value": c.value,
                },
                QtCore.Qt.ItemDataRole.UserRole,
            )
            if c.icon:
                item.setIcon(c.icon)
            item.setEditable(False)
            self._model.appendRow(item)

    def _on_text_changed(self, _text: str):
        self._refresh_list()

    def _select_current(self):
        index = self._list.currentIndex()
        if not index.isValid():
            # Free-text accept: if in ARG_SELECT and user typed text but no match, accept raw input
            if self._state == _State.ARG_SELECT and self._input.text().strip():
                arg_name = self._selected_command.args[self._arg_step].name
                self._resolved_args[arg_name] = self._input.text().strip()
                self._arg_step += 1
                if self._arg_step >= len(self._selected_command.args):
                    self._execute(self._selected_command, self._resolved_args)
                else:
                    self._input.clear()
                    next_arg = self._selected_command.args[self._arg_step]
                    self._input.setPlaceholderText(f"Select {next_arg.name}...")
                    self._refresh_list()
            return
        data = index.data(QtCore.Qt.ItemDataRole.UserRole) or {}

        if self._state == _State.COMMAND_SELECT:
            command_id = data.get("command_id")
            if not command_id:
                return
            cmd = self._registry.get(command_id)
            if not cmd:
                return

            history_args = data.get("history_args")
            if history_args is not None:
                self._execute(cmd, history_args)
                return

            if not cmd.args:
                self._execute(cmd, {})
            else:
                self._selected_command = cmd
                self._arg_step = 0
                self._resolved_args = {}
                self._state = _State.ARG_SELECT
                self._input.clear()
                self._input.setPlaceholderText(f"Select {cmd.args[0].name}...")
                self._refresh_list()

        elif self._state == _State.ARG_SELECT:
            value = data.get("completion_value", "")
            arg_name = self._selected_command.args[self._arg_step].name
            self._resolved_args[arg_name] = value
            self._arg_step += 1
            if self._arg_step >= len(self._selected_command.args):
                self._execute(self._selected_command, self._resolved_args)
            else:
                self._input.clear()
                next_arg = self._selected_command.args[self._arg_step]
                self._input.setPlaceholderText(f"Select {next_arg.name}...")
                self._refresh_list()

    def _go_back(self):
        if self._state == _State.ARG_SELECT:
            if self._arg_step > 0:
                prev_arg = self._selected_command.args[self._arg_step - 1]
                self._resolved_args.pop(prev_arg.name, None)
                self._arg_step -= 1
                self._input.clear()
                self._input.setPlaceholderText(
                    f"Select {self._selected_command.args[self._arg_step].name}..."
                )
                self._refresh_list()
            else:
                self._reset_state()
                self._refresh_list()
        else:
            self._close()

    def _execute(self, cmd: PaletteCommand, args: dict[str, str]):
        self._close()
        self._history.add(cmd.id, args)
        if args:
            cmd.callback(**args)
        else:
            cmd.callback()

    def eventFilter(self, obj, event):
        if obj is self._input and event.type() == QtCore.QEvent.Type.KeyPress:
            key = event.key()
            if key == QtCore.Qt.Key.Key_Escape:
                self._go_back()
                return True
            if key == QtCore.Qt.Key.Key_Return:
                self._select_current()
                return True
            if key == QtCore.Qt.Key.Key_Down:
                idx = self._list.currentIndex()
                next_row = idx.row() + 1 if idx.isValid() else 0
                if next_row < self._model.rowCount():
                    self._list.setCurrentIndex(self._model.index(next_row, 0))
                return True
            if key == QtCore.Qt.Key.Key_Up:
                idx = self._list.currentIndex()
                prev_row = idx.row() - 1 if idx.isValid() else 0
                if prev_row >= 0:
                    self._list.setCurrentIndex(self._model.index(prev_row, 0))
                return True
            if key == QtCore.Qt.Key.Key_Backspace and not self._input.text():
                self._go_back()
                return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self._reposition()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_command_palette_widget.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/command_palette/ui/ tests/test_command_palette_widget.py
git commit -m "feat(command_palette): add CommandPalette widget with state machine and fuzzy filtering"
```

---

### Task 9: Multi-step argument test

**Files:**
- Test: `tests/test_command_palette_widget.py` (append)

- [ ] **Step 1: Write test for multi-step arg execution**

Append to `tests/test_command_palette_widget.py`:

```python
def test_palette_multi_step_args(qtbot, qapp):
    from PySide6.QtWidgets import QMainWindow
    from SciQLop.components.command_palette.backend.registry import (
        CommandRegistry, PaletteCommand, CommandArg, Completion,
    )
    from SciQLop.components.command_palette.backend.history import LRUHistory
    from SciQLop.components.command_palette.ui.palette_widget import CommandPalette
    from dataclasses import dataclass

    @dataclass
    class FakeArg(CommandArg):
        _completions: list[Completion] = None

        def completions(self, context):
            return self._completions or []

    win = QMainWindow()
    win.resize(800, 600)
    result = {}

    def on_execute(product=None, panel=None):
        result["product"] = product
        result["panel"] = panel

    registry = CommandRegistry()
    registry.register(PaletteCommand(
        id="plot.product",
        name="Plot product",
        description="Plot",
        callback=on_execute,
        args=[
            FakeArg(name="product", _completions=[
                Completion(value="B_gsm", display="B_gsm"),
                Completion(value="V_gsm", display="V_gsm"),
            ]),
            FakeArg(name="panel", _completions=[
                Completion(value="Panel 1", display="Panel 1"),
            ]),
        ],
    ))
    history = LRUHistory(path="/dev/null", max_size=5)
    palette = CommandPalette(win, registry, history)
    palette.toggle()

    # Select the command
    palette._list.setCurrentIndex(palette._list.model().index(0, 0))
    qtbot.keyClick(palette._input, QtCore.Qt.Key.Key_Return)
    # Now in ARG_SELECT for product
    assert palette.isVisible()
    assert palette._list.model().rowCount() == 2

    # Select first product
    palette._list.setCurrentIndex(palette._list.model().index(0, 0))
    qtbot.keyClick(palette._input, QtCore.Qt.Key.Key_Return)
    # Now in ARG_SELECT for panel — only 1 option
    assert palette._list.model().rowCount() == 1

    # Select panel
    palette._list.setCurrentIndex(palette._list.model().index(0, 0))
    qtbot.keyClick(palette._input, QtCore.Qt.Key.Key_Return)

    assert not palette.isVisible()
    assert result["product"] == "B_gsm"
    assert result["panel"] == "Panel 1"
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest tests/test_command_palette_widget.py::test_palette_multi_step_args -v`
Expected: PASS (implementation from Task 8 already supports multi-step chains)

- [ ] **Step 3: Commit**

```bash
git add tests/test_command_palette_widget.py
git commit -m "test(command_palette): add multi-step argument chain test"
```

---

## Chunk 3: Integration with SciQLop + Built-in Commands

### Task 10: Wire registry onto SciQLopApp and palette into main window

**Files:**
- Modify: `SciQLop/core/sciqlop_application.py:30-46` (add registry to SciQLopApp)
- Modify: `SciQLop/core/ui/mainwindow.py:52-58` (create palette widget)
- Modify: `SciQLop/sciqlop_app.py:76` (harvest after plugins load)

- [ ] **Step 1: Add CommandRegistry to SciQLopApp**

In `SciQLop/core/sciqlop_application.py`, add import at top and `_command_registry` in `__init__`:

After line 1 (`from PySide6 import QtWidgets, QtCore, QtGui`), the imports are fine. Add the registry initialization in `__init__` after `self._quickstart_shortcuts`:

```python
# Add to __init__, after self._quickstart_shortcuts line (line 46):
from SciQLop.components.command_palette.backend.registry import CommandRegistry
self._command_registry = CommandRegistry()
```

Add a property after the `quickstart_shortcut` method:

```python
@property
def command_registry(self) -> "CommandRegistry":
    return self._command_registry
```

- [ ] **Step 2: Create palette widget in main window**

In `SciQLop/core/ui/mainwindow.py`, at the end of `_setup_ui()` (before `self._center_and_maximise_on_screen()`), add:

```python
# Command palette
from SciQLop.components.command_palette.ui.palette_widget import CommandPalette
from SciQLop.components.command_palette.backend.history import LRUHistory
from SciQLop.components.command_palette.settings import CommandPaletteSettings
from SciQLop.components.settings.backend.entry import SCIQLOP_CONFIG_DIR
import os

palette_settings = CommandPaletteSettings()
history_path = os.path.join(SCIQLOP_CONFIG_DIR, "command_palette_history.json")
self._palette_history = LRUHistory(path=history_path, max_size=palette_settings.max_history_size)
self._command_palette = CommandPalette(self, sciqlop_app().command_registry, self._palette_history)

shortcut = QtGui.QShortcut(QtGui.QKeySequence(palette_settings.keybinding), self)
shortcut.activated.connect(self._command_palette.toggle)
```

- [ ] **Step 3: Register built-in commands and harvest QActions after plugins load**

In `SciQLop/sciqlop_app.py`, after `load_all(main_windows)` (line 76), add. Note: register_builtin_commands must come BEFORE harvest so that `replaces_qaction` dedup works:

```python
from SciQLop.components.command_palette.commands import register_builtin_commands
register_builtin_commands(app.command_registry)

from SciQLop.components.command_palette.backend.harvester import harvest_qactions
harvest_qactions(app.command_registry, main_windows)
```

- [ ] **Step 4: Run existing tests to verify nothing broke**

Run: `uv run pytest tests/ -v --timeout=30`
Expected: All existing tests PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/core/sciqlop_application.py SciQLop/core/ui/mainwindow.py SciQLop/sciqlop_app.py
git commit -m "feat(command_palette): wire registry onto SciQLopApp, palette into main window, harvest after plugins"
```

---

### Task 11: Built-in arg types and command registration

**Files:**
- Create: `SciQLop/components/command_palette/arg_types.py`
- Create: `SciQLop/components/command_palette/commands.py`
- Test: `tests/test_command_palette_arg_types.py`

Note: `register_builtin_commands` is already called in `sciqlop_app.py` from Task 10 Step 3 (before harvest, so `replaces_qaction` dedup works).

- [ ] **Step 1: Write failing tests for arg types**

```python
# tests/test_command_palette_arg_types.py
from tests.fixtures import *


def test_panel_arg_completions(qtbot, main_window):
    from SciQLop.components.command_palette.arg_types import PanelArg

    arg = PanelArg()
    completions = arg.completions({})
    values = [c.value for c in completions]
    assert "__new__" in values  # always offers "New panel"


def test_time_range_arg_presets():
    from SciQLop.components.command_palette.arg_types import TimeRangeArg

    arg = TimeRangeArg()
    completions = arg.completions({})
    displays = [c.display for c in completions]
    assert "Last hour" in displays
    assert "Last day" in displays
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_command_palette_arg_types.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Create arg types module**

```python
# SciQLop/components/command_palette/arg_types.py
from __future__ import annotations

from dataclasses import dataclass

from SciQLop.components.command_palette.backend.registry import CommandArg, Completion


@dataclass
class PanelArg(CommandArg):
    name: str = "panel"

    def completions(self, context: dict) -> list[Completion]:
        from SciQLop.core.sciqlop_application import sciqlop_app
        win = sciqlop_app().main_window
        panels = win.plot_panels()
        items = [Completion(value="__new__", display="New panel")]
        items += [Completion(value=name, display=name) for name in panels]
        return items


@dataclass
class ProductArg(CommandArg):
    name: str = "product"

    def completions(self, context: dict) -> list[Completion]:
        from SciQLop.core.sciqlop_application import sciqlop_app
        win = sciqlop_app().main_window
        tree = win.productTree
        items = []
        for i in range(tree.model().rowCount()):
            _collect_products(tree.model(), tree.model().index(i, 0), items, "")
        return items


def _collect_products(model, parent_index, items, prefix):
    text = model.data(parent_index)
    path = f"{prefix}/{text}" if prefix else text
    if model.rowCount(parent_index) == 0:
        items.append(Completion(value=path, display=path))
    else:
        for row in range(model.rowCount(parent_index)):
            _collect_products(model, model.index(row, 0, parent_index), items, path)


@dataclass
class CatalogArg(CommandArg):
    name: str = "catalog"

    def completions(self, context: dict) -> list[Completion]:
        from SciQLop.core.sciqlop_application import sciqlop_app
        win = sciqlop_app().main_window
        browser = win.catalogs_browser
        model = browser._tree_model
        items = []
        for i in range(model.rowCount()):
            _collect_tree_items(model, model.index(i, 0), items, "")
        return items


def _collect_tree_items(model, parent_index, items, prefix):
    text = model.data(parent_index)
    path = f"{prefix}/{text}" if prefix else text
    if model.rowCount(parent_index) == 0:
        items.append(Completion(value=path, display=path))
    else:
        for row in range(model.rowCount(parent_index)):
            _collect_tree_items(model, model.index(row, 0, parent_index), items, path)


@dataclass
class ProviderArg(CommandArg):
    name: str = "provider"

    def completions(self, context: dict) -> list[Completion]:
        from SciQLop.components.catalogs.backend.registry import CatalogRegistry
        from SciQLop.components.catalogs.backend.catalog_provider import CatalogProviderCapabilities
        items = []
        for provider in CatalogRegistry.instance().providers():
            if CatalogProviderCapabilities.CREATE_CATALOGS in provider.capabilities:
                items.append(Completion(value=provider.name, display=provider.name))
        return items


@dataclass
class WorkspaceArg(CommandArg):
    name: str = "workspace"

    def completions(self, context: dict) -> list[Completion]:
        from SciQLop.components.workspaces.backend.workspaces_manager import list_existing_workspaces
        return [
            Completion(value=ws.name, display=ws.name)
            for ws in list_existing_workspaces()
        ]


@dataclass
class DockWidgetArg(CommandArg):
    name: str = "dock_widget"

    def completions(self, context: dict) -> list[Completion]:
        from SciQLop.core.sciqlop_application import sciqlop_app
        win = sciqlop_app().main_window
        return [
            Completion(value=dw.windowTitle(), display=dw.windowTitle())
            for dw in win.dock_manager.dockWidgets()
        ]


@dataclass
class TimeRangeArg(CommandArg):
    name: str = "time_range"

    def completions(self, context: dict) -> list[Completion]:
        return [
            Completion(value="1h", display="Last hour"),
            Completion(value="1d", display="Last day"),
            Completion(value="1w", display="Last week"),
            Completion(value="1M", display="Last month"),
        ]
```

- [ ] **Step 4: Create commands module**

```python
# SciQLop/components/command_palette/commands.py
from __future__ import annotations

from SciQLop.components.command_palette.backend.registry import PaletteCommand
from SciQLop.components.command_palette.arg_types import (
    PanelArg, ProductArg, CatalogArg, ProviderArg, WorkspaceArg, TimeRangeArg,
)


def _get_win():
    from SciQLop.core.sciqlop_application import sciqlop_app
    return sciqlop_app().main_window


def _do_plot_product(product: str = "", panel: str = ""):
    win = _get_win()
    if panel == "__new__":
        target = win.new_plot_panel()
    else:
        target = win.plot_panel(panel)
    if target and product:
        from SciQLop.components.plotting.ui.time_sync_panel import plot_product
        from SciQLopPlots import PlotType
        plot_product(target.default_plot, product, plot_type=PlotType.TimeSeries)


def _do_remove_panel(panel: str = ""):
    _get_win().remove_panel(panel)


def _toggle_fullscreen():
    win = _get_win()
    win.showNormal() if win.isFullScreen() else win.showFullScreen()


def _do_set_time_range(time_range: str = ""):
    from datetime import datetime, timedelta
    from SciQLop.core import TimeRange
    durations = {"1h": 1, "1d": 24, "1w": 168, "1M": 720}
    hours = durations.get(time_range, 24)
    now = datetime.utcnow()
    tr = TimeRange((now - timedelta(hours=hours)).timestamp(), now.timestamp())
    _get_win()._dt_range_action.range = tr


def _do_switch_workspace(workspace: str = ""):
    from SciQLop.sciqlop_app import switch_workspace
    switch_workspace(workspace)


def register_builtin_commands(registry):
    registry.register(PaletteCommand(
        id="plot.new_panel",
        name="New plot panel",
        description="Create a new plot panel",
        callback=lambda: _get_win().new_plot_panel(),
        replaces_qaction="Add new plot panel",
    ))

    registry.register(PaletteCommand(
        id="plot.product",
        name="Plot product",
        description="Plot a product in a panel",
        callback=_do_plot_product,
        args=[ProductArg(), PanelArg()],
    ))

    registry.register(PaletteCommand(
        id="plot.remove_panel",
        name="Remove panel",
        description="Remove an existing plot panel",
        callback=_do_remove_panel,
        args=[PanelArg(name="panel")],
    ))

    registry.register(PaletteCommand(
        id="plot.set_time_range",
        name="Set time range",
        description="Set the global time range",
        callback=_do_set_time_range,
        args=[TimeRangeArg()],
    ))

    registry.register(PaletteCommand(
        id="catalog.create",
        name="Create catalog",
        description="Create a new catalog",
        callback=lambda provider="": None,  # wired to provider UI in future
        args=[ProviderArg()],
    ))

    registry.register(PaletteCommand(
        id="catalog.open",
        name="Open catalog",
        description="Open a catalog in the browser",
        callback=lambda catalog="": None,  # wired to catalog selection in future
        args=[CatalogArg()],
    ))

    registry.register(PaletteCommand(
        id="jupyter.lab",
        name="Start JupyterLab",
        description="Start JupyterLab in current workspace",
        callback=lambda: __import__(
            "SciQLop.components.workspaces", fromlist=["workspaces_manager_instance"]
        ).workspaces_manager_instance().start_jupyterlab(),
    ))

    registry.register(PaletteCommand(
        id="workspace.switch",
        name="Switch workspace",
        description="Switch to a different workspace",
        callback=_do_switch_workspace,
        args=[WorkspaceArg()],
    ))

    registry.register(PaletteCommand(
        id="view.fullscreen",
        name="Toggle fullscreen",
        description="Toggle fullscreen mode (F11)",
        callback=_toggle_fullscreen,
        keywords=["F11"],
    ))
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_command_palette_arg_types.py tests/ -v --timeout=30`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/command_palette/arg_types.py SciQLop/components/command_palette/commands.py tests/test_command_palette_arg_types.py
git commit -m "feat(command_palette): add all arg types and register all spec-required built-in commands"
```

---

### Task 12: Palette repositioning on parent resize

**Files:**
- Modify: `SciQLop/components/command_palette/ui/palette_widget.py`

The palette installs an event filter on its parent to handle resize events internally, keeping the coupling clean.

- [ ] **Step 1: Add parent event filter to CommandPalette**

In `CommandPalette.__init__`, after `self.hide()`, add:

```python
parent.installEventFilter(self)
```

Then in the `eventFilter` method, add a branch before the existing `self._input` check:

```python
if obj is self.parentWidget() and event.type() == QtCore.QEvent.Type.Resize:
    if self.isVisible():
        self._reposition()
    return False
```

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/ -v --timeout=30`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add SciQLop/components/command_palette/ui/palette_widget.py
git commit -m "feat(command_palette): reposition palette on parent resize via event filter"
```

---

### Task 13: Welcome page news entry

**Files:**
- Modify: `SciQLop/components/welcome/backend.py:72-76`

- [ ] **Step 1: Add news entry to `_MOCK_NEWS`**

In `SciQLop/components/welcome/backend.py`, prepend to the `_MOCK_NEWS` list:

```python
{"icon": "\u2318", "title": "Command Palette — Press Ctrl+K to search and execute any action", "date": "2026-03-13"},
```

- [ ] **Step 2: Commit**

```bash
git add SciQLop/components/welcome/backend.py
git commit -m "feat(welcome): add command palette news entry"
```

---

### Task 14: End-to-end integration test

**Files:**
- Create: `tests/test_command_palette_integration.py`

- [ ] **Step 1: Write integration test**

```python
# tests/test_command_palette_integration.py
from PySide6 import QtCore
from tests.fixtures import *


def test_palette_opens_in_main_window(qtbot, main_window):
    palette = main_window._command_palette
    palette.toggle()
    assert palette.isVisible()
    assert palette._list.model().rowCount() > 0  # has harvested commands
    palette.toggle()
    assert not palette.isVisible()


def test_palette_ctrl_k_shortcut(qtbot, main_window):
    qtbot.keyClick(main_window, QtCore.Qt.Key.Key_K, QtCore.Qt.KeyboardModifier.ControlModifier)
    assert main_window._command_palette.isVisible()
    qtbot.keyClick(main_window._command_palette._input, QtCore.Qt.Key.Key_Escape)
    assert not main_window._command_palette.isVisible()


def test_palette_new_plot_panel(qtbot, main_window):
    palette = main_window._command_palette
    palette.toggle()

    qtbot.keyClicks(palette._input, "new plot")
    qtbot.wait(50)
    palette._list.setCurrentIndex(palette._list.model().index(0, 0))
    qtbot.keyClick(palette._input, QtCore.Qt.Key.Key_Return)

    assert not palette.isVisible()
    assert len(main_window.plot_panels()) >= 1
```

- [ ] **Step 2: Run integration tests**

Run: `uv run pytest tests/test_command_palette_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_command_palette_integration.py
git commit -m "test(command_palette): add end-to-end integration tests"
```

---

### Task 15: Final cleanup and full test run

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Verify the palette works manually** (optional)

Run: `uv run sciqlop`
Press Ctrl+K, verify the palette opens, type to filter, select a command.

- [ ] **Step 3: Final commit if any cleanup needed**

Stage only the specific files that were modified during cleanup (do not use `git add -A`).

```bash
git commit -m "chore(command_palette): cleanup and finalize"
```
