# Settings, docks and workspace sections (plan 2e) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plugin settings, plugin docks and plugin-owned workspace tables are contributions to extension points; the settings panel and the main window follow them live, and withdrawal takes them back out.

**Architecture:** Three extension points on plan 1a's `ExtensionPoint`:
- `sciqlop.settings` holds `ConfigEntry` subclasses, keyed by class name. `ConfigEntry.__pydantic_init_subclass__` contributes the class (owner = the current owner, so a plugin's settings classes, defined while its module imports under `owned_by`, belong to it). `ConfigEntry._entries_` becomes a read-only mapping view onto the EP, so `list_entries()`/`get_entry()` keep working. The settings panel follows `added`/`removed`: today it builds its category list once, on first show, so a plugin installed while the app runs never shows its settings until restart.
- `sciqlop.docks` holds `Dock` records: a title, a widget factory, a placement (`center`, `left`, `right`, `bottom`), an icon, whether it starts visible, whether its toggle goes on the toolbar. The main window follows the EP from its constructor on: it builds and places each dock, and closes it on `removed`. `add_side_pan(widget, location, icon)` keeps its signature and becomes an adapter that contributes a `Dock`. `center` docks tab into the central area, resolved the way three out-of-tree plugins (cdf_workbench, sciqlop_radio, sciqlop_sismo) each work around by hand today (`_find_central_area`: biggest visible area, else the Welcome dock's area).
- `sciqlop.workspace_sections` holds `WorkspaceSection` records: a TOML table name and a pydantic model. `WorkspaceManifest` keeps unknown tables raw (as today, spec §9 issue 1); a table with a contributed section is read through its model by `manifest.section(table)` and written back by `manifest.set_section(table, value)`. A table that fails validation is kept raw and logged, never dropped.

**Tech Stack:** Python 3.10+, PySide6, PySide6-QtAds, pydantic v2, tomllib/tomli-w (whatever `workspace_manifest.py` already uses), pytest + pytest-qt (+ pytest-xvfb).

**Spec:** `docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md` — §4.3 tier-2 row `sciqlop.workspace_sections`, `sciqlop.docks`, `sciqlop.settings` ("fixed manifest tables, `add_side_pan`, ConfigEntry auto-registration (keeps working, gains owner)"), §6 (consumers listen to `removed`), §7 (migration rules), §8 (errors). Plans 1a–2d are implemented and pushed.

## Global Constraints

- Work and commit on `main`, with explicit pathspecs. Never push. Never stage these untracked files: `importlib.metadata`, `setWidget`, `pydata/`, `.claude/`, the untracked `docs/` drafts, `tests/noop_script.py`.
- Run one pytest invocation at a time, in the foreground: `uv run --no-sync pytest <files> -q -p no:cacheprovider`, with Bash `timeout: 600000`. Never `--no-xvfb`. Never `uv sync`. Never edit SciQLopPlots, speasy, jupyqt, or the out-of-tree plugins in `../plugins_sciqlop`.
- Write files with the Write/Edit tools. Never use shell heredocs, `cat` or `ls` (broken aliases in this shell: `cat` runs `bat`, which hangs on stdin).
- SciQLop loggers bypass pytest's `caplog`; tests that check a log call monkeypatch the module's `log.warning`/`log.error`.
- Extension points are main-thread objects. Anything that can run on another thread reaches them through `@on_main_thread` (`SciQLop.user_api.threading`). A `ConfigEntry` subclass may be defined on any thread (a notebook cell, a test worker).
- Owners: a contribution made inside `owned_by(<plugin>)` (plugin import and `activate`) belongs to that plugin; core contributions are owned by `"sciqlop"`; everything else by `"user"`. Use `core.extensions.contribute_taking_over(ep, item, log)` only where a takeover is legitimate (docks); settings and sections keep their duplicate rules below.
- Published API keeps working (spec §7): `ConfigEntry` subclassing (same `category`/`subcategory` checks, same `ValueError("Duplicate entry name: ...")` for a second class with an existing name), `ConfigEntry.list_entries()`, `ConfigEntry.get_entry(name)`, `ConfigEntry.config_file()`, the YAML files, `SciQLopMainWindow.add_side_pan(widget, location=SideBarLeft, icon=None)`, `addWidgetIntoDock(...)` (unchanged, not migrated: it also hosts plot panels), `WorkspaceManifest.load/save/load_or_repair` and `extra_tables` (unknown tables survive a load/save round trip).
- Withdrawal: a withdrawn settings class leaves the settings panel; its YAML file stays on disk. A withdrawn dock is closed and deleted, and its toggle action leaves every menu and toolbar it was added to. A withdrawn section's table stays in the manifest, raw.
- Qt lifetime rules (`docs/qt-lifetime-patterns.md`): followers are module-level functions or connect with a receiver context; never call methods on a parent from a slot wired to a child's `destroyed`.
- Plugin-author docs move with the code (spec §7): `SciQLop/components/agents/skills/sciqlop-plugin-design/references/ui-and-settings.md` (settings, docks, workspace sections) and `references/plugin-contract.md` (EP list) change in the same commit as the code they document. New public API goes in the global `/home/jeandet/.claude/memory/sciqlop-user-api.md` only if it is under `SciQLop.user_api` (edit, never stage).
- Code style (CLAUDE.md): small functions, data over code, no comment-decorated blocks, a `simplify:` comment on deliberate shortcuts.
- Commit trailer: `Co-Authored-By: <the model writing the commit> <noreply@anthropic.com>`.

## Review Focus

1. **A plugin with settings is installed while the app runs** (and the settings panel was already shown). Its category appears without a restart; withdrawing it removes the category, and the page shown before is not left pointing at a deleted widget. → Task 1.
2. **A `ConfigEntry` subclass is defined on a worker thread** (a notebook cell). It registers, owned by `"user"`, and no `WrongThread` escapes. → Task 1.
3. **A plugin's `center` dock is contributed at start-up**, before the main window is laid out. It tabs with the Welcome dock instead of opening a new area above it (the bug the three plugins work around). → Task 2.
4. **A plugin dock is withdrawn while it is open, floating, or auto-hidden.** No crash, no orphan toggle action in the View menu or toolbar. → Task 2.
5. **A workspace table has invalid content for its section's model** (hand-edited file, older plugin version). Loading keeps the raw table, logs once, `section()` returns `None`, and saving writes the raw table back unchanged. → Task 3.

---

## File map

| File | Role | Task |
|---|---|---|
| `SciQLop/components/settings/backend/entry.py` | `SETTINGS` EP, contribution in `__pydantic_init_subclass__`, `_entries_` view | 1 |
| `SciQLop/components/settings/ui/setting_panel.py` | panel follows `added`/`removed` | 1 |
| `SciQLop/core/docks.py` | `Dock`, `DOCKS` EP | 2 |
| `SciQLop/core/ui/mainwindow.py` | dock follower, `add_side_pan` adapter, `central_area()` | 2 |
| `SciQLop/components/workspaces/backend/workspace_manifest.py` | `WorkspaceSection`, `WORKSPACE_SECTIONS` EP, `section`/`set_section` | 3 |
| `SciQLop/components/extension_points.py` | declares the EPs | 1–3 |
| tests | see each task | 1–4 |
| skill docs, spec §4.3 | docs | 1–4 |

---

### Task 1: `sciqlop.settings`

**Files:**
- Modify: `SciQLop/components/settings/backend/entry.py`
- Modify: `SciQLop/components/settings/ui/setting_panel.py`
- Modify: `SciQLop/components/extension_points.py` (import `entry` so the EP is declared; nothing else to wire: the panel connects itself)
- Test: `tests/test_settings_contributions.py` (new); `tests/test_settings_entry.py`, `tests/test_settings*.py`, `tests/test_plugin_compat.py`, `tests/test_workspace_setup.py` must pass.
- Docs: `references/ui-and-settings.md` (settings section: a plugin's `ConfigEntry` classes belong to it and leave the panel when it is withdrawn; live install shows them), `references/plugin-contract.md` EP list.

**Interfaces:**
- Produces:
  - `SETTINGS = declare(ExtensionPoint("sciqlop.settings", type, what="settings entry", key=attrgetter("__name__"), doc="ConfigEntry subclasses by class name."))` in `entry.py`, declared before `class ConfigEntry` (the class body does not need it; `__pydantic_init_subclass__` does, at subclass time). Contribution type is `type`; `__pydantic_init_subclass__` only contributes `ConfigEntry` subclasses, so that is enough.
  - In `__pydantic_init_subclass__`, after the existing checks: keep `if cls.__name__ in SETTINGS: raise ValueError(f"Duplicate entry name: {cls.__name__}")` (same message as today), then `_contribute_entry(cls, current_owner())`, a module function decorated `@on_main_thread` that calls `SETTINGS.contribute(cls, owner=owner)`. Capture the owner on the calling thread and pass it in: the `owned_by` context does not cross threads.
  - `ConfigEntry._entries_` becomes an instance of `_EntriesView(Mapping)` reading `SETTINGS` (`__getitem__` → `SETTINGS.get` raising `KeyError`; `__iter__`/`__len__` over `SETTINGS.keys()`). `list_entries()` returns `dict(_entries_)` (a snapshot: callers iterate it while plugins may register). `get_entry` keeps its `ValueError("Entry not found: ...")`.
  - The settings panel connects `SETTINGS.signals.added` and `.removed` (receiver-context connection on the `SettingsPanel`) to one slot that, if the panel was already initialized, calls `_refresh()` while keeping the current category selected when it still exists (else the first one). `_refresh` already rebuilds the proxy model and clears cached pages.
- Ruling to state in the commit message: today a second class with an existing name raises; with the EP, a withdrawn plugin's class name becomes free again, so re-installing it in the same process registers it again.

- [ ] **Step 1: Write the failing tests** in `tests/test_settings_contributions.py` (use `tmp_config_dir` from the existing settings tests; remove every class you create from `SETTINGS` in teardown):
  - `test_a_config_entry_is_a_contribution`: define a subclass; it is in `SETTINGS`, owner `"user"`, and in `ConfigEntry.list_entries()`.
  - `test_a_plugin_config_entry_is_owned_by_the_plugin`: define it inside `owned_by("set_demo")`; owner is `"set_demo"`; `SETTINGS.remove_owner("set_demo")` removes it from `list_entries()`, and `get_entry(name)` raises `ValueError`.
  - `test_duplicate_name_still_raises`: a second class with the same name raises `ValueError` mentioning `Duplicate entry name`.
  - `test_defined_on_a_worker_thread` (Review Focus 2): define the subclass inside a `threading.Thread` while the test's `qtbot` waits for it (`qtbot.waitUntil(lambda: done)`), so the main loop runs and the marshalled contribution lands; the class is registered, owner `"user"`, no exception recorded in the thread.
  - `test_the_panel_follows_live_settings` (Review Focus 1): build a `SettingsPanel` (look at how existing settings UI tests build one), show it, then define a subclass with a new category; the category list now contains it; `SETTINGS.remove(name)`; the category is gone and the panel still shows a valid page (`_category_view._current` is a category that exists, and its page widget is valid per `shiboken6.isValid`).
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the new file, then (one invocation each) `tests/test_settings_entry.py` plus every other `tests/test_settings*.py`, `tests/test_plugin_compat.py tests/test_workspace_setup.py`. All pass.
- [ ] **Step 5: Commit** `feat(plugins): settings entries are contributions to sciqlop.settings; the settings panel follows live installs`.

---

### Task 2: `sciqlop.docks`

**Files:**
- Create: `SciQLop/core/docks.py`
- Modify: `SciQLop/core/ui/mainwindow.py`
- Modify: `SciQLop/components/extension_points.py` (import `SciQLop.core.docks`; the main window follows on its own)
- Test: `tests/test_dock_contributions.py` (new); `tests/test_mainwindow*.py`, the agents chat-dock tests (grep `add_side_pan` and `chat_dock` under `tests/`), `tests/test_startup_sequence.py` must pass.
- Docs: `references/ui-and-settings.md` (a "Docks" section with a `ctx`-style example contributing a center dock; say that this replaces the `_find_central_area` + `addWidgetIntoDock` + `findDockWidget` + `toggleView(False)` dance), `references/plugin-contract.md` EP list.

**Interfaces:**
- Produces:
  - `Dock(id: str, title: str, build: Callable[[], QWidget], placement: str = "center", icon: str | None = None, visible: bool = True, toolbar: bool = False)`, frozen dataclass in `core/docks.py`. `placement` in `PLACEMENTS = ("center", "left", "right", "bottom")`, else `ValueError` in `__post_init__`. `icon` is a registered icon name or a file path (same rule as `add_side_pan` today).
  - `DOCKS = declare(ExtensionPoint("sciqlop.docks", Dock, what="dock", doc="Docks and side panes by id."))`.
  - `SciQLopMainWindow.follow_docks()` is called in `__init__` before `_setup_side_panels`, so core side panes go through the EP. It connects `DOCKS.signals.added/removed` with the main window as receiver context, and applies every existing contribution (docks contributed before the window existed). It keeps `self._docks: dict[str, CDockWidget]`.
    - `added(dock)`: if the id already has a dock widget (a replace), remove that one first (same path as `removed`). Then `widget = dock.build()`, `widget.setWindowTitle(dock.title)` if it has none, and place it: `left`/`right`/`bottom` → the existing `add_side_pan` body (auto-hide container on that side bar; move it into a private `_place_side_pane(widget, location, icon)`); `center` → a `CDockWidget` tabbed into `central_area()` (else `addDockWidget(TopDockWidgetArea, ...)` when there is no area at all). Then `toggleView(dock.visible)` for `center` docks (side panes stay collapsed as today). The toggle action goes into `viewMenu` (as today, with `_apply_dock_view_tooltip`); `toolbar=True` also adds it to `toolBar` and `toolsMenu`. The icon applies to the dock widget and its toggle action.
    - `removed(dock)`: pop the dock widget; remove its toggle action from `viewMenu`, `toolBar`, `toolsMenu`; `dock_manager.removeDockWidget(dw)` and `dw.deleteLater()`. Must work for a docked, floating or auto-hidden dock (Review Focus 4): check with QtAds' API which call removes an auto-hide container (`CDockWidget.autoHideDockContainer()` / `CAutoHideDockContainer.cleanupAndDelete()` or similar) — use the qt-docs MCP or the installed PySide6QtAds bindings to confirm, and say what you used in the report.
  - `central_area() -> CDockAreaWidget | None` on the main window: `_find_biggest_area()`, else the Welcome dock's area (`dock_manager.findDockWidget("Welcome")`), else `None`. This is the logic the three out-of-tree plugins copy.
  - `add_side_pan(widget, location=SideBarLeft, icon=None)` keeps its signature and becomes: map `location` to a placement (`SideBarLeft`→`left`, `SideBarRight`→`right`, `SideBarBottom`/`SideBarTop`→`bottom`), then `DOCKS.contribute(Dock(id=f"{current_owner()}.{widget.windowTitle()}", title=widget.windowTitle(), build=lambda: widget, placement=..., icon=icon), owner=current_owner())`. A second `add_side_pan` with the same owner and title raises `ValueError` naming the title (today it silently adds a second dock with the same name; `findDockWidget` then returns one of them). `_setup_side_panels` runs its `add_side_pan` calls inside `owned_by("sciqlop")`. `widget is None` stays a no-op.
  - `SideBarTop` maps to `bottom`: say so with a `simplify:` comment (no caller uses top today).

- [ ] **Step 1: Write the failing tests** in `tests/test_dock_contributions.py` (`main_window` fixture; remove every dock you contribute in teardown):
  - `test_core_side_panes_are_contributions`: `DOCKS` holds `sciqlop.Products`, `sciqlop.Catalogs` (use the real titles), `sciqlop.Settings`, `sciqlop.Properties`, all owned by `"sciqlop"`.
  - `test_a_center_dock_tabs_with_welcome` (Review Focus 3): contribute a `center` dock with `visible=False` under `owned_by("dock_demo")`; its `CDockWidget` is in the same `dockAreaWidget()` as `findDockWidget("Welcome")`; it is closed (`isClosed()`); its toggle action is in `viewMenu.actions()`; with `toolbar=True`, also in `toolBar.actions()` and `toolsMenu.actions()`.
  - `test_withdrawal_closes_the_dock_and_its_actions` (Review Focus 4), parametrized over open-docked, floating (`setFloating()`), and a `left` side pane: after `DOCKS.remove_owner("dock_demo")` and `qtbot.wait(50)`, `findDockWidget(title)` is None and no action with that text remains in `viewMenu`, `toolBar` or `toolsMenu`; no crash.
  - `test_replace_rebuilds`: contribute id `dock_demo.x` twice with `replace=True`; one dock widget with that title exists, holding the second widget.
  - `test_add_side_pan_is_an_adapter`: `add_side_pan(QLabel("p"))` with title `"Pane"` contributes `user.Pane`; a second call with another widget titled `"Pane"` raises `ValueError`.
  - `test_bad_placement_is_refused`: `Dock(..., placement="top")` raises `ValueError`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the new file, then (one invocation each) the main-window tests, the chat-dock tests, `tests/test_startup_sequence.py`. All pass.
- [ ] **Step 5: Commit** `feat(plugins): docks are contributions to sciqlop.docks; center docks tab with Welcome; add_side_pan adapts`.

---

### Task 3: `sciqlop.workspace_sections`

**Files:**
- Modify: `SciQLop/components/workspaces/backend/workspace_manifest.py`
- Modify: `SciQLop/components/extension_points.py` (import the manifest module to declare)
- Test: `tests/test_workspace_sections.py` (new); every `tests/test_workspace*.py` must pass.
- Docs: `references/ui-and-settings.md` ("Workspace sections": contribute a `WorkspaceSection(table, model)`, read with `manifest.section(table)`, write with `set_section` then `save`), `references/plugin-contract.md` EP list.

**Interfaces:**
- Produces:
  - `WorkspaceSection(table: str, model: type[BaseModel])`, frozen dataclass; key = `table`. `table` must not be one of `_KNOWN_TABLES` (`ValueError` in `__post_init__`: those belong to SciQLop) and must be a valid bare TOML key (`[A-Za-z0-9_-]+`, else `ValueError`).
  - `WORKSPACE_SECTIONS = declare(ExtensionPoint("sciqlop.workspace_sections", WorkspaceSection, what="workspace section", key=attrgetter("table"), doc="Plugin-owned tables of a .sciqlop workspace file."))`.
  - `WorkspaceManifest.section(table: str) -> BaseModel | None`: `None` if no section is contributed for `table`, or the table is absent; else `model.model_validate(extra_tables[table])`. On `ValidationError`: `log.warning` once per (manifest, table) naming the table and the first error, and return `None` (Review Focus 5). Not cached: a plugin calls it when it needs the value.
  - `WorkspaceManifest.set_section(table: str, value: BaseModel) -> None`: requires a contributed section for `table` whose `model` is `type(value)` (else `ValueError`), then `extra_tables[table] = value.model_dump(mode="json")`. Persisting is the caller's `save()`, as for every other manifest field.
  - Load and save are unchanged: tables stay raw in `extra_tables`, so a withdrawn section or an invalid table round-trips byte-for-byte equal in content.
  - `simplify:` comment on `section`: no change notification; add a `section_changed` signal when a plugin needs to react to another writer.

- [ ] **Step 1: Write the failing tests** in `tests/test_workspace_sections.py` (pure backend, `tmp_path`; remove contributed sections in teardown; contribute on the main thread — the `qapp` fixture is enough):
  - `test_a_section_reads_and_writes_its_table`: model `class Demo(BaseModel): n: int = 0; names: list[str] = []`; contribute `WorkspaceSection("demo", Demo)`; `m.set_section("demo", Demo(n=3, names=["a"]))`; `m.save(p)`; `WorkspaceManifest.load(p).section("demo") == Demo(n=3, names=["a"])`.
  - `test_no_section_contributed_returns_none_and_keeps_the_table`.
  - `test_invalid_table_is_kept_and_logged_once` (Review Focus 5): write a manifest file with `[demo] n = "not an int"`; load; `section("demo")` is `None` twice, one `log.warning`; save to a new path; the reloaded raw `extra_tables["demo"] == {"n": "not an int"}`.
  - `test_core_table_names_are_refused`: `WorkspaceSection("plugins", Demo)` raises `ValueError`.
  - `test_set_section_with_the_wrong_model_is_refused`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the new file, then every `tests/test_workspace*.py` (one invocation). All pass.
- [ ] **Step 5: Commit** `feat(plugins): plugins own workspace tables through sciqlop.workspace_sections`.

---

### Task 4: Interop proof and spec bookkeeping

**Files:**
- Modify: `tests/test_plugin_interop.py` (one test; reuse `_plugin`, `fresh`, `_OWNERS`; withdraw through `loader._withdraw` as the newest tests there do)
- Modify: `docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md` (§4.3 row: append `; **implemented**: docs/superpowers/plans/2026-10-15-settings-docks-workspace-sections.md`)

- [ ] **Step 1: Write the test** `test_plugin_contributes_settings_a_dock_and_a_workspace_section`: plugin `ui_maker` whose module defines a `ConfigEntry` subclass (unique class name, category `"ui_maker"`) and whose `activate(ctx)` contributes a `center` `Dock` (id `ui_maker.panel`, `build=lambda: QLabel("ui")`) and a `WorkspaceSection("ui_maker", Model)`. Load it through the loader with the `main_window` fixture. Assert: the entry is owned by `ui_maker`; the dock widget exists next to Welcome; the section is owned by `ui_maker`. Then `loader._withdraw("ui_maker")`: the entry left `ConfigEntry.list_entries()`, `findDockWidget(title)` is None, the section is gone from `WORKSPACE_SECTIONS`.
- [ ] **Step 2: Run** `tests/test_plugin_interop.py` alone; all pass.
- [ ] **Step 3: Update the spec row** and commit `test(plugins): interop proof for settings, docks and workspace sections; spec row marked implemented`.

Follow-up outside this plan (out-of-tree repo, needs its own change): migrate `cdf_workbench`, `sciqlop_radio` and `sciqlop_sismo` in `../plugins_sciqlop` from `_find_central_area` + `addWidgetIntoDock` to a contributed `center` `Dock`, once a SciQLop release ships `sciqlop.docks`.
