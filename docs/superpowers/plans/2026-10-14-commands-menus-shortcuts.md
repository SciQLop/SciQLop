# Commands, menus and shortcuts (plan 2a) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plugins contribute commands, menu entries and keyboard shortcuts through extension points. The QActions of a plugin loaded without a restart reach the command palette.

**Architecture:** Three extension points, all built on plan 1a's `ExtensionPoint`:
- `sciqlop.commands` holds the palette's `PaletteCommand`s. `CommandRegistry` becomes a thin adapter over it, so `app.command_registry` keeps working.
- `sciqlop.menus` holds `MenuEntry` contributions, each placing a command at a location with a `when(context)` predicate, as VS Code does (spec §4.3). One helper, `add_menu_entries(menu, location, context)`, appends a location's entries. Every context menu that has a location calls it.
- `sciqlop.shortcuts` holds the existing `Shortcut` records. `register_shortcut` and `registered_shortcuts` stay as adapters.

The plugin loader refreshes the palette's harvest of menu-bar QActions after every activation, which fixes spec §9 issue 3.

**Tech Stack:** Python 3.10+, PySide6, pytest + pytest-qt (+ pytest-xvfb).

**Spec:** `docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md`. The sections that matter here:
- §4.3: the tier-2 row `sciqlop.commands`, `sciqlop.menus`, `sciqlop.shortcuts`, and the "Menus follow VS Code" paragraph;
- §7: migration rules;
- §9 item 3.

Plans 1a, 1b and 1c are implemented and pushed.

## Global Constraints

- Work and commit on `main`, with explicit pathspecs. Never push. Never stage these untracked files: `importlib.metadata`, `setWidget`, `pydata/`, `.claude/`, the untracked `docs/` drafts, `tests/noop_script.py`.
- Run one pytest invocation at a time, in the foreground: `uv run --no-sync pytest <files> -q -p no:cacheprovider`, with Bash `timeout: 600000`. Never `--no-xvfb`. Never `uv sync`. Never edit SciQLopPlots or speasy.
- Write files with the Write/Edit tools. Never use shell heredocs, `cat` or `ls`.
- Ids. Commands keep their existing ids (`app.*`, `qaction.*` and so on); new core ids are `sciqlop.<name>`, and plugins use `<plugin id>.<name>`. Shortcut ids are unchanged (`panel.organize`, ...). The menu locations are exactly `panel`, `panel.export`, `graph`, `product_tree`, `catalog_tree` and `main.tools` (spec §4.3).
- Core contributions are owned by `"sciqlop"` and pass it explicitly. Extension points are main-thread objects.
- Published API keeps working (spec §7):
  - `CommandRegistry.register/unregister/commands/get`;
  - `PaletteCommand`;
  - `register_shortcut`, `registered_shortcuts`, `key_for`, `shortcut_text`, `bind_shortcut`, `add_shortcut`;
  - `user_api.plot.register_panel_menu` and `unregister_panel_menu`.
- Menu-entry context values follow the command palette's argument conventions, so one command callback serves the palette and the menus alike:
  - `panel` is the panel name;
  - `product` is the product path string a `ProductArg` completion would give;
  - `catalog` is `catalog_arg_value(provider_name, uuid)`;
  - `provider` is the provider name;
  - `graph` is the graph name.
- Qt lifetimes: never connect an app-lifetime signal to a widget's bound method (`docs/qt-lifetime-patterns.md`).
- Plugin-author docs move with the code (spec §7): `SciQLop/components/agents/skills/sciqlop-plugin-design/` changes in the same commit. If a `user_api` function is added, also update `/home/jeandet/.claude/memory/sciqlop-user-api.md`; that file is outside the repo and not committed.
- Code style (CLAUDE.md): small functions, data over code, no comment-decorated blocks, a `simplify:` comment on deliberate shortcuts.
- Commit trailer: `Co-Authored-By: <the model writing the commit> <noreply@anthropic.com>`.

## Review Focus

1. **A plugin installed from the App Store or enabled in settings while SciQLop runs** adds a menu-bar action. It appears in the command palette without a restart. → Task 2.
2. **A plugin menu entry whose `when` or command raises.** The rest of the context menu still opens; the error is logged once, and the entry is left out. → Task 3.
3. **A menu entry naming a command that no longer exists**, for example because its plugin failed and was withdrawn. The entry is left out, not shown dead. → Task 3.
4. **A plugin that registers a shortcut while the shortcuts help or settings page is open.** The shortcut is listed without reopening. → Task 4.
5. **Every built-in palette command and menu-bar action that works today is still in the palette exactly once.** No duplicate comes from re-harvesting. → Task 2.

---

## File map

| File | Role | Task |
|---|---|---|
| `SciQLop/components/command_palette/backend/registry.py` | `COMMANDS` extension point; `CommandRegistry` as an adapter | 1 |
| `SciQLop/sciqlop_app.py` | built-in commands registered as owner `sciqlop` | 1 |
| `SciQLop/components/command_palette/backend/harvester.py` | `refresh_harvest(main_window)` | 2 |
| `SciQLop/components/plugins/backend/loader/loader.py` | refresh the harvest after activation | 2 |
| `SciQLop/core/menus.py` (new) | `MenuEntry`, `MENUS`, location constants | 3 |
| `SciQLop/components/command_palette/menu_entries.py` (new) | `add_menu_entries(menu, location, context)` | 3 |
| `time_sync_panel.py`, `graph_context_menu.py`, `products/product_context_menu.py`, `catalogs/ui/catalog_browser.py`, `core/ui/mainwindow.py` | each menu appends its location's entries | 3 |
| `SciQLop/components/shortcuts/registry.py` | `SHORTCUTS` extension point; a new shortcut re-emits `shortcuts_changed` | 4 |
| `SciQLop/components/extension_points.py` | imports the declaring modules | 1, 3, 4 |
| `tests/test_plugin_commands_interop.py` (new), skill references, spec | interop proof, docs | 5 |

---

### Task 1: `sciqlop.commands`, with `CommandRegistry` as an adapter

**Files:**
- Modify: `SciQLop/components/command_palette/backend/registry.py`
- Modify: `SciQLop/sciqlop_app.py` (register the built-ins under `owned_by("sciqlop")`)
- Modify: `SciQLop/components/extension_points.py`
- Test: `tests/test_command_extension_point.py` (new); the existing command palette tests

**Interfaces:**
- Consumes: `ExtensionPoint`, `declare`, `owned_by`, `current_owner`, `key in ep`, `remove` (plans 1a and 1b).
- Produces:
  - `registry.COMMANDS: ExtensionPoint`, contribution type `PaletteCommand`, keyed by `id`.
  - `CommandRegistry` keeps its methods:
    - `register(command)` contributes with the current owner and `replace=True`, as the old dict did;
    - `unregister(id)` removes the command if present;
    - `commands()` returns `COMMANDS.list()`;
    - `get(id)` returns the command or None.
  - Every `CommandRegistry()` instance is a view onto the same `COMMANDS`; the app's instance is one.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_command_extension_point.py`:

```python
"""Palette commands are contributions to sciqlop.commands; CommandRegistry stays as the published adapter."""
import pytest

from SciQLop.components.command_palette.backend.registry import COMMANDS, CommandRegistry, PaletteCommand
from SciQLop.core.extensions import owned_by


@pytest.fixture
def withdraw(qapp):
    yield
    COMMANDS.remove_owner("cmd_demo")


def _cmd(cid, name="Demo"):
    return PaletteCommand(id=cid, name=name, description="", callback=lambda: None)


def test_registering_contributes_with_the_current_owner(withdraw):
    with owned_by("cmd_demo"):
        CommandRegistry().register(_cmd("cmd_demo.hello"))
    assert COMMANDS.owner_of("cmd_demo.hello") == "cmd_demo"
    assert CommandRegistry().get("cmd_demo.hello").name == "Demo"


def test_registering_again_replaces(withdraw):
    with owned_by("cmd_demo"):
        CommandRegistry().register(_cmd("cmd_demo.hello", "First"))
        CommandRegistry().register(_cmd("cmd_demo.hello", "Second"))
    assert CommandRegistry().get("cmd_demo.hello").name == "Second"


def test_unregister_and_unknown_ids(withdraw):
    with owned_by("cmd_demo"):
        CommandRegistry().register(_cmd("cmd_demo.bye"))
    CommandRegistry().unregister("cmd_demo.bye")
    CommandRegistry().unregister("cmd_demo.never")
    assert CommandRegistry().get("cmd_demo.bye") is None
    assert "cmd_demo.bye" not in [c.id for c in CommandRegistry().commands()]


def test_the_app_registry_is_a_view_onto_the_extension_point(withdraw):
    from SciQLop.core.sciqlop_application import sciqlop_app
    with owned_by("cmd_demo"):
        COMMANDS.contribute(_cmd("cmd_demo.direct"))
    assert sciqlop_app().command_registry.get("cmd_demo.direct") is not None
```

Check how tests reach `sciqlop_app()`: grep `command_registry` in tests/. Adapt the last test to that fixture if `qapp` is not a `SciQLopApp`.

- [ ] **Step 2: Run them and see them fail**

Run: `uv run --no-sync pytest tests/test_command_extension_point.py -q -p no:cacheprovider`
Expected: FAIL with an ImportError on `COMMANDS`.

- [ ] **Step 3: Implement**

In `registry.py`, keep `Completion`, `CommandArg` and `PaletteCommand` unchanged, and add:

```python
from SciQLop.core.extensions import ExtensionPoint, declare

COMMANDS = declare(ExtensionPoint("sciqlop.commands", PaletteCommand, what="command",
                                  doc="Commands of the command palette; menu entries place them in menus."))


class CommandRegistry:
    """The published registry API, a view onto sciqlop.commands: every instance sees the same commands."""

    def register(self, command: PaletteCommand) -> None:
        COMMANDS.contribute(command, replace=True)

    def unregister(self, command_id: str) -> None:
        if command_id in COMMANDS:
            COMMANDS.remove(command_id)

    def commands(self) -> list[PaletteCommand]:
        return COMMANDS.list()

    def get(self, command_id: str) -> PaletteCommand | None:
        return COMMANDS.get(command_id) if command_id in COMMANDS else None
```

`PaletteCommand` is a mutable dataclass, which the extension point accepts.

In `sciqlop_app.py`, wrap `register_builtin_commands(app.command_registry)` and `harvest_qactions(...)` in `with owned_by("sciqlop"):`, importing it from `SciQLop.core.extensions`.

In `prepare_extension_points`, add `from SciQLop.components.command_palette.backend import registry  # noqa: F401  declares sciqlop.commands`.

Grep for other `CommandRegistry(` constructions and `_commands` accesses in SciQLop/ and tests/. Tests that build a fresh `CommandRegistry()` expecting it to be empty now share `COMMANDS`. Make them use ids unique to the test and withdraw their owner, or clear only what they added. Report every test you changed.

- [ ] **Step 4: Run them and see them pass**

Run: `uv run --no-sync pytest tests/test_command_extension_point.py tests/test_command_palette*.py -q -p no:cacheprovider`
Expected: all PASS. If the glob matches no file, find the palette tests with `grep -rln "CommandRegistry\|PaletteCommand" tests` and run those.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/command_palette/backend/registry.py SciQLop/sciqlop_app.py SciQLop/components/extension_points.py tests/test_command_extension_point.py
git commit -m "feat(plugins): palette commands are contributions to sciqlop.commands"
```

Add any adjusted test files to the `git add`.

---

### Task 2: The palette sees the menu actions of plugins loaded without a restart (spec §9 issue 3)

**Files:**
- Modify: `SciQLop/components/command_palette/backend/harvester.py` (`refresh_harvest`)
- Modify: `SciQLop/components/plugins/backend/loader/loader.py` (call it after activation)
- Modify: `SciQLop/sciqlop_app.py` (use `refresh_harvest`)
- Test: `tests/test_command_harvest_refresh.py` (new)

**Interfaces:**
- Consumes: `COMMANDS` and the `CommandRegistry` adapter (Task 1); `harvest_qactions(registry, main_window)` (existing, skips known ids and names).
- Produces: `harvester.refresh_harvest(main_window) -> None`. It harvests `main_window`'s menu bar into the palette, owned by `"sciqlop"`. It does nothing when `main_window` has no `menuBar`, as with the loader tests' `object()` main windows. It is idempotent.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_command_harvest_refresh.py`:

```python
"""A plugin activated after startup gets its menu-bar actions into the command palette (spec §9 issue 3)."""
import json
import textwrap

import pytest
from PySide6.QtWidgets import QMainWindow

from SciQLop.components.command_palette.backend.registry import COMMANDS
from SciQLop.components.plugins.backend.loader import context, loader
from SciQLop.core import extensions


@pytest.fixture
def fresh(qapp):
    saved = (dict(context.STATES), set(loader._attempted), dict(vars(loader.loaded_plugins)),
             dict(extensions._EXTENSION_POINTS))
    before = {c.id for c in COMMANDS.list()}
    yield
    for cid in [c.id for c in COMMANDS.list() if c.id not in before]:
        COMMANDS.remove(cid)
    for live, old in zip((context.STATES, loader._attempted, vars(loader.loaded_plugins),
                          extensions._EXTENSION_POINTS), saved):
        live.clear()
        live.update(old)


def _plugin(folder, name, code):
    pkg = folder / name
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text(textwrap.dedent(code))
    (pkg / "plugin.json").write_text(json.dumps({"name": name, "version": "1.0.0"}))
    return (str(folder), name)


def test_a_live_loaded_plugins_menu_action_reaches_the_palette(qtbot, tmp_path, fresh):
    window = QMainWindow()
    qtbot.addWidget(window)
    window.menuBar().addMenu("Tools").addAction("Existing tool")
    plugin = _plugin(tmp_path, "hv_late", """
        def load(main_window):
            main_window.menuBar().actions()[0].menu().addAction("Late plugin tool")
    """)
    loader.activate_all([plugin], main_window=window, ep_plugins={})
    names = [c.name for c in COMMANDS.list()]
    assert "Late plugin tool" in names
    assert names.count("Existing tool") == 1


def test_refreshing_twice_adds_nothing(qtbot, fresh):
    from SciQLop.components.command_palette.backend.harvester import refresh_harvest
    window = QMainWindow()
    qtbot.addWidget(window)
    window.menuBar().addMenu("Tools").addAction("Once only")
    refresh_harvest(window)
    count = len(COMMANDS.list())
    refresh_harvest(window)
    assert len(COMMANDS.list()) == count
    assert [c.name for c in COMMANDS.list()].count("Once only") == 1


def test_main_windows_without_a_menu_bar_are_ignored(qapp):
    from SciQLop.components.command_palette.backend.harvester import refresh_harvest
    refresh_harvest(object())
```

- [ ] **Step 2: Run them and see them fail**

Run: `uv run --no-sync pytest tests/test_command_harvest_refresh.py -q -p no:cacheprovider`
Expected: FAIL. `refresh_harvest` doesn't exist, and the late action is missing.

- [ ] **Step 3: Implement**

In `harvester.py`:

```python
def refresh_harvest(main_window) -> None:
    """Harvest the menu bar into the palette; safe to repeat, so the loader calls it after every activation."""
    from SciQLop.core.extensions import owned_by
    if not hasattr(main_window, "menuBar"):
        return
    with owned_by("sciqlop"):
        harvest_qactions(CommandRegistry(), main_window)
```

In `loader.py`, at the end of `_activate_fresh`, after `_warn_on_provides_drift`:

```python
    _refresh_palette(main_window)
```

with:

```python
def _refresh_palette(main_window) -> None:
    """Plugins add QActions to the menu bar in activate()/load(); the palette lists them (spec §9 issue 3)."""
    from SciQLop.components.command_palette.backend.harvester import refresh_harvest
    try:
        refresh_harvest(main_window)
    except Exception as e:
        log.error(f"refreshing the command palette after plugin activation failed: {e}")
```

`_activate_fresh` already takes `main_window`.

In `sciqlop_app.py`, replace the direct `harvest_qactions(app.command_registry, main_windows)` with `refresh_harvest(main_windows)`. `load_all` already refreshed after activating plugins, so this second call only picks up actions added between `load_all` and here; it costs nothing since harvesting is idempotent. Keep the `owned_by("sciqlop")` block from Task 1 around `register_builtin_commands`.

- [ ] **Step 4: Run them and see them pass**

Run: `uv run --no-sync pytest tests/test_command_harvest_refresh.py tests/test_command_extension_point.py tests/test_plugin_activation.py tests/test_plugin_live_activation.py -q -p no:cacheprovider`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/command_palette/backend/harvester.py SciQLop/components/plugins/backend/loader/loader.py SciQLop/sciqlop_app.py tests/test_command_harvest_refresh.py
git commit -m "fix(plugins): menu actions of plugins loaded without restart reach the command palette"
```

---

### Task 3: `sciqlop.menus`, which places commands in the context menus

**Files:**
- Create: `SciQLop/core/menus.py`
- Create: `SciQLop/components/command_palette/menu_entries.py`
- Modify:
  - `SciQLop/components/plotting/ui/time_sync_panel.py`: the panel context menu (`panel`) and `_build_export_share_menu` (`panel.export`);
  - `SciQLop/components/plotting/ui/graph_context_menu.py`: the per-graph submenu (`graph`);
  - `SciQLop/components/products/product_context_menu.py`: `_on_context_menu` (`product_tree`);
  - `SciQLop/components/catalogs/ui/catalog_browser.py`: `_build_tree_context_menu` (`catalog_tree`);
  - `SciQLop/core/ui/mainwindow.py`: the Tools menu (`main.tools`);
  - `SciQLop/components/extension_points.py`.
- Test: `tests/test_menu_entries.py` (new)

**Interfaces:**
- Consumes: `COMMANDS` (Task 1); `CommandArg.name` for argument names.
- Produces:
  - `SciQLop.core.menus.MenuEntry(id, location, command, label=None, when=<always>, order=0)`, a frozen dataclass.
  - `MENUS: ExtensionPoint`.
  - The constants `PANEL = "panel"`, `PANEL_EXPORT = "panel.export"`, `GRAPH = "graph"`, `PRODUCT_TREE = "product_tree"`, `CATALOG_TREE = "catalog_tree"` and `MAIN_TOOLS = "main.tools"`.
  - `SciQLop.components.command_palette.menu_entries.add_menu_entries(menu, location: str, context: dict) -> list[QAction]`. It appends, in `(order, id)` order, every entry of `location` whose command exists and whose `when(context)` is true. Triggering an entry calls `command.callback(**{a.name: context[a.name] for a in command.args if a.name in context})`. An entry whose `when` raises, or whose command is missing, is skipped and logged once.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_menu_entries.py`:

```python
"""Menu entries (spec §4.3): a registered command placed at a menu location, filtered by when(context)."""
import pytest
from PySide6.QtWidgets import QMenu

from SciQLop.components.command_palette.arg_types import PanelArg
from SciQLop.components.command_palette.backend.registry import COMMANDS, PaletteCommand
from SciQLop.components.command_palette.menu_entries import add_menu_entries
from SciQLop.core.extensions import owned_by
from SciQLop.core.menus import MENUS, PANEL, PRODUCT_TREE, MenuEntry


@pytest.fixture
def demo(qapp):
    calls = []
    with owned_by("mn_demo"):
        COMMANDS.contribute(PaletteCommand(id="mn_demo.zoom", name="Zoom to event", description="",
                                           callback=lambda panel="": calls.append(panel), args=[PanelArg("panel")]))
    yield calls
    MENUS.remove_owner("mn_demo")
    COMMANDS.remove_owner("mn_demo")


def _texts(actions):
    return [a.text() for a in actions]


def test_an_entry_runs_its_command_with_the_context_values_it_names(demo):
    with owned_by("mn_demo"):
        MENUS.contribute(MenuEntry("mn_demo.zoom_entry", PANEL, "mn_demo.zoom"))
    menu = QMenu()
    actions = add_menu_entries(menu, PANEL, {"panel": "Panel 1", "unused": 3})
    assert _texts(actions) == ["Zoom to event"]
    actions[0].trigger()
    assert demo == ["Panel 1"]


def test_label_order_and_location(demo):
    with owned_by("mn_demo"):
        MENUS.contribute(MenuEntry("mn_demo.b", PANEL, "mn_demo.zoom", label="Second", order=2))
        MENUS.contribute(MenuEntry("mn_demo.a", PANEL, "mn_demo.zoom", label="First", order=1))
        MENUS.contribute(MenuEntry("mn_demo.c", PRODUCT_TREE, "mn_demo.zoom", label="Elsewhere"))
    assert _texts(add_menu_entries(QMenu(), PANEL, {})) == ["First", "Second"]


def test_when_filters_and_a_raising_when_is_skipped(demo):
    def boom(context):
        raise RuntimeError("bad predicate")

    with owned_by("mn_demo"):
        MENUS.contribute(MenuEntry("mn_demo.only_p1", PANEL, "mn_demo.zoom", label="Only P1",
                                   when=lambda c: c.get("panel") == "P1"))
        MENUS.contribute(MenuEntry("mn_demo.broken", PANEL, "mn_demo.zoom", label="Broken", when=boom))
    assert _texts(add_menu_entries(QMenu(), PANEL, {"panel": "P2"})) == []
    assert _texts(add_menu_entries(QMenu(), PANEL, {"panel": "P1"})) == ["Only P1"]


def test_an_entry_whose_command_is_gone_is_left_out(demo):
    with owned_by("mn_demo"):
        MENUS.contribute(MenuEntry("mn_demo.orphan", PANEL, "mn_gone.command", label="Orphan"))
    assert _texts(add_menu_entries(QMenu(), PANEL, {})) == []


def test_the_panel_context_menu_shows_entries(qtbot, demo):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    with owned_by("mn_demo"):
        MENUS.contribute(MenuEntry("mn_demo.in_panel", PANEL, "mn_demo.zoom", label="From a plugin"))
    panel = TimeSyncPanel("mn_panel", show_search_overlay=False)
    qtbot.addWidget(panel)
    menu = panel._build_context_menu()
    assert "From a plugin" in [a.text() for a in menu.actions()]
```

Test the other locations' wiring with one assertion each, in the same file, but only where a builder can be called without a full main window:
- the export submenu (call `panel._build_export_share_menu(QMenu())` and look in the "Export" submenu);
- the product-tree menu (extract the menu-building part of `_on_context_menu` into `build_product_menu(tree, product_path, main_window) -> QMenu` if needed to test it without `exec`).

For the graph, catalog-tree and Tools menus, the review reads the wiring. Say in the report which locations are covered by a test.

- [ ] **Step 2: Run them and see them fail**

Run: `uv run --no-sync pytest tests/test_menu_entries.py -q -p no:cacheprovider`
Expected: FAIL with an ImportError on `SciQLop.core.menus`.

- [ ] **Step 3: Implement**

Create `SciQLop/core/menus.py`:

```python
"""Where commands appear in menus: the sciqlop.menus extension point (spec §4.3; menus follow VS Code)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from SciQLop.core.extensions import ExtensionPoint, declare

PANEL, PANEL_EXPORT, GRAPH = "panel", "panel.export", "graph"
PRODUCT_TREE, CATALOG_TREE, MAIN_TOOLS = "product_tree", "catalog_tree", "main.tools"


def _always(context: dict) -> bool:
    return True


@dataclass(frozen=True)
class MenuEntry:
    id: str
    location: str                      # one of the location constants above
    command: str                       # a sciqlop.commands id
    label: Optional[str] = None        # None: the command's name
    when: Callable[[dict], bool] = _always
    order: int = 0


MENUS = declare(ExtensionPoint("sciqlop.menus", MenuEntry, what="menu entry",
                               doc="Commands placed in menus: location, label, order and a when(context) predicate."))
```

Create `SciQLop/components/command_palette/menu_entries.py`:

```python
"""Append the sciqlop.menus entries of one location to a QMenu."""
from SciQLop.components.command_palette.backend.registry import COMMANDS
from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.menus import MENUS

log = getLogger(__name__)


def _shown(entry, context) -> bool:
    if entry.command not in COMMANDS:
        log.warning(f"menu entry {entry.id}: command {entry.command!r} is not registered")
        return False
    try:
        return bool(entry.when(context))
    except Exception as e:
        log.error(f"menu entry {entry.id}: when() failed: {e}")
        return False


def _run(command, context: dict) -> None:
    args = {a.name: context[a.name] for a in command.args if a.name in context}
    try:
        command.callback(**args)
    except Exception as e:
        log.error(f"command {command.id} failed: {e}", exc_info=True)


def add_menu_entries(menu, location: str, context: dict) -> list:
    entries = sorted((e for e in MENUS.list(location=location) if _shown(e, context)), key=lambda e: (e.order, e.id))
    actions = []
    for entry in entries:
        command = COMMANDS.get(entry.command)
        action = menu.addAction(entry.label or command.name)
        action.triggered.connect(lambda _checked=False, c=command: _run(c, context))
        actions.append(action)
    return actions
```

"Logged once" in the Interfaces block is reached simply by logging per menu build. The menus are built on demand, so this is acceptable. Note it in a `simplify:` comment on `_shown` if you keep it that way.

Wire each location. At each one:
- read the builder;
- append `add_menu_entries(<menu>, <location>, <context>)` at its end, after a separator only when there are entries (`menu.addSeparator()` before, removed again if nothing was added, or added only when `MENUS.list(location=...)` is non-empty);
- build the context with the palette's value conventions. Check `arg_types.py` (`ProductArg`, `CatalogArg` and `catalog_arg_value`).

The locations:
- `panel`: in `TimeSyncPanel._build_context_menu`, after `_add_plugin_menus`, with context `{"panel": self.windowTitle()}`.
- `panel.export`: in `_build_export_share_menu`, at the end of the Export submenu, with the same context.
- `graph`: in `graph_context_menu.add_graph_context_actions`, inside each per-graph submenu, with context `{"panel": <panel name>, "graph": graph_name(graph)}`.
- `product_tree`: in `product_context_menu._on_context_menu`, after `_build_plot_target_menu`, with context `{"product": <the ProductArg value for product_path>}`. Find how `ProductArg` turns a path into its value (`_palette_product_path` and its inverse); if no direct helper exists, use `"//".join(product_path)` after checking that `to_product_path` accepts it.
- `catalog_tree`: in `catalog_browser._build_tree_context_menu`, before `return menu`, with context `{"provider": node.provider.name}` plus `"catalog": catalog_arg_value(node.provider.name, node.catalog.uuid)` when `node.catalog` is set.
- `main.tools`: in `mainwindow.py`, connect the Tools menu's `aboutToShow` to a method that removes the previously added entry actions (keep them in a list attribute) and adds the current ones with an empty context. That method is a bound method of the main window connected to its own child menu's signal, which is fine under the lifetime rules: both die together.

In `prepare_extension_points`, add `import SciQLop.core.menus  # noqa: F401  declares sciqlop.menus`.

`register_panel_menu` stays as it is (dynamic submenus, a published API). Say so in the docs.

Docs: in `references/ui-and-settings.md`, add a "Commands and menu entries" section covering:
- registering a `PaletteCommand` through `ctx.contribute("sciqlop.commands", ...)`;
- placing it with a `MenuEntry`;
- the six locations and their context keys;
- `when`;
- a 10-line example.

- [ ] **Step 4: Run them and see them pass**

Run: `uv run --no-sync pytest tests/test_menu_entries.py tests/test_command_extension_point.py tests/test_graph_context_integration.py tests/test_catalog_dnd.py -q -p no:cacheprovider`. Add every test file that covers the menus you touched; find them with `grep -rln "_build_context_menu\|_build_tree_context_menu\|add_graph_context_actions\|_on_context_menu\|toolsMenu" tests`.
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/core/menus.py SciQLop/components/command_palette/menu_entries.py SciQLop/components/plotting/ui/time_sync_panel.py SciQLop/components/plotting/ui/graph_context_menu.py SciQLop/components/products/product_context_menu.py SciQLop/components/catalogs/ui/catalog_browser.py SciQLop/core/ui/mainwindow.py SciQLop/components/extension_points.py SciQLop/components/agents/skills/sciqlop-plugin-design/references/ui-and-settings.md tests/test_menu_entries.py
git commit -m "feat(plugins): menu entries place commands in the panel, export, graph, product-tree, catalog-tree and Tools menus"
```

---

### Task 4: `sciqlop.shortcuts`

**Files:**
- Modify: `SciQLop/components/shortcuts/registry.py`
- Modify (only if needed): `SciQLop/components/shortcuts/ui.py`
- Modify: `SciQLop/components/extension_points.py`
- Test: `tests/test_shortcuts_extension_point.py` (new); the existing shortcut tests

**Interfaces:**
- Consumes: `ExtensionPoint`, `declare`, `owned_by`, `key in ep`.
- Produces:
  - `registry.SHORTCUTS: ExtensionPoint`, contribution type `Shortcut`, keyed by `id`, with the built-ins owned by `"sciqlop"`.
  - `register_shortcut(shortcut)` contributes with `replace=True` and returns the shortcut.
  - `registered_shortcuts()` returns `SHORTCUTS.list()`.
  - `key_for` raises `KeyError` for an unknown id, as before.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_shortcuts_extension_point.py`:

```python
"""Keyboard shortcuts are contributions to sciqlop.shortcuts; the published helpers keep working."""
import pytest

from SciQLop.components.shortcuts.registry import (SHORTCUTS, Shortcut, key_for, register_shortcut,
                                                    registered_shortcuts)
from SciQLop.core.extensions import owned_by


@pytest.fixture
def withdraw(qapp):
    yield
    SHORTCUTS.remove_owner("sc_demo")


def test_builtin_shortcuts_are_owned_by_sciqlop(qapp):
    assert SHORTCUTS.owner_of("app.command_palette") == "sciqlop"
    assert key_for("app.command_palette") == "Ctrl+K"


def test_a_plugin_shortcut_is_registered_listed_and_bound(withdraw):
    with owned_by("sc_demo"):
        register_shortcut(Shortcut("sc_demo.fit", "VDF", "Fit the distribution", "Ctrl+Alt+F"))
    assert SHORTCUTS.owner_of("sc_demo.fit") == "sc_demo"
    assert "sc_demo.fit" in [s.id for s in registered_shortcuts()]
    assert key_for("sc_demo.fit") == "Ctrl+Alt+F"


def test_unknown_ids_still_raise_key_error(qapp):
    with pytest.raises(KeyError):
        key_for("sc_nowhere.nothing")


def test_the_help_lists_a_shortcut_registered_while_it_is_open(qtbot, withdraw):
    from SciQLop.components.shortcuts.ui import ShortcutsHelp
    dialog = ShortcutsHelp()
    qtbot.addWidget(dialog)
    with owned_by("sc_demo"):
        register_shortcut(Shortcut("sc_demo.late", "VDF", "Late shortcut", "Ctrl+Alt+L"))
    assert "Late shortcut" in [label for label, _key in dialog.rows()]
```

`ShortcutsHelp.rows()` returns `(label, key)` pairs of what the dialog shows. The dialog repopulates on the module's `shortcuts_changed` signal, through `on_shortcuts_changed`.

- [ ] **Step 2: Run them and see them fail**

Run: `uv run --no-sync pytest tests/test_shortcuts_extension_point.py -q -p no:cacheprovider`
Expected: FAIL with an ImportError on `SHORTCUTS`.

- [ ] **Step 3: Implement**

In `registry.py`, replace `_registry` with:

```python
SHORTCUTS = declare(ExtensionPoint("sciqlop.shortcuts", Shortcut, what="keyboard shortcut",
                                   doc="Configurable keyboard shortcuts, listed in the help panel and settings."))
for _shortcut in _BUILTIN:
    SHORTCUTS.contribute(_shortcut, owner="sciqlop")


def register_shortcut(shortcut: Shortcut) -> Shortcut:
    """For plugins: make a shortcut configurable and listed in the help panel."""
    return SHORTCUTS.contribute(shortcut, replace=True)


def registered_shortcuts() -> list[Shortcut]:
    return SHORTCUTS.list()


def _shortcut(shortcut_id: str) -> Shortcut:
    if shortcut_id not in SHORTCUTS:
        raise KeyError(shortcut_id)
    return SHORTCUTS.get(shortcut_id)
```

`key_for` and `conflicts` use `_shortcut(...)` and `SHORTCUTS.list()` instead of `_registry`. Grep for `_registry` users in SciQLop/ and tests/ and migrate them.

A newly contributed shortcut must reach the open help dialog, the settings editor and every bound QShortcut. Every one of them already refreshes on the module signal `shortcuts_changed`, through `on_shortcuts_changed`, which drops dead owners with `shiboken6.isValid`. So re-emit it, after `shortcuts_changed` and `_refresh_bindings` are defined:

```python
SHORTCUTS.signals.added.connect(lambda _shortcut: shortcuts_changed.emit())
```

This connects one module-level signal to another module-level signal: no widget is involved, so the lifetime rule holds. `ui.py` needs no change. If the settings editor (`ShortcutsEditor`) does not refresh through `on_shortcuts_changed`, read it, make it do so the same way the help dialog does, and say so in the report.

In `prepare_extension_points`, add `from SciQLop.components.shortcuts import registry as _shortcuts  # noqa: F401  declares sciqlop.shortcuts`.

Docs: in `references/ui-and-settings.md`, update the shortcut paragraph. Use `register_shortcut` in `activate(ctx)`, or `ctx.contribute("sciqlop.shortcuts", Shortcut(...))`; the id is `<plugin id>.<name>`.

- [ ] **Step 4: Run them and see them pass**

Run: `uv run --no-sync pytest tests/test_shortcuts_extension_point.py tests/test_keyboard_shortcuts.py -q -p no:cacheprovider`. Add any other shortcut test files: `grep -rln "register_shortcut\|key_for\|ShortcutsHelp\|ShortcutsEditor" tests`.
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/shortcuts/registry.py SciQLop/components/shortcuts/ui.py SciQLop/components/extension_points.py SciQLop/components/agents/skills/sciqlop-plugin-design/references/ui-and-settings.md tests/test_shortcuts_extension_point.py
git commit -m "feat(plugins): keyboard shortcuts are contributions to sciqlop.shortcuts; help and settings follow new ones"
```

---

### Task 5: Interop proof and plugin-author docs

**Files:**
- Create: `tests/test_plugin_commands_interop.py`
- Modify: `references/plugin-contract.md` (catalogue row), `SKILL.md` (pointer), the spec's §4.3 status line

**Interfaces:**
- Consumes: Tasks 1–4; `loader.activate_all`; `context.STATES`.
- Produces: none.

- [ ] **Step 1: Write the test**

Create `tests/test_plugin_commands_interop.py`. Like plan 1c's interop test, give it a local fixture that restores `STATES`, `loader._attempted`, `loaded_plugins` and `_EXTENSION_POINTS`, and withdraws its owners from every extension point. Copy the fixture and `_plugin` helper from `tests/test_plugin_panel_interop.py`.

One plugin, `ci_vdf`, has an `activate(ctx)` that:
- contributes a `PaletteCommand("ci_vdf.fit", "Fit VDF", "", callback=<records its panel kwarg>, args=[PanelArg("panel")])` to `sciqlop.commands`;
- contributes `MenuEntry("ci_vdf.fit_in_panel", "panel", "ci_vdf.fit", when=lambda c: c.get("panel", "").startswith("Event"))` to `sciqlop.menus`;
- contributes `Shortcut("ci_vdf.fit", "VDF", "Fit VDF", "Ctrl+Alt+V")` to `sciqlop.shortcuts`;
- adds `main_window.menuBar().addMenu("VDF").addAction("Open VDF browser")`, using a `QMainWindow` the test passes as main window.

Assert:
1. `ci_vdf` is active.
2. The palette lists "Fit VDF" and "Open VDF browser" (the harvest after activation).
3. `add_menu_entries(QMenu(), "panel", {"panel": "Event 1"})` gives "Fit VDF", and triggering it records `"Event 1"`.
4. `{"panel": "Other"}` gives nothing.
5. `key_for("ci_vdf.fit") == "Ctrl+Alt+V"`.
6. Activate a failing plugin `ci_broken` that contributes a command and then raises. Its command is gone, because the loader withdraws it (plan 1b). A menu entry that named it is left out.

- [ ] **Step 2: Run it**

Run: `uv run --no-sync pytest tests/test_plugin_commands_interop.py -q -p no:cacheprovider`
Expected: PASS. A failure is a real gap: fix it minimally in the owning module and report it; don't weaken the test.

- [ ] **Step 3: Docs**

- In `references/plugin-contract.md`, add one table row each for `sciqlop.commands`, `sciqlop.menus` and `sciqlop.shortcuts`, with their contribution types and keys, pointing to the `ui-and-settings.md` sections.
- In `SKILL.md`, add one pointer line.
- In the spec's §4.3, mark the commands/menus/shortcuts tier-2 row implemented and name this plan file.

- [ ] **Step 4: Run the skill-name test and the interop test**

Run: `uv run --no-sync pytest tests/test_plugin_commands_interop.py tests/test_agent_skills.py -q -p no:cacheprovider`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_plugin_commands_interop.py SciQLop/components/agents/skills/sciqlop-plugin-design/references/plugin-contract.md SciQLop/components/agents/skills/sciqlop-plugin-design/SKILL.md docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md
git commit -m "test(plugins): interop proof for commands, menu entries and shortcuts; plugin-author docs"
```

Then the controller runs the full suite once and reads the real pass/fail count and exit code.

---

## Decisions this plan makes (each is a ruling; the spec stays the authority)

- **Built-in menu items stay hard-coded.** Each menu appends the entries contributed for its location, so plugins can add to every menu now. Core items move to commands only when their code is touched for another reason. Why: converting dozens of built-in actions is churn with no user-visible gain. Cost if wrong: two ways an item reaches a menu until the core items migrate.
- **`register_panel_menu` (published, dynamic submenus) stays beside menu entries.** It is not adapted onto them, because a menu entry places one command, while a panel menu lists entries computed per panel. The trigger to unify them: a second location that needs dynamic submenus.
- **Harvested menu-bar commands are owned by `"sciqlop"`.** The harvest cannot tell which plugin added a QAction. Cost: unloading a plugin (spec §6, not exposed) would not remove its harvested commands. That is acceptable while disabling a plugin still means a restart.
- **Menu contexts carry the palette's argument values** (names and path strings), not Qt objects, so one callback serves both the palette and the menus. A plugin needing the panel object looks it up by name.
