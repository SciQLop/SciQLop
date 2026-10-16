# Panel kinds and panel extensions (plan 2g) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plugins declare new kinds of panels (any widget) that other plugins and users can open, save and restore, and plugins extend any panel, the time panel included, through a hand-off with clean-up.

**Architecture:** Two extension points. `sciqlop.panel_kinds` holds `PanelKind(id, label, create, to_config, icon, in_new_menu)`; the time panel becomes the core kind `sciqlop.time_panel`; one `open_panel(kind_id, name, **config)` docks any kind through the docking path today's panels use (moved out of `mainwindow.py` into a small `panel_host.py`). `sciqlop.panel_extensions` holds `PanelExtension(id, attach, kinds)`; a follower owned by the main window attaches extensions to open and future panels and calls their clean-ups on close, withdrawal and replace. Templates accept any root kind: a missing kind restores as a placeholder panel that keeps its tree, offers to install the plugin, and turns into the real panel once the kind arrives.

**Tech Stack:** Python 3.10+, PySide6, PySide6-QtAds, pydantic v2, pytest + pytest-qt (+ pytest-xvfb).

**Spec:** `docs/superpowers/specs/2026-10-16-panel-kinds-and-extensions-design.md` (approved 2026-10-16). Parent: `docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md` §4.3, §5, §6, §7, §8. Plans 1a–2f are implemented and pushed.

## Global Constraints

- Work and commit on `main`, with explicit pathspecs. Never push. Never stage these untracked files: `importlib.metadata`, `setWidget`, `pydata/`, `.claude/`, the untracked `docs/` drafts, `tests/noop_script.py`.
- Run one pytest invocation at a time, in the foreground: `uv run --no-sync pytest <files> -q -p no:cacheprovider`, with Bash `timeout: 600000`. Never `--no-xvfb`. Never `uv sync`. Never edit SciQLopPlots, speasy, jupyqt, or `../plugins_sciqlop`.
- Memory is tight on this machine: before every pytest run check `free -g` shows at least 8 GB available (else wait, `sleep 30` loops up to 15 min); after every run kill only the `Xvfb` processes you started whose parent is PID 1 (`pgrep -a Xvfb`).
- Write files with the Write/Edit tools. Never use shell heredocs, `cat` or `ls` (broken aliases: `cat` runs `bat`, which hangs on stdin).
- SciQLop loggers bypass pytest's `caplog`; tests that check a log call monkeypatch the module's `log.warning`/`log.error`.
- Tests that wait for Qt or async work assert outcomes with `qtbot.waitUntil(...)`, never a fixed `qtbot.wait(...)` before an assert (fixed waits flaked on CI and under load, 2026-10-16).
- Extension points are main-thread objects; `user_api` entry points are marshalled with `@on_main_thread` (`SciQLop.user_api.threading`). Core contributions are owned by `"sciqlop"`, passed explicitly.
- Qt lifetime (`docs/qt-lifetime-patterns.md`, plan 2e lessons): EP signals live for the whole process, main windows do not, and several are alive at once in tests. Connect bound methods, start every slot with `if not shiboken6.isValid(self): return` (this PySide6 refuses `signal.connect(context, slot)`); never call into a parent from a child's `destroyed`; test teardown through `destroy_main_window` (tests/fixtures.py). Closing a dock: take its content out and `deleteLater()` it before `closeDockWidget()` (`_queue_content_delete` in mainwindow.py) — QRhiWidget use-after-free otherwise.
- Published API keeps working (parent spec §7): `SciQLopMainWindow.new_plot_panel(backend="native", name=None)`, `new_native_plot_panel(name=None, area=None)` (returns the `TimeSyncPanel`), `plot_panels()` and `plot_panel(name)` (time panels only, as today), `remove_panel(panel_or_name)`, the `panel_added` signal (emitted with the panel widget), `user_api` `create_plot_panel`, `plot_panel`, `templates.load/list_templates/delete/rename`, `PanelTemplate.from_file/to_file/from_panel/create_panel/apply`, and every existing template file loading as before.
- Plugin-author docs move with the code (parent spec §7): `SciQLop/components/agents/skills/sciqlop-plugin-design/references/plugin-contract.md` (EP list) and a "Panels: kinds and extensions" section in `references/ui-and-settings.md`; new `user_api` functions go in the global `/home/jeandet/.claude/memory/sciqlop-user-api.md` (outside the repo: edit, never stage).
- Code style (CLAUDE.md): small functions, data over code, no comment-decorated blocks, a `simplify:` comment on deliberate shortcuts.
- Commit trailer: `Co-Authored-By: <the model writing the commit> <noreply@anthropic.com>`.

## Review Focus

1. **A plugin panel is closed by its dock's X, floating, or while its extension's attach is still running.** No crash; extension clean-ups run once; the panel leaves `panels()`. → Tasks 1, 3.
2. **Two main windows alive at once (tests) and a plugin contributes an extension.** Each window attaches only to its own panels; destroying one window does not call into it later. → Task 3.
3. **A template whose kind's plugin is missing is loaded, then saved again** (through a time panel's or the placeholder's save path). The file keeps the original tree byte-for-byte in content; nothing becomes a time panel. → Task 4.
4. **The store index is unreachable (offline) when a placeholder opens.** No GUI freeze (lookup off the GUI thread, 10 s timeout), the placeholder shows the message without a button, nothing raises. → Task 5.
5. **The plugin providing a placeholder's kind is hot-loaded** (App Store install, `%install`, or any later contribution). The placeholder becomes the real panel in the same dock area, with the saved config, and the placeholder's name is released and reused. → Task 5.

---

## File map

| File | Role | Task |
|---|---|---|
| `SciQLop/core/panel_kinds.py` (new) | `PanelKind`, `PANEL_KINDS`, `KIND_PROPERTY`, `panel_kind_of` | 1 |
| `SciQLop/core/ui/panel_host.py` (new) | docking any panel widget; finding docked panels of any kind | 1 |
| `SciQLop/core/ui/mainwindow.py` | `open_panel`, `panels()`, generalised `remove_panel`; time path through `panel_host` | 1, 2 |
| `SciQLop/components/plotting/time_panel_kind.py` (new) | the core `sciqlop.time_panel` contribution | 1 |
| `SciQLop/user_api/plot/_panel.py` (or a new `user_api/panels.py`) | `open_panel`, `list_panel_kinds` | 2 |
| `SciQLop/core/panel_extensions.py` (new) | `PanelExtension`, `PANEL_EXTENSIONS` | 3 |
| `SciQLop/core/ui/panel_extensions_follower.py` (new) | attach / clean-up bookkeeping per main window | 3 |
| `SciQLop/components/plotting/panel_template.py` | any root kind; `panel_tree(widget)` | 4 |
| `SciQLop/components/plotting/ui/placeholder_panel.py` (new) | placeholder panel + swap on contribution | 4, 5 |
| `SciQLop/components/plugins/install_offer.py` (new) | store lookup for a kind | 5 |
| `SciQLop/components/extension_points.py` | declares the EPs, contributes the core kind | 1, 3 |
| tests, docs, spec rows | | 1–6 |

---

### Task 1: `sciqlop.panel_kinds`, the shared docking path, the core time kind

**Files:**
- Create: `SciQLop/core/panel_kinds.py`, `SciQLop/core/ui/panel_host.py`, `SciQLop/components/plotting/time_panel_kind.py`
- Modify: `SciQLop/core/ui/mainwindow.py`, `SciQLop/components/extension_points.py`
- Test: `tests/test_panel_kinds.py` (new); every `tests/test_mainwindow*.py`, `tests/test_panel*.py`, `tests/test_floating_panel_close.py`, `tests/test_dock_contributions.py`, `tests/test_startup_sequence.py` must pass unchanged.
- Docs: `references/plugin-contract.md` EP row; "Panels: kinds and extensions" section in `references/ui-and-settings.md` (kinds half: contract, `open_panel`, naming, withdrawal).

**Interfaces:**
- Produces:
  - `PanelKind(id: str, label: str, create: Callable[[str, dict], QWidget], to_config: Optional[Callable[[QWidget], dict]] = None, icon: Optional[str] = None, in_new_menu: bool = True)`, frozen dataclass; empty `id`/`label` → `ValueError`.
  - `PANEL_KINDS = declare(ExtensionPoint("sciqlop.panel_kinds", PanelKind, what="panel kind", doc="Kinds of panels a main window can open, save and restore."))`.
  - `KIND_PROPERTY = "sciqlop_panel_kind"`; `panel_kind_of(widget) -> Optional[str]` reads it (`None` for an untagged widget; a `TimeSyncPanel` created through any path reports `"sciqlop.time_panel"` — tag it in the time kind's `create` and in `new_native_plot_panel`).
  - `panel_host.py`: `dock_panel(main_window, panel: QWidget, kind_id: str, area=None) -> CDockWidget` — the body of today's `new_native_plot_panel` after the panel exists (wrap a `TimeSyncPanel` in `PanelContainer`, other widgets dock directly; `addWidgetIntoDock(..., delete_on_close=True, custom_close_callback=lambda: main_window.remove_panel(panel))`, `_ensure_add_panel_button`, `_follow_panel_renames`, `closed` → `_on_panel_dock_closed`, `delete_me` if the widget has it, `panel_added.emit(panel)`, `_notify_panels_list_changed`, the `destroyed` hooks), and sets `KIND_PROPERTY`. `panel_of(dock_widget) -> Optional[QWidget]` = `_extract_panel(dw)` for a `PanelContainer`, else the dock's widget when it carries `KIND_PROPERTY` and is valid. `panel_docks(main_window) -> list[(CDockWidget, QWidget)]` over `dockWidgetsMap()` (floating docks included). Move the helpers this needs (`_follow_panel_renames`, `_queue_content_delete`, `_destroy_content_before_its_window`, `_extract_panel`) only if that is the smallest change that keeps `mainwindow.py` importing them; otherwise import them from `mainwindow.py` into `panel_host.py` lazily — say which in the report.
  - `SciQLopMainWindow.open_panel(kind_id: str, name: Optional[str] = None, area=None, **config) -> QWidget`: `PANEL_KINDS.get(kind_id)` (raises `NotRegistered`), `name = auto_name(base=kind.label, name=name)`, `widget = kind.create(name, config)` — on exception `release_name(name)`, `log.error(f"panel kind {kind_id} failed to create {name!r}", exc_info=True)` and re-raise; `widget.setObjectName(name)`, `widget.setWindowTitle(name)` (a `TimeSyncPanel` already has both); icon from `kind.icon` (same rule as `add_side_pan`); `dock_panel(self, widget, kind_id, area)`; return widget.
  - `new_native_plot_panel(name=None, area=None)` keeps its signature and return value and becomes `return self.open_panel(TIME_PANEL, name=name, area=area)` (so both paths are one).
  - `SciQLopMainWindow.panels() -> list[QWidget]` every docked panel of any kind; `plot_panels()`/`plot_panel()` unchanged in behaviour (time panels only: filter `panels()` on `isinstance(p, TimeSyncPanel)`).
  - `remove_panel(panel_or_name)`: a name resolves over `panels()` by `objectName()`/`.name`; works for any kind; same order as today (`release_name`, `_queue_content_delete(dw)`, `closeDockWidget()`, notify). Task 3 inserts the extension clean-up call at the top of this method.
  - `time_panel_kind.py`: contributes `PanelKind(TIME_PANEL, "Panel", create=_create_time_panel, to_config=None, icon="add_graph")` with `owner="sciqlop"` (Task 4 sets `to_config`). `_create_time_panel(name, config)` builds `TimeSyncPanel(parent=None, name=name, time_range=<main window default range>)` — read how `new_native_plot_panel` gets `self._default_time_range` and pass it through `config` (`config.get("time_range")`) from `open_panel`'s caller when absent: `open_panel` for `TIME_PANEL` fills `config.setdefault("time_range", self._default_time_range)`. Keep the base name `"Panel"` so default names stay `Panel`, `Panel1`… as today.
  - `simplify:` comment in `open_panel`: open panels of a withdrawn kind stay open.

- [ ] **Step 1: Write the failing tests** in `tests/test_panel_kinds.py` (`main_window` fixture; contribute test kinds under `owned_by("pk_demo")`, `PANEL_KINDS.remove_owner("pk_demo")` and remove leftover panels in teardown):
  - `test_the_time_panel_is_a_core_kind`: `TIME_PANEL in PANEL_KINDS`, owner `"sciqlop"`; `new_plot_panel()` returns a `TimeSyncPanel` with `panel_kind_of(p) == TIME_PANEL`; its name starts with `"Panel"`.
  - `test_open_panel_docks_a_plugin_widget`: kind `pk_demo.label` with `create=lambda name, config: QLabel(config.get("text", ""))`; `w = main_window.open_panel("pk_demo.label", text="hi")`; `w.text() == "hi"`, `panel_kind_of(w) == "pk_demo.label"`, `w in main_window.panels()`, `w.objectName() not in main_window.plot_panels()`, a dock with that title exists, `panel_added` was emitted with `w` (spy).
  - `test_names_are_unique`: two `open_panel` with the same `name="X"` give `X` and `X_1` (or whatever `auto_name` yields — assert they differ and both are listed).
  - `test_remove_panel_closes_any_kind`: `remove_panel(w)` → `qtbot.waitUntil(lambda: w not in main_window.panels())`; the name is released (a new `open_panel(name=same)` gets it back exactly).
  - `test_closing_by_the_dock_x` (Review Focus 1): call the dock widget's close request the way the X does (read `addWidgetIntoDock`'s `custom_close_callback` path: `dw.closeRequested.emit()` or `dw.requestCloseDockWidget()` — check the QtAds binding), for a docked and a floating (`dw.setFloating()`) plugin panel; no crash, panel leaves `panels()`.
  - `test_create_raising_is_logged_and_raised`: kind whose `create` raises `RuntimeError`; `open_panel` raises it; one `log.error` naming the kind; no new dock; the name is free again.
  - `test_unknown_kind`: `open_panel("nope.kind")` raises `LookupError` whose message lists `sciqlop.time_panel`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the new file, then (one invocation each, memory check first) the main-window/panel/floating/dock/startup tests listed above. All pass.
- [ ] **Step 5: Commit** `feat(plugins): panels are contributions to sciqlop.panel_kinds; open_panel docks any kind; the time panel is the core kind`.

---

### Task 2: New-panel menu and `user_api`

**Files:**
- Modify: `SciQLop/core/ui/mainwindow.py` (`_ensure_add_panel_button`, `_add_panel_in_button_area`)
- Modify: `SciQLop/user_api/plot/__init__.py` and/or a new `SciQLop/user_api/panels.py` (follow how `create_plot_panel` is exported; list in `__all__`)
- Modify: `tests/test_user_api_thread_classification.py` only as its failures require (new functions are `@on_main_thread`).
- Test: `tests/test_panel_kinds_ui.py` (new); `tests/test_panel_area_add_button.py`, `tests/test_user_api*.py` must pass.
- Docs: `ui-and-settings.md` (menu + user_api lines); global `sciqlop-user-api.md` (`open_panel`, `list_panel_kinds`).

**Interfaces:**
- Consumes: `PANEL_KINDS`, `open_panel`, `TIME_PANEL` (Task 1).
- Produces:
  - The area "+" button: when the time panel is the only kind with `in_new_menu=True` (the normal case) it behaves exactly as today (click opens a time panel in that area). With two or more `in_new_menu` kinds it gets a menu (`QToolButton.setPopupMode(MenuButtonPopup)`: click still opens a time panel, the arrow lists every `in_new_menu` kind by `label`, time panel first, then contribution order); choosing an entry calls `open_panel(kind.id, area=<the button's live area>)` resolved the way `_add_panel_in_button_area` does today (from the button's parent chain at click time — keep that comment's reasoning). The menu is rebuilt when shown (`aboutToShow`), so kinds contributed or withdrawn later are reflected without tracking signals.
  - `user_api`: `open_panel(kind: str, name: Optional[str] = None, **config)` (`@on_main_thread`): a time panel comes back as today's user_api `PlotPanel` (reuse whatever `create_plot_panel` does to wrap), any other kind as the widget. `list_panel_kinds() -> list[str]` (thread-safe: `PANEL_KINDS.keys()`; leave it unmarshalled and list it where the classifier wants plain reads).

- [ ] **Step 1: Write the failing tests** in `tests/test_panel_kinds_ui.py`:
  - `test_one_kind_keeps_the_plain_button`: the add button has no menu (`button.menu() is None`) and clicking it opens a time panel in its area (copy how `tests/test_panel_area_add_button.py` clicks it).
  - `test_a_plugin_kind_adds_a_menu`: contribute `pk_ui.label` (`in_new_menu=True`); `button.menu()` lists "Panel" then the plugin label after `aboutToShow`; triggering the plugin action opens it in the same area as the button.
  - `test_hidden_kind_is_not_listed`: `in_new_menu=False` kind does not appear.
  - `test_user_api_open_panel`: `open_panel("sciqlop.time_panel")` returns a user_api `PlotPanel`; `open_panel("pk_ui.label", text="x")` returns the widget; `list_panel_kinds()` contains both.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the new file, `tests/test_panel_area_add_button.py`, `tests/test_user_api*.py` (one invocation each). All pass.
- [ ] **Step 5: Commit** `feat(plugins): the new-panel button lists plugin panel kinds; user_api open_panel and list_panel_kinds`.

---

### Task 3: `sciqlop.panel_extensions`

**Files:**
- Create: `SciQLop/core/panel_extensions.py`, `SciQLop/core/ui/panel_extensions_follower.py`
- Modify: `SciQLop/core/ui/mainwindow.py` (create the follower in `__init__` before `_setup_side_panels`; call it from `open_panel`/`dock_panel` after docking and at the top of `remove_panel`; also from `_on_panel_dock_closed` for a force-closed dock), `SciQLop/components/extension_points.py`
- Test: `tests/test_panel_extensions.py` (new); Task 1's and the main-window tests must pass.
- Docs: `ui-and-settings.md` (extensions half, with a 10-line example adding a toolbar button to every time panel and removing it in the clean-up), `plugin-contract.md` EP row.

**Interfaces:**
- Consumes: `panel_kind_of`, `panels()`, `remove_panel`, `dock_panel` (Task 1).
- Produces:
  - `PanelExtension(id: str, attach: Callable[[QWidget], Optional[Callable[[], None]]], kinds: tuple[str, ...] = ())`, frozen dataclass; `kinds=()` means every kind.
  - `PANEL_EXTENSIONS = declare(ExtensionPoint("sciqlop.panel_extensions", PanelExtension, what="panel extension", doc="Code run on every open and future panel of some kinds, with a clean-up."))`.
  - `PanelExtensionsFollower(QObject)`, child of the main window: `self._cleanups: dict[tuple[str, int], tuple[QWidget, PanelExtension, Optional[Callable]]]` keyed by `(extension id, id(panel))`.
    - `panel_opened(panel)`: attach every matching contribution in `PANEL_EXTENSIONS.list()` order.
    - `panel_closing(panel)`: run and drop that panel's clean-ups (exactly once; a second call is a no-op).
    - `added(ext)` slot: if `ext.id` already has entries (a replace), run their clean-ups first; then attach to every panel in `main_window.panels()` that matches.
    - `removed(ext)` slot: run and drop its clean-ups.
    - `matches(ext, panel)`: `not ext.kinds or panel_kind_of(panel) in ext.kinds`.
    - Every slot starts with `if not shiboken6.isValid(self): return`; bound methods; connected in the constructor.
    - `_attach`/`_cleanup` wrap the call: an exception → `log.error(f"panel extension {ext.id} failed on {panel.objectName()!r}", exc_info=True)`, the entry is recorded as having no clean-up (attach) or dropped (clean-up).
    - A clean-up is never called for a panel whose C++ object is already gone: check `shiboken6.isValid(panel)` and skip (drop the entry) — the plugin's own objects died with it.

- [ ] **Step 1: Write the failing tests** in `tests/test_panel_extensions.py` (record attach/clean-up calls in lists; contribute under `owned_by("px_demo")`; teardown `remove_owner` and close panels):
  - `test_attaches_to_open_and_future_panels`: one time panel open; contribute; attached once; open a second time panel; attached to it too.
  - `test_kinds_filter`: extension with `kinds=("pk_demo.label",)` attaches to the plugin kind (Task 1's test kind pattern) and not to time panels.
  - `test_cleanup_on_close`: `remove_panel(p)` → clean-up called once with nothing else; closing via the dock X too (Review Focus 1).
  - `test_cleanup_on_withdrawal`: `PANEL_EXTENSIONS.remove_owner("px_demo")` → clean-up called for every attached panel; panels stay open.
  - `test_replace_cleans_then_attaches`: contribute the same id again with `replace=True`; old clean-up ran before the new attach (order list).
  - `test_attach_raising_is_contained`: one extension raises in attach, a second works; panel opens; one `log.error` naming the first id; closing the panel runs only the second's clean-up.
  - `test_cleanup_raising_is_contained`.
  - `test_two_windows` (Review Focus 2): build a second `SciQLopMainWindow` while the fixture's is alive (copy `tests/test_dock_contributions.py`'s two-window test and its teardown); open a panel in each; contribute; each window's follower attached only its own panel; destroy the second window with `destroy_main_window`; contribute another extension; no exception (pytest-qt reports slot errors).
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the new file, `tests/test_panel_kinds.py`, the main-window tests (one invocation each). All pass.
- [ ] **Step 5: Commit** `feat(plugins): panel extensions attach to open and future panels and clean up on close and withdrawal`.

---

### Task 4: Saving and restoring any kind; the placeholder panel

**Files:**
- Modify: `SciQLop/components/plotting/panel_template.py`, `SciQLop/components/plotting/time_panel_kind.py` (`to_config`)
- Create: `SciQLop/components/plotting/ui/placeholder_panel.py`
- Test: `tests/test_panel_tree.py` (new); every `tests/test_*template*.py`, `tests/test_proxy_share.py`, `tests/test_welcome*.py` must pass.
- Docs: `ui-and-settings.md` (saving: `panel_tree`, templates of plugin kinds, placeholder).

**Interfaces:**
- Consumes: `PANEL_KINDS`, `open_panel`, `panel_kind_of`, `KIND_PROPERTY` (Task 1).
- Produces:
  - `PanelTemplate` gains `panel_kind: str = TIME_PANEL` and a private `_foreign_root: Optional[dict]` (the raw root node `{kind, config, slots}` of a non-time template). `from_tree`: a non-time root no longer raises; it returns `PanelTemplate(name=..., description=..., plots=[], panel_kind=root.kind)` with `_foreign_root` set. `to_tree`: when `_foreign_root` is set, write it as `"panel"` (with the same top-level `version/name/description` keys). `from_file`, `list_templates`, `find_template`, rename/delete therefore work for any kind unchanged.
  - `PanelTemplate.create_panel(main_window, source_path=None)`: time templates exactly as today; a foreign template → `open_panel(kind, name=self.name, **root["config"])` when the kind is contributed, else `open_placeholder(main_window, root, name=self.name)`. `apply(panel)` keeps its time-panel meaning; on a foreign template it raises `TypeError("... is a <kind> template")`.
  - `panel_tree(widget) -> dict` (module function): a `TimeSyncPanel` → `PanelTemplate.from_panel(widget).to_tree()["panel"]`; a placeholder → its stored root (unchanged); any other kind → `{"kind": k, "config": kind.to_config(widget), "slots": {}}`; a kind without `to_config` → `ValueError(f"panel kind {k!r} cannot be saved")`. `PanelTemplate.from_panel(widget)` for a non-time panel → a foreign template built from `panel_tree(widget)` (name from the widget title).
  - The time kind's `to_config` = `lambda panel: panel_tree(panel)["config"]` — set it in `time_panel_kind.py` (only used by generic callers; templates keep their own path).
  - `placeholder_panel.py`: `PlaceholderPanel(QWidget)` with `root: dict` and `missing_kind: str`; shows `f"This panel needs plugin {plugin_of(kind)!r} (panel kind {kind!r})."`; tagged `KIND_PROPERTY = "sciqlop.placeholder_panel"` (not a contribution). `open_placeholder(main_window, root, name) -> PlaceholderPanel` docks it with `dock_panel(main_window, widget, "sciqlop.placeholder_panel")` after `auto_name`/`setObjectName`/`setWindowTitle` (mirror `open_panel`'s naming). Task 5 adds the install button and the swap.

- [ ] **Step 1: Write the failing tests** in `tests/test_panel_tree.py` (`main_window`, `tmp_path`; a test kind `pt_demo.note` with `create=lambda n, c: QLabel(c.get("text", ""))` and `to_config=lambda w: {"text": w.text()}`):
  - `test_a_plugin_kind_round_trips_through_a_template`: open it with `text="hello"`; `t = PanelTemplate.from_panel(w)`; `t.to_file(tmp/"n.yaml")`; `PanelTemplate.from_file(...)` has `panel_kind == "pt_demo.note"`; `create_panel(main_window)` opens a `QLabel` with text `hello`.
  - `test_a_kind_without_to_config_cannot_be_saved`: `panel_tree(widget)` raises `ValueError` naming the kind.
  - `test_time_templates_are_unchanged`: an existing time template file from the test data (grep tests for a v3 template fixture) loads, saves and reloads with identical `to_tree()` as before (compare with the tree produced by the parent commit's code path: load → to_tree → equal to the file's content).
  - `test_missing_kind_opens_a_placeholder` and `test_the_placeholder_saves_its_tree_back` (Review Focus 3): write a template file whose root kind is `absent.viewer` with a nested config; load it (it appears in `list_templates()` — point `templates_dir` at `tmp_path` the way existing template tests do); `create_panel` opens a `PlaceholderPanel` naming `absent`; `panel_tree(placeholder)` equals the original root; `PanelTemplate.from_panel(placeholder).to_file(other)` writes a file whose `"panel"` equals the original root.
  - `test_apply_refuses_a_foreign_template`.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the new file, the template/proxy-share/welcome tests (one invocation each). All pass.
- [ ] **Step 5: Commit** `feat(plugins): templates save and restore any panel kind; a missing kind restores as a placeholder that keeps its tree`.

---

### Task 5: Install offer and placeholder swap

**Files:**
- Create: `SciQLop/components/plugins/install_offer.py`
- Modify: `SciQLop/components/plotting/ui/placeholder_panel.py`
- Test: `tests/test_panel_install_offer.py` (new); `tests/test_panel_tree.py`, `tests/test_appstore*.py` (grep) must pass.
- Docs: `ui-and-settings.md` (placeholder: install offer; plugin authors: list your panel kinds under `provides["sciqlop.panel_kinds"]` in plugin.json so the offer finds you).

**Interfaces:**
- Consumes: `PlaceholderPanel`, `open_panel`, `PANEL_KINDS`, `plugin_of`.
- Produces:
  - `install_offer.py`: `store_entry_for_kind(kind_id: str, index: list[dict]) -> Optional[dict]` (pure): the first entry whose latest compatible version (`compatible_versions`/`latest_version` from `components/plugins/plugin_registry.py`) lists `kind_id` in `version.get("provides", {}).get("sciqlop.panel_kinds", [])`; else the entry whose `canonical_package_name(entry["name"]) == canonical_package_name(plugin_of(kind_id))`; else `None`. `find_store_entry(kind_id, done: Callable[[Optional[dict]], None])`: runs `fetch_index()` + `store_entry_for_kind` on a daemon thread and delivers `done(entry)` on the main thread (use the project's existing main-thread hand-off; never call Qt from the worker); any exception (offline, timeout, bad JSON) → `done(None)` and `log.warning` once.
  - `PlaceholderPanel`: on construction calls `find_store_entry(missing_kind, self._on_entry)`; `_on_entry(entry)` (guarded with `shiboken6.isValid(self)`) shows an "Install {entry['name']}" button when `entry` is not None. The button installs through the App Store backend (`components/appstore/backend.py` `AppStoreBackend`): read how the store page drives `install_package(name)` and `install_finished`, and reuse that object/path rather than calling pip; disable the button while installing; on `install_finished` with `ok: False` show the error text in the placeholder.
  - Swap: the placeholder connects `PANEL_KINDS.signals.added` (bound slot, `isValid` guard); when the added kind's id equals `missing_kind`, it opens the real panel with `main_window.open_panel(kind_id, name=<its own name after releasing it>, area=<its dock's area>, **root["config"])`, then removes itself with `main_window.remove_panel(self)`. Release its name before `open_panel` so the real panel gets the same name (Review Focus 5). If `open_panel` raises, keep the placeholder and show the error.
  - `simplify:` comment: the lookup refetches the index each time a placeholder opens (no cache).

- [ ] **Step 1: Write the failing tests** in `tests/test_panel_install_offer.py` (no network: monkeypatch `install_offer.fetch_index`; no pip: monkeypatch the backend's install to emit `install_finished` and contribute the kind):
  - `test_lookup_by_provides`, `test_lookup_by_prefix`, `test_lookup_none` (pure `store_entry_for_kind` with small fake indexes; include an incompatible-only version that must be skipped).
  - `test_offline_shows_no_button` (Review Focus 4): `fetch_index` raises `URLError`; the placeholder opens, no install button after `qtbot.waitUntil` on the lookup having completed (expose a flag or check the widget), no exception, one `log.warning`.
  - `test_install_then_swap` (Review Focus 5): fake index with an entry; the button appears; clicking it calls the faked install, which contributes the missing kind; `qtbot.waitUntil(lambda: placeholder not in main_window.panels())`; a panel of the real kind with the same name and the saved config exists in the same dock area as the placeholder was.
  - `test_install_failure_is_shown`: faked install emits `ok: False, error: "boom"`; the placeholder shows `boom` and stays.
  - `test_contribution_without_install_also_swaps`: contributing the kind directly (no click) swaps the placeholder.
- [ ] **Step 2: Run, expect FAIL.**
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** the new file, `tests/test_panel_tree.py`, the appstore tests (one invocation each). All pass.
- [ ] **Step 5: Commit** `feat(plugins): a placeholder panel offers to install its plugin and becomes the real panel when the kind arrives`.

---

### Task 6: Interop proof and spec bookkeeping

**Files:**
- Modify: `tests/test_plugin_interop.py` (one test; reuse `_plugin`, `fresh`, `_OWNERS`; load with the `main_window` fixture; withdraw through `loader._withdraw`)
- Modify: `docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md`: §4.3 row `sciqlop.panel_kinds` + slots → append `; **implemented** as panel kinds + panel extensions (no slot API): docs/superpowers/plans/2026-10-16-panel-kinds-and-extensions.md`; §5 first paragraph: replace "panel kinds and slots beyond the existing time panel come with the panels sub-project" with "panel kinds and panel extensions: docs/superpowers/specs/2026-10-16-panel-kinds-and-extensions-design.md (extensions get the panel widget; no predefined slots)"; §11 bullet "Panel kinds, slots and chrome injection" → "Foreign widget rows inside a time panel: when SciQLopPlots offers an API for them".

- [ ] **Step 1: Write the test** `test_plugin_contributes_a_panel_kind_and_another_extends_it`: plugin `viewer_maker` contributes `PanelKind("viewer_maker.viewer", "Viewer", create=lambda n, c: QLabel(c.get("text", "")), to_config=lambda w: {"text": w.text()})` and `PanelExtension("viewer_maker.badge", attach=<records the panel, returns a clean-up that records too>, kinds=("viewer_maker.viewer",))`; plugin `viewer_user` depends on `viewer_maker`, and in `activate(ctx)` opens `viewer_maker.viewer` through `ctx.main_window.open_panel(...)` (or the user_api `open_panel`) with `text="from user"` and contributes `PanelExtension("viewer_user.time", attach=..., kinds=("sciqlop.time_panel",))`. Assert: owners; the viewer panel exists with the text and has the badge attached; opening a time panel attaches `viewer_user.time`. Then `loader._withdraw("viewer_maker")`: the badge's clean-up ran; the viewer panel is still open (withdrawal leaves open panels, spec §3); `open_panel("viewer_maker.viewer")` raises `LookupError`. Clean up the panels in a `finally`.
- [ ] **Step 2: Run** `tests/test_plugin_interop.py` alone (memory check first); all pass.
- [ ] **Step 3: Update the spec rows** and commit `test(plugins): interop proof for panel kinds and extensions; parent spec rows updated`.
