# Tier 3b: template formats, time presets, themes — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Three hard-coded lists become extension points: template file formats, time-range presets and themes. Every duplicated copy derives from its point, and plugins can add to each.

**Architecture:** One small module per point declares the `ExtensionPoint` and contributes the core values under `CORE_OWNER` when imported. The old sites (six template-suffix checks, three duration tables, three palette-name lists and the palette loader) read the point. UI that is built once (the time-range bar's combo, the settings combo, the active theme) follows `added`/`removed`.

**Tech Stack:** Python 3.14, PySide6, pydantic, PyYAML, pytest + pytest-qt (+ pytest-xvfb on Linux).

**Spec:** `docs/superpowers/specs/2026-10-16-tier3-extension-points-design.md` §4 (parent: `docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md`).

## Global Constraints

- Approach A: the extension point is the source of truth; existing public functions keep their signatures.
- `panel.duration = "7d"` keeps working; zoom limits (`ZOOM_LIMIT_PRESETS`) stay core-only.
- The saved theme setting is never overwritten by a fallback; the fallback theme is `space`.
- `user_api.themes` keeps `apply_theme`, `current_theme`, `list_themes`; `PaletteName` becomes `str`.
- Process-lifetime EP signals connect to plain functions or to slots guarded by `shiboken6.isValid(self)`.
- Core contributions use `CORE_OWNER` (`SciQLop.core.name_follower.CORE_OWNER == "sciqlop"`).
- `SciQLop/components/plotting/panel_template.py` must stay importable without a QApplication (the remote worker imports it): new modules it imports may import `PySide6.QtCore` (as `SciQLop.core.extensions` does) but not `QtWidgets`/`QtGui`.
- Run tests with `uv run pytest` (never `--no-xvfb`), one invocation at a time, in the foreground. Never `uv sync`.
- Commit on `main` with explicit pathspecs; end each commit message with `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`. Never push.

## Rulings made while writing this plan

- `TimePreset` gets an optional `description` used by the command palette ("Last hour"), falling back to `"Last <label>"`. The spec says the palette shows "Last <label>"; `tests/test_command_palette_arg_types.py` pins "Last hour"/"Last day", and those phrases read better, so the core presets keep them.
- The duration combo lists presets sorted by length, so a plugin's "3d" lands between "1d" and "7d".
- Settings combos fed by a point show each item's `label` when it has one (themes do), else its key.

## Review Focus

- A theme `.yaml` that exists but is not a mapping (e.g. a list) is refused when contributed, not when applied (Task 3 test).
- The saved theme names a plugin theme whose plugin is never installed: SciQLop starts on `space` and stays there (Task 3 test).
- The active theme is withdrawn while the settings page is open: the combo drops it and the app is on `space` (Task 4 test).
- A preset added while a panel's bar shows "1d" keeps "1d" selected (Task 2 test).
- A template file with an unknown suffix in the templates folder is ignored by `list_templates`, not an error (Task 1 test).

---

### Task 1: `sciqlop.template_formats`

**Files:**
- Create: `SciQLop/components/plotting/template_formats.py`
- Modify: `SciQLop/components/plotting/panel_template.py:174-192` (reader and `_load_yaml`), `:224-233` (`to_file`), `:456` and its two users (`list_templates`, near line 469; the lookup near line 492)
- Modify: `SciQLop/user_api/templates.py:13-17`
- Modify: `SciQLop/user_api/plot/_panel.py:921-923` (`save_template`)
- Modify: `SciQLop/components/welcome/backend.py:342` (import dialog filter)
- Test: `tests/test_template_formats.py`

**Interfaces:**
- Produces: `TEMPLATE_FORMATS` (id `sciqlop.template_formats`); `TemplateFormat(id: str, label: str, suffixes: tuple[str, ...], loads: Callable[[str], dict], dumps: Callable[[dict], str])`; `format_for(path: Path) -> TemplateFormat` (raises `ValueError`); `template_suffixes() -> tuple[str, ...]`; `file_dialog_filter() -> str`.

- [ ] **Step 1: Write the failing tests**

```python
"""Template file formats are contributions to sciqlop.template_formats (Tier 3 spec §4.1)."""
import json
from pathlib import Path

import pytest

from SciQLop.components.plotting import panel_template
from SciQLop.components.plotting.panel_template import PanelTemplate, PlotModel, ProductModel
from SciQLop.components.plotting.template_formats import (TEMPLATE_FORMATS, TemplateFormat, file_dialog_filter,
                                                          format_for, template_suffixes)
from SciQLop.core.extensions import owned_by


def _template(name="tf_demo"):
    return PanelTemplate(name=name, plots=[PlotModel(products=[ProductModel(path="speasy//amda//imf",
                                                                            kind="speasy", graph_type="Line",
                                                                            y_axis="y")])])


@pytest.fixture
def plugin_format(qapp):
    with owned_by("tf_demo"):
        TEMPLATE_FORMATS.contribute(TemplateFormat("tf_demo.jsonl", "JSON on one line", (".tpl",),
                                                   loads=json.loads, dumps=json.dumps))
    yield
    TEMPLATE_FORMATS.remove_owner("tf_demo")


def test_the_core_formats_cover_today_s_suffixes():
    assert set(template_suffixes()) >= {".json", ".yaml", ".yml"}
    assert format_for(Path("a.yml")).id == "yaml"
    assert "*.json" in file_dialog_filter() and "*.yml" in file_dialog_filter()


def test_an_unknown_suffix_lists_the_supported_ones():
    with pytest.raises(ValueError, match=r"Unsupported file extension: \.txt.*\.json"):
        format_for(Path("a.txt"))


def test_a_plugin_format_round_trips_a_template(plugin_format, tmp_path):
    path = tmp_path / "demo.tpl"
    _template().to_file(str(path))
    assert json.loads(path.read_text())["name"] == "tf_demo"
    assert PanelTemplate.from_file(str(path)).name == "tf_demo"


def test_templates_in_a_plugin_format_are_listed_until_it_is_withdrawn(plugin_format, monkeypatch, tmp_path):
    monkeypatch.setattr(panel_template, "templates_dir", lambda: tmp_path)
    _template("tf_listed").to_file(str(tmp_path / "tf_listed.tpl"))
    assert "tf_listed" in [t.name for t in panel_template.list_templates()]
    TEMPLATE_FORMATS.remove_owner("tf_demo")
    assert "tf_listed" not in [t.name for t in panel_template.list_templates()]
    assert (tmp_path / "tf_listed.tpl").exists()


def test_an_unknown_suffix_in_the_templates_folder_is_ignored(monkeypatch, tmp_path):
    monkeypatch.setattr(panel_template, "templates_dir", lambda: tmp_path)
    (tmp_path / "notes.txt").write_text("not a template")
    _template("tf_json").to_file(str(tmp_path / "tf_json.json"))
    assert [t.name for t in panel_template.list_templates()] == ["tf_json"]


def test_user_api_load_reads_a_plugin_format_file(plugin_format, tmp_path):
    from SciQLop.user_api import templates
    path = tmp_path / "demo.tpl"
    _template().to_file(str(path))
    assert templates.load(str(path)).name == "tf_demo"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_template_formats.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'SciQLop.components.plotting.template_formats'`.

- [ ] **Step 3: Create `SciQLop/components/plotting/template_formats.py`**

Move `_load_yaml` here from `panel_template.py` (unchanged body) and declare the point:

```python
"""Panel template file formats: the sciqlop.template_formats extension point (Tier 3 spec §4.1)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from SciQLop.core.extensions import ExtensionPoint, declare, owned_by
from SciQLop.core.name_follower import CORE_OWNER


@dataclass(frozen=True)
class TemplateFormat:
    id: str
    label: str
    suffixes: tuple[str, ...]
    loads: Callable[[str], dict]
    dumps: Callable[[dict], str]


TEMPLATE_FORMATS = declare(ExtensionPoint("sciqlop.template_formats", TemplateFormat, what="template format",
                                          doc="Panel template file formats by id; each lists its suffixes."))


def template_suffixes() -> tuple[str, ...]:
    return tuple(s for fmt in TEMPLATE_FORMATS.list() for s in fmt.suffixes)


def format_for(path: Path) -> TemplateFormat:
    fmt = next((f for f in TEMPLATE_FORMATS.list() if path.suffix in f.suffixes), None)
    if fmt is None:
        raise ValueError(f"Unsupported file extension: {path.suffix} (supported: {', '.join(template_suffixes())})")
    return fmt


def file_dialog_filter() -> str:
    return f"Templates ({' '.join(f'*{s}' for s in template_suffixes())})"


def _load_yaml(text: str):
    """Templates saved before 0.14.2 wrote ranges as !!python/tuple, which
    safe_load rejects; read those as plain lists."""
    import yaml

    class Loader(yaml.SafeLoader):
        pass

    Loader.add_constructor("tag:yaml.org,2002:python/tuple", Loader.construct_sequence)
    return yaml.load(text, Loader=Loader)


def _dump_yaml(tree: dict) -> str:
    import yaml
    return yaml.dump(tree, default_flow_style=False, sort_keys=False)


with owned_by(CORE_OWNER):
    TEMPLATE_FORMATS.contribute(TemplateFormat("json", "JSON", (".json",), loads=json.loads,
                                               dumps=lambda tree: json.dumps(tree, indent=2)))
    TEMPLATE_FORMATS.contribute(TemplateFormat("yaml", "YAML", (".yaml", ".yml"), loads=_load_yaml,
                                               dumps=_dump_yaml))
```

- [ ] **Step 4: `panel_template.py` reads the point**

Import at the top: `from SciQLop.components.plotting.template_formats import format_for, template_suffixes`.
Delete `_load_yaml` there (it moved). Replace the reader and `to_file`:

```python
def _read_template_data(p: Path) -> dict:
    return format_for(p).loads(p.read_text())
```

```python
    def to_file(self, path: str) -> None:
        p = Path(path)
        p.write_text(format_for(p).dumps(self.to_tree()))
```

Delete `_TEMPLATE_EXTENSIONS = ('.json', '.yaml', '.yml')` and replace both `for ext in _TEMPLATE_EXTENSIONS:` loops
with `for ext in template_suffixes():`. Grep the file for any other `_load_yaml` or `'.json'` use and route it the same
way; `grep -rn "_load_yaml" SciQLop tests` must show only `template_formats.py` afterwards (update any test importing
it from `panel_template` to import it from `template_formats`).

- [ ] **Step 5: The three outside sites read the point**

`SciQLop/user_api/templates.py`:

```python
def load(name_or_path: str) -> PanelTemplate | None:
    from SciQLop.components.plotting.template_formats import template_suffixes
    p = Path(name_or_path)
    if p.suffix in template_suffixes() and p.exists():
        return PanelTemplate.from_file(str(p))
    return _find_template(name_or_path)
```

`SciQLop/user_api/plot/_panel.py` `save_template` (lines 921-923):

```python
        from SciQLop.components.plotting.template_formats import template_suffixes
        if '/' not in name_or_path and '\\' not in name_or_path:
            suffix = next((s for s in template_suffixes() if name_or_path.endswith(s)), "")
            t.name = name_or_path.removesuffix(suffix) if suffix else name_or_path
            if not suffix:
                name_or_path = name_or_path + '.json'
            name_or_path = str(templates_dir() / name_or_path)
```

`SciQLop/components/welcome/backend.py` (the import dialog, line 342): replace the literal
`"Templates (*.json *.yaml *.yml)"` with `file_dialog_filter()`, imported next to `PanelTemplate` in that method:
`from SciQLop.components.plotting.template_formats import file_dialog_filter`.

- [ ] **Step 6: Run the template tests**

Run: `uv run pytest tests/test_template_formats.py tests/test_panel_tree.py $(ls tests/test_*template*.py) -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add SciQLop/components/plotting/template_formats.py tests/test_template_formats.py
git commit SciQLop/components/plotting/template_formats.py SciQLop/components/plotting/panel_template.py SciQLop/user_api/templates.py SciQLop/user_api/plot/_panel.py SciQLop/components/welcome/backend.py tests/test_template_formats.py -m "feat(plugins): template file formats are contributions to sciqlop.template_formats; six suffix lists become one"
```

(Add any test file you changed for the `_load_yaml` move to the pathspec.)

---

### Task 2: `sciqlop.time_presets`

**Files:**
- Create: `SciQLop/core/time_presets.py`
- Modify: `SciQLop/components/plotting/ui/time_range_bar.py:11,23-29,87-88,95-182`
- Modify: `SciQLop/components/command_palette/arg_types.py:176-187` (`TimeRangeArg.completions`)
- Modify: `SciQLop/components/command_palette/commands.py:35-42` (`_do_set_time_range`)
- Modify: `tests/test_time_range_bar.py:23-26`
- Test: `tests/test_time_presets.py`

**Interfaces:**
- Produces: `TIME_PRESETS` (id `sciqlop.time_presets`); `TimePreset(id: str, label: str, seconds: float, description: str = "")`; `duration_presets() -> list[TimePreset]` (sorted by `seconds`); `preset_seconds(text: str, default: float = 86400.0) -> float` (by id or label).

- [ ] **Step 1: Write the failing tests**

```python
"""Time-range presets are contributions to sciqlop.time_presets (Tier 3 spec §4.2)."""
import pytest

from SciQLop.core.extensions import owned_by
from SciQLop.core.time_presets import TIME_PRESETS, TimePreset, duration_presets, preset_seconds


@pytest.fixture
def three_days(qapp):
    with owned_by("tp_demo"):
        TIME_PRESETS.contribute(TimePreset("3d", "3d", 3 * 86400))
    yield
    TIME_PRESETS.remove_owner("tp_demo")


@pytest.fixture
def bar(qtbot):
    from SciQLop.components.plotting.ui.time_range_bar import TimeRangeBar
    w = TimeRangeBar()
    qtbot.addWidget(w)
    return w


def _items(bar):
    return [bar._duration_combo.itemText(i) for i in range(bar._duration_combo.count())]


def test_the_core_presets_merge_the_bar_and_the_palette():
    assert [p.id for p in duration_presets()] == ["1m", "1h", "12h", "1d", "7d", "1M"]
    assert preset_seconds("7d") == 604800
    assert preset_seconds("no such preset") == 86400


def test_a_plugin_preset_shows_in_an_open_bar_sorted_by_length(bar, three_days):
    assert _items(bar) == ["1m", "1h", "12h", "1d", "3d", "7d", "1M"]


def test_an_open_bar_keeps_its_selection_when_presets_change(bar, qtbot):
    bar.duration_text = "1d"
    with qtbot.assertNotEmitted(bar.range_changed):
        with owned_by("tp_demo"):
            TIME_PRESETS.contribute(TimePreset("3d", "3d", 3 * 86400))
        TIME_PRESETS.remove_owner("tp_demo")
    assert bar.duration_text == "1d"
    assert "3d" not in _items(bar)


def test_panel_duration_7d_still_selects_a_week(bar):
    bar.duration_text = "7d"
    assert bar.time_range.stop() - bar.time_range.start() == pytest.approx(604800)


def test_the_palette_offers_every_preset(three_days):
    from SciQLop.components.command_palette.arg_types import TimeRangeArg
    completions = TimeRangeArg().completions({})
    assert [c.value for c in completions] == ["1m", "1h", "12h", "1d", "3d", "7d", "1M"]
    assert "Last hour" in [c.display for c in completions]
    assert "Last 3d" in [c.display for c in completions]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_time_presets.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'SciQLop.core.time_presets'`.

- [ ] **Step 3: Create `SciQLop/core/time_presets.py`**

```python
"""Time-range duration presets: the sciqlop.time_presets extension point (Tier 3 spec §4.2).

The time-range bar's duration combo, the command palette's time-range completions and its duration table all
read this point. Zoom limits are not presets: they stay in time_range_bar.ZOOM_LIMIT_PRESETS.
"""
from __future__ import annotations

from dataclasses import dataclass
from operator import attrgetter

from SciQLop.core.extensions import ExtensionPoint, declare, owned_by
from SciQLop.core.name_follower import CORE_OWNER


@dataclass(frozen=True)
class TimePreset:
    id: str  # what a user types in the palette, e.g. "1d"
    label: str  # what the bar shows
    seconds: float
    description: str = ""  # the palette's wording; "Last <label>" when empty


TIME_PRESETS = declare(ExtensionPoint("sciqlop.time_presets", TimePreset, what="time preset",
                                      doc="Time-range duration presets by id."))


def duration_presets() -> list[TimePreset]:
    return sorted(TIME_PRESETS.list(), key=attrgetter("seconds"))


def preset_seconds(text: str, default: float = 86400.0) -> float:
    preset = next((p for p in TIME_PRESETS.list() if text in (p.id, p.label)), None)
    return preset.seconds if preset is not None else default


_CORE = (("1m", 60, "Last minute"), ("1h", 3600, "Last hour"), ("12h", 43200, "Last 12 hours"),
         ("1d", 86400, "Last day"), ("7d", 604800, "Last week"), ("1M", 30 * 86400, "Last month"))

with owned_by(CORE_OWNER):
    for _id, _seconds, _description in _CORE:
        TIME_PRESETS.contribute(TimePreset(_id, _id, _seconds, _description))
```

- [ ] **Step 4: The bar reads and follows the point**

In `SciQLop/components/plotting/ui/time_range_bar.py`:
- Delete `DURATION_PRESETS` (keep `ZOOM_LIMIT_PRESETS`). Import
  `from SciQLop.core.time_presets import TIME_PRESETS, duration_presets, preset_seconds` and `import shiboken6`.
- `_make_duration_combo`:

```python
def _make_duration_combo(parent):
    w = QComboBox(parent)
    for preset in duration_presets():
        w.addItem(preset.label)
    w.setCurrentText("1d")
    fit_combo_to_content(w)
    return w
```

- `_closest_duration_index`:

```python
def _closest_duration_index(seconds):
    presets = duration_presets()
    return min(range(len(presets)), key=lambda i: abs(presets[i].seconds - seconds))
```

- `_duration_seconds`: `return preset_seconds(self._duration_combo.currentText())`.
- At the end of `TimeRangeBar.__init__`:

```python
        TIME_PRESETS.signals.added.connect(self._on_presets_changed)
        TIME_PRESETS.signals.removed.connect(self._on_presets_changed)
```

- New method on `TimeRangeBar`:

```python
    def _on_presets_changed(self, _preset) -> None:
        """Keep the shown duration across a plugin adding or withdrawing presets; nothing is emitted."""
        if not shiboken6.isValid(self):
            return
        seconds = self._duration_seconds
        self._suppressing = True
        try:
            self._duration_combo.clear()
            for preset in duration_presets():
                self._duration_combo.addItem(preset.label)
            self._duration_combo.setCurrentIndex(_closest_duration_index(seconds))
            fit_combo_to_content(self._duration_combo)
        finally:
            self._suppressing = False
```

Read `_on_user_changed` first: it must be the only `currentTextChanged` consumer, and it must ignore changes while
`self._suppressing` is true (it does today). Read `_duration_seconds` before `clear()`.

- [ ] **Step 5: The palette reads the point**

`SciQLop/components/command_palette/arg_types.py` `TimeRangeArg.completions`:

```python
    def completions(self, context: dict) -> list[Completion]:
        from SciQLop.core.time_presets import duration_presets
        return [Completion(value=p.id, display=p.description or f"Last {p.label}") for p in duration_presets()]
```

`SciQLop/components/command_palette/commands.py` `_do_set_time_range`:

```python
def _do_set_time_range(time_range: str = ""):
    from datetime import datetime, timedelta
    from SciQLop.core import TimeRange
    from SciQLop.core.time_presets import preset_seconds
    now = datetime.utcnow()
    tr = TimeRange((now - timedelta(seconds=preset_seconds(time_range))).timestamp(), now.timestamp())
    _get_win()._default_time_range = tr
```

- [ ] **Step 6: The bar test expects the merged list**

In `tests/test_time_range_bar.py::test_duration_presets_available`, the expected list becomes
`["1m", "1h", "12h", "1d", "7d", "1M"]`.

- [ ] **Step 7: Run the time tests**

Run: `uv run pytest tests/test_time_presets.py tests/test_time_range_bar.py tests/test_command_palette_arg_types.py $(ls tests/test_command_palette*.py) -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add SciQLop/core/time_presets.py tests/test_time_presets.py
git commit SciQLop/core/time_presets.py SciQLop/components/plotting/ui/time_range_bar.py SciQLop/components/command_palette/arg_types.py SciQLop/components/command_palette/commands.py tests/test_time_range_bar.py tests/test_time_presets.py -m "feat(plugins): time-range presets are contributions to sciqlop.time_presets; the bar and the palette share them"
```

---

### Task 3: `sciqlop.themes` and the palette loader

**Files:**
- Create: `SciQLop/components/theming/themes.py`
- Modify: `SciQLop/components/theming/palette.py:17-61`
- Modify: `SciQLop/components/theming/icons.py:227-229` (`get_current_style_icon`)
- Modify: `SciQLop/core/sciqlop_application.py:57-60,83-97`
- Test: `tests/test_themes_point.py`

**Interfaces:**
- Produces: `THEMES` (id `sciqlop.themes`); `Theme(id: str, label: str, palette: dict[str, str] | Path)` with `colors() -> dict[str, str]`; `DEFAULT_THEME = "space"`; `palette.active_theme_name() -> str`; `SciQLopApp.current_theme()` returns the active (resolved) theme.

- [ ] **Step 1: Write the failing tests**

```python
"""Themes are contributions to sciqlop.themes; the palette loader resolves through it (Tier 3 spec §4.3)."""
from pathlib import Path

import pytest

from SciQLop.components.theming import palette as palette_module
from SciQLop.components.theming.themes import DEFAULT_THEME, THEMES, Theme
from SciQLop.core import sciqlop_application
from SciQLop.core.extensions import owned_by

_MIDNIGHT = {"Window": "#101020", "Base": "#000010", "Text": "#e0e0ff"}


@pytest.fixture
def restore_theme(qapp):
    original = qapp.current_theme()
    yield
    THEMES.remove_owner("th_demo")
    qapp.apply_theme(original)


def _contribute(theme_id="th_demo.midnight", palette=None):
    with owned_by("th_demo"):
        THEMES.contribute(Theme(theme_id, "Midnight", palette if palette is not None else dict(_MIDNIGHT)))


def test_the_core_themes_are_the_palette_files():
    files = {p.stem for p in Path(palette_module.palettes_path).glob("*.yaml")}
    assert set(THEMES.keys()) >= files
    assert THEMES.owner_of("space") == "sciqlop"


def test_a_theme_from_a_yaml_file_loads(tmp_path):
    path = tmp_path / "sand.yaml"
    path.write_text("Window: '#f0e0c0'\nText: '#202020'\n")
    assert Theme("th_demo.sand", "Sand", path).colors()["Window"] == "#f0e0c0"


@pytest.mark.parametrize("content", ["- a\n- b\n", "key: [unclosed\n"])
def test_a_yaml_that_is_not_a_mapping_is_refused_when_built(tmp_path, content):
    path = tmp_path / "bad.yaml"
    path.write_text(content)
    with pytest.raises(ValueError, match="th_demo.bad"):
        Theme("th_demo.bad", "Bad", path)


def test_a_missing_file_is_refused_when_built(tmp_path):
    with pytest.raises(ValueError, match="th_demo.gone"):
        Theme("th_demo.gone", "Gone", tmp_path / "gone.yaml")


def test_a_plugin_theme_applies(qapp, restore_theme):
    _contribute()
    qapp.apply_theme("th_demo.midnight")
    assert qapp.current_theme() == "th_demo.midnight"
    assert palette_module.current_palette()["window"] == "#101020"


def test_an_unknown_theme_starts_on_the_default(qapp, restore_theme):
    qapp.apply_theme("th_demo.never_installed")
    assert qapp.current_theme() == DEFAULT_THEME
    assert palette_module.active_theme_name() == DEFAULT_THEME


def test_the_saved_theme_applies_when_its_plugin_contributes_it(qapp, restore_theme, monkeypatch):
    monkeypatch.setattr(sciqlop_application, "_saved_theme", lambda: "th_demo.midnight")
    qapp.apply_theme("th_demo.midnight")
    assert qapp.current_theme() == DEFAULT_THEME
    _contribute()
    assert qapp.current_theme() == "th_demo.midnight"


def test_withdrawing_the_active_theme_falls_back_and_keeps_the_setting(qapp, restore_theme):
    from SciQLop.components.theming.settings import SciQLopStyle
    saved = SciQLopStyle().color_palette
    _contribute()
    qapp.apply_theme("th_demo.midnight")
    THEMES.remove_owner("th_demo")
    assert qapp.current_theme() == DEFAULT_THEME
    assert SciQLopStyle().color_palette == saved
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_themes_point.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'SciQLop.components.theming.themes'`.

- [ ] **Step 3: Create `SciQLop/components/theming/themes.py`**

```python
"""Themes: the sciqlop.themes extension point (Tier 3 spec §4.3). The core themes are the palette files in
SciQLop/resources/palettes, contributed when this module is imported."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Union

import yaml

import SciQLop
from SciQLop.core.extensions import ExtensionPoint, declare, owned_by
from SciQLop.core.name_follower import CORE_OWNER

DEFAULT_THEME = "space"
CORE_THEMES = ("light", "dark", "neutral", "space", "github_light", "nord_light", "catppuccin_latte",
               "high_contrast_light")
palettes_path = os.path.join(SciQLop.sciqlop_root, "resources", "palettes")


@dataclass(frozen=True)
class Theme:
    id: str
    label: str
    palette: Union[dict, Path]  # role -> colour, or a .yaml file holding that mapping

    def __post_init__(self):
        self.colors()

    def colors(self) -> dict[str, str]:
        """A fresh copy of the role -> colour mapping; ValueError when the file is missing or not a mapping."""
        if isinstance(self.palette, dict):
            return dict(self.palette)
        try:
            colors = yaml.safe_load(Path(self.palette).read_text())
        except (OSError, yaml.YAMLError) as e:
            raise ValueError(f"theme {self.id}: cannot read {self.palette}: {e}") from e
        if not isinstance(colors, dict):
            raise ValueError(f"theme {self.id}: {self.palette} is not a mapping of roles to colours")
        return colors


THEMES = declare(ExtensionPoint("sciqlop.themes", Theme, what="theme", doc="Colour themes by id."))

with owned_by(CORE_OWNER):
    for _name in CORE_THEMES:
        THEMES.contribute(Theme(_name, _name, Path(palettes_path) / f"{_name}.yaml"))
```

Check `resources/palettes` holds exactly these 8 names first (`ls SciQLop/resources/palettes`); the order of
`CORE_THEMES` is today's `_VALID_THEMES` order, which `list_themes()` returns.

- [ ] **Step 4: The palette loader resolves through the point**

In `SciQLop/components/theming/palette.py`: import `from .themes import DEFAULT_THEME, THEMES, palettes_path` and
delete the local `palettes_path` definition (keep the name importable from `palette`: the test above reads
`palette_module.palettes_path`). Replace `_load_palette`, the `SCIQLOP_PALETTE` binding and `setup_palette`:

```python
_active_theme = DEFAULT_THEME


def _resolve(name: str) -> str:
    return name if name in THEMES else DEFAULT_THEME


def _load_palette(name: str) -> dict[str, str]:
    try:
        return _make_palette_case_insensitive(THEMES.get(_resolve(name)).colors())
    except ValueError as e:  # a core palette file broken on disk
        log.error(e)
        return _make_palette_case_insensitive(THEMES.get(DEFAULT_THEME).colors())


def active_theme_name() -> str:
    """The theme actually shown: the requested one, or the default while it is not contributed."""
    return _active_theme


SCIQLOP_PALETTE = _load_palette(SciQLopStyle().color_palette)


def setup_palette(palette_name: str) -> QtGui.QPalette:
    """Load the named palette (the default when it is not contributed), rebuild icons, and return a QPalette."""
    global SCIQLOP_PALETTE, _active_theme
    _active_theme = _resolve(palette_name)
    SCIQLOP_PALETTE = _load_palette(_active_theme)
    qpalette = build_palette(SCIQLOP_PALETTE)
    build_icon_set_for_palette(_active_theme, qpalette.base().color())
    return qpalette
```

`yaml` may become unused in `palette.py`; drop the import if flake8 says so.

- [ ] **Step 5: Icons follow the active theme**

In `SciQLop/components/theming/icons.py`, `get_current_style_icon`:

```python
def get_current_style_icon(name: str) -> QIcon:
    from .palette import active_theme_name
    return QIcon(str(per_palette_icon_dir(palette_name=active_theme_name()) / f"{name}.png"))
```

- [ ] **Step 6: The app applies the resolved theme and follows the point**

In `SciQLop/core/sciqlop_application.py`, add a module-level function (tests patch it):

```python
def _saved_theme() -> str:
    return SciQLopStyle().color_palette
```

In `SciQLopApp.__init__`, after `self.load_stylesheet()` (the first one), connect the point:

```python
        from SciQLop.components.theming.themes import THEMES
        THEMES.signals.added.connect(self._on_theme_added)
        THEMES.signals.removed.connect(self._on_theme_removed)
```

and keep `self._current_palette_name` the resolved name: replace the two lines

```python
        self._current_palette_name = SciQLopStyle().color_palette
        self._current_palette = setup_palette(palette_name=self._current_palette_name)
```

with

```python
        self._current_palette = setup_palette(palette_name=_saved_theme())
        self._current_palette_name = active_theme_name()
```

importing `active_theme_name` from `SciQLop.components.theming.palette`. In `apply_theme`, set the name after
`setup_palette`:

```python
    def apply_theme(self, palette_name: str):
        self._current_palette = setup_palette(palette_name=palette_name)
        self._current_palette_name = active_theme_name()
        self.setPalette(self._current_palette)
        self.load_stylesheet()
        self._update_plot_themes()
        self.theme_changed.emit(self._current_palette_name)

    def _on_theme_added(self, theme) -> None:
        """A plugin theme saved as the user's choice applies once its plugin contributes it."""
        if theme.id == _saved_theme() and theme.id != self._current_palette_name:
            self.apply_theme(theme.id)

    def _on_theme_removed(self, theme) -> None:
        """The setting is kept: the theme comes back with its plugin on the next start."""
        if theme.id == self._current_palette_name:
            self.apply_theme(DEFAULT_THEME)
```

importing `DEFAULT_THEME` from `SciQLop.components.theming.themes`.

- [ ] **Step 7: Run the theme tests**

Run: `uv run pytest tests/test_themes_point.py tests/test_theme_api.py $(ls tests/test_*them*.py tests/test_*palette*.py 2>/dev/null) -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add SciQLop/components/theming/themes.py tests/test_themes_point.py
git commit SciQLop/components/theming/themes.py SciQLop/components/theming/palette.py SciQLop/components/theming/icons.py SciQLop/core/sciqlop_application.py tests/test_themes_point.py -m "feat(plugins): themes are contributions to sciqlop.themes; a plugin theme applies when contributed and falls back on withdrawal"
```

---

### Task 4: Settings combo and `user_api.themes` follow the point

**Files:**
- Modify: `SciQLop/components/settings/ui/settings_delegates/__init__.py:244-280,665-678`
- Modify: `SciQLop/components/theming/settings.py:8-23`
- Modify: `SciQLop/user_api/themes/__init__.py` (whole module)
- Test: `tests/test_themes_point.py` (append)

**Interfaces:**
- Consumes: `THEMES`, `Theme`, `DEFAULT_THEME` (Task 3).
- Produces: `PointChoicesDelegate(point_id: str)`; `json_schema_extra={"widget": "combo", "choices_from": "<extension point id>"}` is honoured by `get_delegate_for_field`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_themes_point.py`:

```python
def test_the_settings_combo_lists_themes_contributed_after_it_was_built(qapp, restore_theme):
    from SciQLop.components.settings.ui.settings_delegates import get_delegate_for_field
    from SciQLop.components.theming.settings import SciQLopStyle
    combo = get_delegate_for_field("color_palette", SciQLopStyle.model_fields["color_palette"])
    try:
        values = lambda: [combo._combo.itemData(i) for i in range(combo._combo.count())]
        labels = lambda: [combo._combo.itemText(i) for i in range(combo._combo.count())]
        assert "space" in values()
        _contribute()
        assert "th_demo.midnight" in values() and "Midnight" in labels()
        combo.set_value("th_demo.midnight")
        qapp.apply_theme("th_demo.midnight")
        THEMES.remove_owner("th_demo")
        assert "th_demo.midnight" not in values()
        assert qapp.current_theme() == DEFAULT_THEME
    finally:
        combo.deleteLater()


def test_user_api_lists_and_applies_plugin_themes(qapp, restore_theme):
    from SciQLop.user_api import themes
    _contribute()
    assert "th_demo.midnight" in themes.list_themes()
    themes.apply_theme("th_demo.midnight")
    assert themes.current_theme() == "th_demo.midnight"
    with pytest.raises(ValueError, match="unknown theme"):
        themes.apply_theme("th_demo.never_installed")
```

- [ ] **Step 2: Run them to verify they fail**

Run: `uv run pytest tests/test_themes_point.py -q -k "settings_combo or user_api"`
Expected: FAIL (`th_demo.midnight` missing from the combo; `unknown theme` raised for the plugin theme).

- [ ] **Step 3: A combo fed by an extension point**

In `SciQLop/components/settings/ui/settings_delegates/__init__.py`, after `ComboDelegate`, add (import `shiboken6`
at the top if it is not imported yet):

```python
class PointChoicesDelegate(ComboDelegate):
    """A combo listing an extension point's keys, kept current as plugins contribute and withdraw: settings
    pages are built at startup, before plugins activate."""

    def __init__(self, point_id: str, parent=None):
        from SciQLop.core import extensions
        super().__init__(parent=parent)
        self._point = extensions.get(point_id)
        self._repopulate()
        self._point.signals.added.connect(self._on_point_changed)
        self._point.signals.removed.connect(self._on_point_changed)

    def _repopulate(self) -> None:
        self.populate((getattr(item, "label", key), key)
                      for key, item in ((k, self._point.find(k)) for k in self._point.keys()))
        fit_combo_to_content(self._combo)

    def _on_point_changed(self, _item) -> None:
        if not shiboken6.isValid(self):
            return
        current = self.get_value()
        self._repopulate()
        self.set_value(current)
```

In `get_delegate_for_field`, inside `if widget:` and before the `choices` lookup:

```python
        choices_from = extra.get("choices_from")
        if choices_from:
            return PointChoicesDelegate(choices_from)
```

- [ ] **Step 4: The theme setting reads the point**

In `SciQLop/components/theming/settings.py`, replace the `json_schema_extra` of `color_palette` with
`json_schema_extra={"widget": "combo", "choices_from": "sciqlop.themes"}` (delete the literal list).

- [ ] **Step 5: `user_api.themes` reads the point**

Replace the top of `SciQLop/user_api/themes/__init__.py` (the `Literal` import, `PaletteName` and `_VALID_THEMES`)
and the bodies of `apply_theme` and `list_themes`; keep the docstrings' examples:

```python
PaletteName = str  # a theme id: the core ones (see list_themes()) or one a plugin contributed


def apply_theme(name: PaletteName) -> None:
    """Switch the running SciQLop application to the named palette.

    Examples
    --------
    >>> apply_theme("dark")
    """
    from SciQLop.components.theming.themes import THEMES
    if name not in THEMES:
        raise ValueError(f"unknown theme {name!r}; expected one of: {list_themes()}")
    from SciQLop.core.sciqlop_application import sciqlop_app

    sciqlop_app().apply_theme(name)
```

```python
def list_themes() -> list[PaletteName]:
    """Return the list of available palette names.

    Examples
    --------
    >>> list_themes()
    ['light', 'dark', 'neutral', 'space', 'github_light', 'nord_light',
     'catppuccin_latte', 'high_contrast_light']
    """
    from SciQLop.components.theming.themes import THEMES
    return THEMES.keys()
```

Keep `current_theme()` and any `@on_main_thread` decorators the module already has. Then update the global memory
reference `/home/jeandet/.claude/memory/sciqlop-user-api.md`: `PaletteName` is `str`, and `list_themes()` includes
plugin themes.

- [ ] **Step 6: Run the theme and settings tests**

Run: `uv run pytest tests/test_themes_point.py tests/test_theme_api.py tests/test_user_api_thread_classification.py $(ls tests/test_settings*.py) -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git commit SciQLop/components/settings/ui/settings_delegates/__init__.py SciQLop/components/theming/settings.py SciQLop/user_api/themes/__init__.py tests/test_themes_point.py -m "feat(plugins): the theme setting and user_api.themes list the themes contributed to sciqlop.themes"
```

---

### Task 5: Declared before plugins, interop proof, docs

**Files:**
- Modify: `SciQLop/components/extension_points.py:7-45`
- Modify: `tests/test_plugin_interop.py` (`_OWNERS` and a new test)
- Modify: `SciQLop/components/agents/skills/sciqlop-plugin-design/references/plugin-contract.md` (EP table)
- Modify: `SciQLop/components/agents/skills/sciqlop-plugin-design/references/ui-and-settings.md`
- Modify: `docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md` (§4.3 Tier 3 rows)
- Modify: `CHANGELOG.md` (Unreleased → Plugins)

**Interfaces:**
- Consumes: `TEMPLATE_FORMATS`/`TemplateFormat` (Task 1), `TIME_PRESETS`/`TimePreset` (Task 2), `THEMES`/`Theme` (Task 3).

- [ ] **Step 1: Write the interop test**

In `tests/test_plugin_interop.py`, add `"tier3b_maker"` to `_OWNERS`, then append:

```python
_TIER3B_MAKER = """
    import json
    from SciQLop.components.plotting.template_formats import TemplateFormat
    from SciQLop.components.theming.themes import Theme
    from SciQLop.core.time_presets import TimePreset

    def activate(ctx):
        ctx.contribute("sciqlop.template_formats", TemplateFormat("tier3b_maker.tpl", "Demo", (".t3b",),
                                                                  loads=json.loads, dumps=json.dumps))
        ctx.contribute("sciqlop.time_presets", TimePreset("tier3b_maker.3d", "3d", 3 * 86400))
        ctx.contribute("sciqlop.themes", Theme("tier3b_maker.dusk", "Dusk", {"Window": "#303040"}))
"""


def test_plugin_contributes_a_template_format_a_time_preset_and_a_theme(tmp_path, main_window, fresh):
    from SciQLop.components.plotting.template_formats import template_suffixes
    from SciQLop.components.theming.themes import THEMES
    from SciQLop.core.time_presets import duration_presets

    loader.activate_all([_plugin(tmp_path, "tier3b_maker", _TIER3B_MAKER)], main_window=main_window, ep_plugins={})
    assert context.STATES["tier3b_maker"].status == "active", context.STATES["tier3b_maker"].reason
    assert ".t3b" in template_suffixes()
    assert "tier3b_maker.3d" in [p.id for p in duration_presets()]
    assert THEMES.owner_of("tier3b_maker.dusk") == "tier3b_maker"

    loader._withdraw("tier3b_maker")
    assert ".t3b" not in template_suffixes()
    assert "tier3b_maker.3d" not in [p.id for p in duration_presets()]
    assert "tier3b_maker.dusk" not in THEMES.keys()
```

- [ ] **Step 2: Run it**

Run: `uv run pytest tests/test_plugin_interop.py -q -k tier3b`
Expected: PASS when the three modules happen to be imported already, `NotRegistered` otherwise; Step 3 makes it
independent of import order.

- [ ] **Step 3: Declare the three points before plugins activate**

In `SciQLop/components/extension_points.py` `prepare_extension_points`, after the Tier 3a lines, add:

```python
    import SciQLop.components.plotting.template_formats  # noqa: F401  declares sciqlop.template_formats
    import SciQLop.core.time_presets  # noqa: F401  declares sciqlop.time_presets
    import SciQLop.components.theming.themes  # noqa: F401  declares sciqlop.themes
```

- [ ] **Step 4: Document the points**

In `references/plugin-contract.md`, append to the extension-point table:

```markdown
| `sciqlop.template_formats` | `TemplateFormat(id, label, suffixes, loads, dumps)` | `id` |
| `sciqlop.time_presets` | `TimePreset(id, label, seconds, description="")` | `id` |
| `sciqlop.themes` | `Theme(id, label, palette)`; `palette` is a role → colour dict or a `.yaml` path | `id` |
```

In `references/ui-and-settings.md`, append to the section added by plan 3a ("Quickstart shortcuts, tours, search
domains, catalog providers"), renaming it "Quickstart, tours, search, catalogs, templates, presets, themes":

```markdown
- `ctx.contribute("sciqlop.template_formats", TemplateFormat(id, label, suffixes, loads, dumps))` lets panel templates
  be saved and read in your format: `loads(text) -> dict`, `dumps(dict) -> text`. "Save as template" still writes
  `.json`; files in your format are listed while your plugin is active.
- `ctx.contribute("sciqlop.time_presets", TimePreset(id, label, seconds, description))` adds a duration to every
  panel's time-range bar and to the palette's "Set time range". `description` is the palette wording ("Last 3 days").
- `ctx.contribute("sciqlop.themes", Theme(id, label, palette))` adds a theme to Settings → Appearance and to
  `user_api.themes`. `palette` maps Qt palette roles (`Window`, `Base`, `Text`, …) to colours, as the files in
  `SciQLop/resources/palettes` do. If your theme is the user's choice, it applies as soon as your plugin activates;
  when your plugin is withdrawn SciQLop shows `space` and keeps the user's choice.
```

In the parent spec §4.3, append to the Tier 3 rows' "Replaces" cells: `template_formats`, `time_presets` and
`themes` **implemented**: `docs/superpowers/plans/2026-10-16-tier3b-template-formats-time-presets-themes.md`.

In `CHANGELOG.md`, under `## Unreleased` → `### Plugins`, add:

```markdown
- Plugins can add quickstart shortcuts, guided tours, smart-search domains, catalog providers, panel template file formats, time-range presets and themes. Everything a plugin adds goes away when the plugin is disabled.
- The time-range bar offers "1M" (30 days), and the command palette's "Set time range" offers every duration the bar has.
```

- [ ] **Step 5: Run the interop tests and lint**

Run: `uv run pytest tests/test_plugin_interop.py tests/test_plugin_panel_interop.py -q`
Expected: PASS.
Run: `git ls-files '*.py' | grep -v '^docs/' | xargs uv run flake8 --select=E9,F63,F7,F82 --count`
Expected: `0`.

- [ ] **Step 6: Commit**

```bash
git commit SciQLop/components/extension_points.py tests/test_plugin_interop.py SciQLop/components/agents/skills/sciqlop-plugin-design/references/plugin-contract.md SciQLop/components/agents/skills/sciqlop-plugin-design/references/ui-and-settings.md docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md CHANGELOG.md -m "feat(plugins): Tier 3b points are declared before plugins activate; interop proof, docs and changelog"
```
