# Export targets and inspector sections (plan 2b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Plugins add file formats to a panel's Export menu and to `PlotPanel.save`, and add their own sections to the Properties inspector of panels, plots and graphs.

**Architecture:** Two extension points on plan 1a's `ExtensionPoint`:
- `sciqlop.export_targets` holds `ExportTarget` records: a label, file suffixes and a `write(panel, path, width, height, scale)` function. `PlotPanel.save` and the Export submenu both go through one function, `export_panel`. PNG, PDF, JPG and BMP become core contributions owned by `"sciqlop"`. The Speasy proxy share link becomes a built-in palette command placed at the `panel.export` menu location (plan 2a's `sciqlop.menus`).
- `sciqlop.inspector_sections` holds `InspectorSection` records: a title, a target (`panel`, `plot` or `graph`), an `applies(obj)` predicate and a `build(obj, parent) -> QWidget` function. One generic SciQLopPlots `InspectorExtension` subclass shows a contributed section. Sections attach when panels, plots and graphs are created, and follow `added`/`removed`, so a plugin loaded without a restart shows its sections on existing graphs.

Plugin code always receives the published `user_api` objects (`PlotPanel`, `TimeSeriesPlot`/`XYPlot`/`ProjectionPlot`, `Graph`/`ColorMap`/...), never the SciQLopPlots implementation objects.

**Tech Stack:** Python 3.10+, PySide6, SciQLopPlots (`InspectorExtension`, `add_inspector_extension`, `remove_inspector_extension`, `inspector_extensions`, `plot_added`, `graph_list_changed`), pytest + pytest-qt (+ pytest-xvfb).

**Spec:** `docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md`. The sections that matter here:
- §4.3: the tier-2 rows `sciqlop.export_targets` ("Export submenu, `PlotPanel.save` formats, proxy share") and `sciqlop.inspector_sections` ("core-only `add_inspector_extension`"), and the "Menus follow VS Code" paragraph;
- §6: consumers that cache contributions listen to `removed`;
- §7: migration rules.

Plans 1a, 1b, 1c and 2a are implemented and pushed.

## Global Constraints

- Work and commit on `main`, with explicit pathspecs. Never push. Never stage these untracked files: `importlib.metadata`, `setWidget`, `pydata/`, `.claude/`, the untracked `docs/` drafts, `tests/noop_script.py`.
- Run one pytest invocation at a time, in the foreground: `uv run --no-sync pytest <files> -q -p no:cacheprovider`, with Bash `timeout: 600000`. Never `--no-xvfb`. Never `uv sync`. Never edit SciQLopPlots or speasy.
- Write files with the Write/Edit tools. Never use shell heredocs, `cat` or `ls`.
- SciQLop loggers bypass pytest's `caplog`; tests that check a log call monkeypatch the module's `log.warning`/`log.error`.
- Ids: core ids are `sciqlop.<name>`; plugins use `<plugin id>.<name>`. Core contributions are owned by `"sciqlop"` and pass it explicitly (`owner="sciqlop"` or `owned_by("sciqlop")`). Extension points are main-thread objects.
- Published API keeps working (spec §7): `PlotPanel.save(path, *, width=0, height=0, scale=None)` keeps its signature, its errors (`ValueError` mentioning "Unsupported" for an unknown suffix, `ValueError` mentioning "raster" for `scale` on PDF, `OSError` when the write fails) and its default scale (the screen's pixel ratio).
- Qt lifetimes (`docs/qt-lifetime-patterns.md`): never connect an app-lifetime signal (an extension point's `added`/`removed`) to a widget's bound method; connect module-level functions. A Python `InspectorExtension` subclass keeps its state in Qt storage (`objectName()`, `parent()`), never in Python attributes, because Shiboken can hand back a fresh wrapper with an empty `__dict__` (see the docstring of `SciQLop/components/plotting/ui/graph_context_inspector/extension.py`).
- Plugin-author docs move with the code (spec §7): `SciQLop/components/agents/skills/sciqlop-plugin-design/` changes in the same commit as the code it documents.
- Code style (CLAUDE.md): small functions, data over code, no comment-decorated blocks, a `simplify:` comment on deliberate shortcuts.
- Commit trailer: `Co-Authored-By: <the model writing the commit> <noreply@anthropic.com>`.

## Review Focus

1. **A plugin contributes a target for a suffix the core already handles** (say `.png`). `panel.save("x.png")` keeps using the core PNG writer; the plugin's target still shows in the menu under its own label. → Task 1.
2. **The user types a file name without a suffix in the Export dialog.** The target's first suffix is appended; the file is not written suffix-less. → Task 2.
3. **A plugin section whose `applies` or `build` raises.** The inspector still opens; other sections still show; the failing `build` shows a one-line "failed" label and logs the error. → Task 3.
4. **A plugin installed or enabled while SciQLop runs** contributes a graph section. Graphs that already exist show it without being re-plotted; withdrawing the plugin's contributions removes it. → Task 3.
5. **A graph or plot is removed while it carries a contributed section.** No crash, no error on the next `added`/`removed` walk. → Task 3.

---

## File map

| File | Role | Task |
|---|---|---|
| `SciQLop/core/export_targets.py` | `ExportTarget`, `EXPORT_TARGETS` extension point, `target_for(path)` | 1 |
| `SciQLop/components/plotting/export.py` | core PNG/PDF/JPG/BMP targets, `export_panel(...)` | 1 |
| `SciQLop/user_api/plot/_panel.py` | `PlotPanel.save` delegates to `export_panel`; `wrap_plot` extracted to module level | 1, 3 |
| `SciQLop/components/extension_points.py` | declares the two new EPs; wires the inspector follower | 1, 3 |
| `SciQLop/components/plotting/ui/time_sync_panel.py` | Export submenu built from targets; proxy share moves out; sections attached on panel/plot/graph creation | 2, 3 |
| `SciQLop/components/plotting/ui/proxy_share.py` | `open_in_speasy_viewer` command, its menu entry and `proxy_url_of(panel)` | 2 |
| `SciQLop/components/command_palette/commands.py` | registers the proxy command and its menu entry | 2 |
| `SciQLop/core/inspector_sections.py` | `InspectorSection`, `INSPECTOR_SECTIONS` extension point | 3 |
| `SciQLop/components/plotting/ui/contributed_sections.py` | `ContributedSection(InspectorExtension)`, `attach_sections`, follower | 3 |
| `tests/test_export_targets.py`, `tests/test_inspector_sections.py`, `tests/test_proxy_share.py`, `tests/test_plugin_interop.py` | tests | 1–4 |
| `SciQLop/components/agents/skills/sciqlop-plugin-design/references/ui-and-settings.md`, `SKILL.md` | plugin-author docs | 2, 3, 4 |
| spec §4.3 table | rows marked implemented | 4 |

---

### Task 1: `sciqlop.export_targets`, with `PlotPanel.save` as its adapter

**Files:**
- Create: `SciQLop/core/export_targets.py`
- Create: `SciQLop/components/plotting/export.py`
- Modify: `SciQLop/user_api/plot/_panel.py` (`PlotPanel.save`, ~line 887)
- Modify: `SciQLop/components/extension_points.py` (`prepare_extension_points`)
- Test: `tests/test_export_targets.py` (new); `tests/test_panel_save.py` must pass unchanged.

**Interfaces:**
- Produces:
  - `ExportTarget(id: str, label: str, suffixes: tuple[str, ...], write: Callable[[PlotPanel, str, int, int, Optional[float]], None], scalable: bool = True)`. `suffixes` are lowercase and start with a dot. `write` raises on failure. `scale` is `None` exactly when `scalable` is False.
  - `EXPORT_TARGETS` (id `sciqlop.export_targets`).
  - `target_for(path: str) -> Optional[ExportTarget]`: the target owning the path's suffix, case-insensitive. On a suffix several targets claim, the `"sciqlop"`-owned one wins, then the smallest id.
  - `export_panel(panel: PlotPanel, path: str, *, width: int = 0, height: int = 0, scale: Optional[float] = None) -> None` in `SciQLop/components/plotting/export.py`.
  - Core target ids: `sciqlop.png` (`.png`), `sciqlop.pdf` (`.pdf`, `scalable=False`), `sciqlop.jpg` (`.jpg`, `.jpeg`), `sciqlop.bmp` (`.bmp`). Labels: `PNG`, `PDF`, `JPEG`, `BMP`.

- [ ] **Step 1: Write the failing tests** in `tests/test_export_targets.py`:

```python
"""sciqlop.export_targets (spec §4.3): file formats for PlotPanel.save and the Export menu."""
from .fixtures import *  # noqa: F401,F403
import pytest

from SciQLop.core.export_targets import EXPORT_TARGETS, ExportTarget, target_for
from SciQLop.core.extensions import owned_by


@pytest.fixture
def csv_target(qapp):
    written = []
    with owned_by("et_demo"):
        EXPORT_TARGETS.contribute(ExportTarget(
            "et_demo.csv", "CSV", (".csv",),
            write=lambda panel, path, w, h, s: written.append((panel, path, w, h, s)),
            scalable=False))
    yield written
    EXPORT_TARGETS.remove_owner("et_demo")


def test_core_targets_cover_the_formats_save_always_had(qapp):
    for suffix in (".png", ".pdf", ".jpg", ".jpeg", ".bmp"):
        assert EXPORT_TARGETS.owner_of(target_for(f"x{suffix}").id) == "sciqlop"


def test_suffix_lookup_ignores_case(csv_target):
    assert target_for("A.CSV").id == "et_demo.csv"


def test_save_writes_through_a_plugin_target(plot_panel, csv_target, tmp_path):
    plot_panel.save(str(tmp_path / "a.csv"), width=10, height=20)
    (panel, path, w, h, s), = csv_target
    assert panel is plot_panel and path.endswith("a.csv") and (w, h, s) == (10, 20, None)


def test_a_core_suffix_claimed_by_a_plugin_stays_core(qapp):
    with owned_by("et_demo"):
        EXPORT_TARGETS.contribute(ExportTarget("et_demo.png", "Fancy PNG", (".png",), write=lambda *a: None))
    try:
        assert target_for("x.png").id == "sciqlop.png"
    finally:
        EXPORT_TARGETS.remove_owner("et_demo")


def test_unknown_suffix_error_lists_plugin_suffixes(plot_panel, csv_target, tmp_path):
    with pytest.raises(ValueError, match=r"Unsupported.*\.csv"):
        plot_panel.save(str(tmp_path / "a.svg"))


def test_scale_is_refused_by_a_non_scalable_plugin_target(plot_panel, csv_target, tmp_path):
    with pytest.raises(ValueError, match="raster"):
        plot_panel.save(str(tmp_path / "a.csv"), scale=2.0)


def test_suffixes_are_validated(qapp):
    with pytest.raises(ValueError):
        ExportTarget("et_demo.bad", "Bad", ("csv",), write=lambda *a: None)
```

- [ ] **Step 2: Run them; they fail** (`ModuleNotFoundError: SciQLop.core.export_targets`).

Run: `uv run --no-sync pytest tests/test_export_targets.py -q -p no:cacheprovider`

- [ ] **Step 3: Write `SciQLop/core/export_targets.py`:**

```python
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
```

- [ ] **Step 4: Write `SciQLop/components/plotting/export.py`:** the four core targets and `export_panel`. The core writers call the impl methods exactly as `PlotPanel.save` did (`save_png/save_jpg/save_bmp(path, width, height, scale)`, `save_pdf(path, width, height)`) and raise `OSError(f"failed to save {path!r}: check that the directory exists and is writable")` when the impl returns falsy.

```python
"""Saving a panel to a file: the core export targets and the one function PlotPanel.save and the menu share."""
from __future__ import annotations

from typing import Optional

from SciQLop.core.export_targets import EXPORT_TARGETS, ExportTarget, known_suffixes, target_for


def _checked(ok: bool, path: str) -> None:
    if not ok:
        raise OSError(f"failed to save {path!r}: check that the directory exists and is writable")


def _raster(method: str):
    def write(panel, path, width, height, scale):
        _checked(getattr(panel._get_impl_or_raise(), method)(path, width, height, scale), path)
    return write


def _pdf(panel, path, width, height, scale):
    _checked(panel._get_impl_or_raise().save_pdf(path, width, height), path)


CORE_TARGETS = (
    ExportTarget("sciqlop.png", "PNG", (".png",), _raster("save_png")),
    ExportTarget("sciqlop.pdf", "PDF", (".pdf",), _pdf, scalable=False),
    ExportTarget("sciqlop.jpg", "JPEG", (".jpg", ".jpeg"), _raster("save_jpg")),
    ExportTarget("sciqlop.bmp", "BMP", (".bmp",), _raster("save_bmp")),
)

for _target in CORE_TARGETS:
    if _target.id not in EXPORT_TARGETS:
        EXPORT_TARGETS.contribute(_target, owner="sciqlop")


def export_panel(panel, path: str, *, width: int = 0, height: int = 0, scale: Optional[float] = None) -> None:
    target = target_for(path)
    if target is None:
        raise ValueError(f"Unsupported format for {path!r}. Use one of: {', '.join(known_suffixes())}")
    if not target.scalable and scale is not None:
        raise ValueError(f"scale only applies to raster formats; give width and height for {target.label}")
    if target.scalable and scale is None:
        scale = panel._get_impl_or_raise().devicePixelRatioF()
    target.write(panel, path, width, height, scale)
```

Check `ExtensionPoint.contribute`'s real signature in `SciQLop/core/extensions.py` before relying on `owner=`; match how `components/plotting/core_kinds.py` contributes its core kind and make the module import idempotent the same way.

- [ ] **Step 5: Make `PlotPanel.save` an adapter.** Keep the signature and the docstring's Parameters/Examples; change the format sentence to "The format comes from the file extension: .png, .pdf, .jpg, .jpeg, .bmp, plus any format a loaded plugin adds." The body becomes:

```python
        from SciQLop.components.plotting.export import export_panel
        export_panel(self, path, width=width, height=height, scale=scale)
```

- [ ] **Step 6: Declare the EP at startup.** In `prepare_extension_points`, after the `core.menus` import, add `import SciQLop.components.plotting.export  # noqa: F401  declares sciqlop.export_targets, contributes the core formats`.

- [ ] **Step 7: Run** `tests/test_export_targets.py tests/test_panel_save.py`; all pass.

- [ ] **Step 8: Commit** `feat(plugins): file formats are contributions to sciqlop.export_targets; PlotPanel.save writes through them`.

---

### Task 2: The Export submenu lists the targets; the Speasy share link is a command at `panel.export`

**Files:**
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py` (`_build_export_share_menu` ~1500, `_add_proxy_share_actions` ~1515, `_export_png`/`_export_pdf` ~1563-1580)
- Modify: `SciQLop/components/plotting/ui/proxy_share.py`
- Modify: `SciQLop/components/command_palette/commands.py` (`register_builtin_commands`)
- Modify: `tests/test_proxy_share.py` (the two tests at ~123 and ~138 that call `_add_proxy_share_actions`)
- Test: `tests/test_export_targets.py` (menu tests appended)
- Docs: `references/ui-and-settings.md` gains an "Export targets" section (fields, the `write` contract, the suffix precedence rule, a 10-line example plugin contributing a `.csv` target through `ctx.contribute("sciqlop.export_targets", ...)`).

**Interfaces:**
- Consumes: `EXPORT_TARGETS`, `export_panel` (Task 1); `MenuEntry`, `PANEL_EXPORT`, `MENUS` (`SciQLop/core/menus.py`); `PaletteCommand`, `PanelArg`.
- Produces:
  - `TimeSyncPanel._export_to(target: ExportTarget) -> None`: the dialog flow for one target.
  - In `proxy_share.py`: `proxy_url_of(panel) -> Optional[str]` (the proxy URL of a panel object, `None` when there is no proxy URL configured or nothing shareable; this is what `_add_proxy_share_actions` computed), `open_in_speasy_viewer(panel: str = "")` (the command callback: resolves the panel by name through the main window and opens `proxy_url_of`), and `register_proxy_share(registry)` which registers the command `sciqlop.open_in_speasy_viewer` (name "Open in Speasy web viewer", description "Open this panel as a shareable Speasy proxy web page.", `args=[PanelArg(name="panel")]`) and contributes `MenuEntry("sciqlop.open_in_speasy_viewer", PANEL_EXPORT, "sciqlop.open_in_speasy_viewer", when=<the panel named by context["panel"] has a proxy_url_of>)`.
  - `_speasy_proxy_url` moves from `time_sync_panel.py` to `proxy_share.py` (tests monkeypatch it there).

Behaviour of the submenu, in order:
1. One action per export target, sorted by `_precedence` (core first, then id), labelled `f"Export as {target.label}…"` with tooltip `f"Save this panel as {target.label} ({', '.join(target.suffixes)})."`.
2. `add_graph_context_actions(sub, self)` (unchanged).
3. `add_menu_entries(sub, PANEL_EXPORT, self._menu_context())` — the Speasy link now comes from here.

`_export_to(target)`:
- `QFileDialog.getSaveFileName(self, f"Export as {target.label}", f"{self.name}{target.suffixes[0]}", f"{target.label} ({' '.join('*' + s for s in target.suffixes)})")`. Use `self.name`, not `windowTitle()`: a Properties rename does not update the window title.
- No path: return. A path whose suffix is not one of `target.suffixes`: append `target.suffixes[0]`.
- `export_panel(PlotPanel(self), path)`; on any exception, log it with `log.error(..., exc_info=True)` and show `QMessageBox.warning(self, "Export failed", str(exc))`.

Delete `_export_png`, `_export_pdf` and `_add_proxy_share_actions` (grep shows no other callers except the two proxy tests, which this task rewrites).

- [ ] **Step 1: Write the failing tests.** Append to `tests/test_export_targets.py`:
  - `test_the_export_submenu_lists_every_target`: with `csv_target`, build `panel._build_export_share_menu(QMenu())` on `plot_panel._get_impl_or_raise()`, find the "Export" submenu, assert its first five non-separator action texts are `["Export as PNG…", "Export as PDF…", "Export as JPEG…", "Export as BMP…", "Export as CSV…"]`.
  - `test_export_appends_the_suffix_the_user_left_out`: monkeypatch `QFileDialog.getSaveFileName` (in the module `time_sync_panel` imports it from) to return `(str(tmp_path / "quicklook"), "")`, trigger "Export as CSV…", assert the recorded path ends with `quicklook.csv`.
  - `test_a_failing_export_is_shown_not_raised`: a target whose `write` raises `OSError("disk full")`; monkeypatch the dialog and `QMessageBox.warning` to record; trigger; assert the warning got `"disk full"`.

  Rewrite the two proxy tests in `tests/test_proxy_share.py`:
  - `test_export_share_menu_opens_proxy_url_in_browser` → `test_proxy_url_of_a_panel_with_speasy_graphs`: monkeypatch `proxy_share._speasy_proxy_url`, assert `proxy_url_of(panel).startswith("http://proxy/cache/plot?config=")`; then monkeypatch the main-window lookup used by `open_in_speasy_viewer` to return `panel` and `QDesktopServices.openUrl` (as imported in `proxy_share`) to record; call `open_in_speasy_viewer("P")`; assert one URL opened with that prefix.
  - `test_export_share_menu_hides_proxy_actions_without_speasy_graphs` → `test_no_proxy_url_without_speasy_graphs`: same fake panel, assert `proxy_url_of(p) is None`.
  - New `test_the_share_link_entry_is_shown_only_for_shareable_panels(main_window, ...)`: the `when` of the `sciqlop.open_in_speasy_viewer` entry returns False for a panel with nothing shareable (a fresh `main_window.new_plot_panel()`), and the command exists in `COMMANDS`.

- [ ] **Step 2: Run** `tests/test_export_targets.py tests/test_proxy_share.py`; the new tests fail.

- [ ] **Step 3: Implement** the submenu, `_export_to`, the `proxy_share.py` functions, and call `register_proxy_share(registry)` at the end of `register_builtin_commands` (it already runs inside `owned_by("sciqlop")` from `start_plugins`; contribute the menu entry with `owner="sciqlop"` explicitly so a test calling it outside that block still owns it correctly).

- [ ] **Step 4: Run** `tests/test_export_targets.py tests/test_proxy_share.py tests/test_menu_entries.py tests/test_panel_save.py`; all pass.

- [ ] **Step 5: Commit** `feat(plugins): the Export menu lists every export target; the Speasy share link is a command placed at panel.export`.

---

### Task 3: `sciqlop.inspector_sections`

**Files:**
- Create: `SciQLop/core/inspector_sections.py`
- Create: `SciQLop/components/plotting/ui/contributed_sections.py`
- Modify: `SciQLop/user_api/plot/_panel.py` (extract the nested `wrap_plot` of `PlotPanel.plots` to a module-level `wrap_plot(impl)`; `plots` uses it)
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py` (attach on panel creation, `plot_added`, and each plot's `graph_list_changed`)
- Modify: `SciQLop/components/extension_points.py` (declare; call `follow_inspector_sections()`)
- Test: `tests/test_inspector_sections.py` (new)
- Docs: `references/ui-and-settings.md` gains an "Inspector sections" section; `SKILL.md` lists both new EPs where it lists the others.

**Interfaces:**
- Produces:
  - `InspectorSection(id: str, title: str, target: str, build: Callable[[obj, QWidget], QWidget], applies: Callable[[obj], bool] = <always True>, priority: int = 0)`. `target` is one of `PANEL_TARGET, PLOT_TARGET, GRAPH_TARGET = "panel", "plot", "graph"`; anything else raises `ValueError` in `__post_init__`. `priority` must be an int (`TypeError` otherwise, like `MenuEntry.order`).
  - `INSPECTOR_SECTIONS` (id `sciqlop.inspector_sections`).
  - `ContributedSection(InspectorExtension)`: `__init__(section_id, host)` sets `objectName(section_id)` and `parent=host`; `section_title()` and `priority()` read `INSPECTOR_SECTIONS.get(self.objectName())`; `build_widget(parent)` wraps `self.parent()` into its `user_api` object and calls `section.build(obj, parent)`; on any exception it logs with `log.error(..., exc_info=True)` and returns `QLabel(f"{title}: failed to build, see the log", parent)`.
  - `attach_sections(host, target: str) -> None`: adds a `ContributedSection` for every section of that target that `applies` to the wrapped host and is not already on the host (compare `objectName()` of `host.inspector_extensions()`). A raising `applies` is logged and counts as False.
  - `follow_inspector_sections() -> None`: idempotent; connects `INSPECTOR_SECTIONS.signals.added` to a module function that attaches the new section to every existing host, and `removed` to one that calls `remove_inspector_extension` and `deleteLater()` on every `ContributedSection` with that id.
  - Hosts are walked from the main window: `plot_panels()` names → `plot_panel(name)` → its `plots()` → each plot's `plottables()`. Skip objects `shiboken6.isValid` says are gone.
  - Wrapping for plugin code: panel → `PlotPanel(impl)`; plot → `wrap_plot(impl)` (skip the section when it returns `None`); graph → `to_plottable(impl, plot)` from `SciQLop/user_api/plot/_graphs.py`.

Keepalive: Python-subclass extensions must stay referenced (graph_context_inspector docstring). Keep each `ContributedSection` in a module-level `set` and discard it from the extension's own `destroyed` signal (`ext.destroyed.connect(lambda *_, e=ext: _alive.discard(e))`). `simplify:` comment: the set holds wrappers of every live section, O(sections × hosts) memory; fine until thousands of graphs.

Attaching in `time_sync_panel.py`: in `TimeSyncPanel.__init__`, next to the other `plot_added` connections (~1281): `attach_sections(self, PANEL_TARGET)`, and `self.plot_added.connect(_attach_plot_sections)` where the module-level `_attach_plot_sections(plot)` calls `attach_sections(plot, PLOT_TARGET)`, attaches the graph sections of the plot's current plottables, and connects `plot.graph_list_changed` with the plot as receiver context to a function that re-runs the graph attach for that plot (attach is idempotent, so re-running on every change is correct). Verify `graph_list_changed` and `plottables()` exist on the plot types used (`SciQLopPlot`, projection and XY plots) by introspection before relying on them; record what you find in the report.

- [ ] **Step 1: Write the failing tests** in `tests/test_inspector_sections.py`, using the `plot_panel` fixture and `owned_by("is_demo")` with `INSPECTOR_SECTIONS.remove_owner("is_demo")` in teardown. Helper `_sections(host)` returns the `objectName()`s of `host.inspector_extensions()` that are `ContributedSection`s. Tests:
  - `test_a_graph_section_appears_on_new_graphs`: contribute a graph section, plot a line (`plot_panel.plot_data(x, y)` or the user_api call the `plot_panel` fixture tests already use — grep `tests/` for one), assert the section id is on the graph impl; call its `build_widget(QWidget())` and assert the `build` callback received a `user_api` `Graph`.
  - `test_applies_filters_and_a_raising_applies_is_skipped`: two sections, one `applies=lambda g: False`, one raising; neither attaches; the raising one is logged (monkeypatch `contributed_sections.log.error`).
  - `test_a_raising_build_shows_a_failed_label`: `build` raises; `build_widget` returns a `QLabel` whose text contains "failed".
  - `test_a_section_contributed_later_reaches_existing_graphs`: plot first, then contribute; the section is on the existing graph.
  - `test_withdrawing_removes_the_section`: after `remove_owner("is_demo")`, the id is gone from the graph's extensions.
  - `test_panel_and_plot_targets`: a panel section is on the panel impl with a `PlotPanel` passed to `build`; a plot section is on each plot.
  - `test_removing_a_graph_with_a_section_is_safe`: attach, remove the plot from the panel (or delete the graph), `qtbot.wait(0)`, then contribute and withdraw another section; nothing raises.
  - `test_target_and_priority_are_validated`.

- [ ] **Step 2: Run** `tests/test_inspector_sections.py`; it fails on the missing module.

- [ ] **Step 3: Implement** `core/inspector_sections.py`, `contributed_sections.py`, the `wrap_plot` extraction, the `time_sync_panel.py` hooks and the startup wiring.

- [ ] **Step 4: Run** `tests/test_inspector_sections.py tests/test_graph_context_integration.py tests/test_plotting/test_knob_delegates.py`; all pass.

- [ ] **Step 5: Commit** `feat(plugins): inspector sections are contributions to sciqlop.inspector_sections, shown on panels, plots and graphs`.

---

### Task 4: Interop proof and spec bookkeeping

**Files:**
- Modify: `tests/test_plugin_interop.py` (or the file plan 2a used for its interop proof — grep for the commands/menus interop test and extend it)
- Modify: `docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md` §4.3 table
- Docs: `SKILL.md` checked for both EPs (Task 3 added them; fix anything missing)

- [ ] **Step 1: Write the interop test.** A test plugin folder (follow the existing interop test's pattern for writing a plugin to `tmp_path` and loading it through the loader) whose `activate(ctx)` contributes `ExportTarget("<id>.txt", "Text", (".txt",), write=...)` writing the panel name to the file, and an `InspectorSection("<id>.note", "Note", "panel", build=lambda panel, parent: QLabel(panel.name, parent))`. Assert: `plot_panel.save(tmp_path / "p.txt")` writes the panel name; the panel impl carries the `<id>.note` section; withdrawing the plugin's contributions (the same call the loader uses when an activation fails, `remove_owner` on every EP) removes both.

- [ ] **Step 2: Run** the interop test file; it passes.

- [ ] **Step 3: Spec.** In the §4.3 table, append "; **implemented**: docs/superpowers/plans/2026-10-15-export-targets-inspector-sections.md" to the `sciqlop.export_targets` and `sciqlop.inspector_sections` rows.

- [ ] **Step 4: Commit** `test(plugins): interop proof for export targets and inspector sections; spec rows marked implemented`.
