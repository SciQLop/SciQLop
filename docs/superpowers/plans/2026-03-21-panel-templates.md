# Panel Templates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Save and load plot panel layouts as JSON/YAML files, compatible with speasy_proxy preset format.

**Architecture:** Pydantic models define the template schema (superset of speasy_proxy format). Product traceability via Qt `setProperty` on graph objects enables bidirectional save/load. Three UI surfaces: Jupyter API, panel context menu, welcome page cards.

**Tech Stack:** Pydantic, pyyaml, PySide6, Jinja2 (existing), QWebChannel (existing)

**Spec:** `docs/superpowers/specs/2026-03-21-panel-templates-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `SciQLop/components/plotting/panel_template.py` | Pydantic models + file I/O + path resolution |
| Modify | `SciQLop/components/plotting/ui/time_sync_panel.py:74-98` | Store product path on graph objects via `setProperty` |
| Modify | `SciQLop/components/plotting/ui/time_sync_panel.py:164-175` | Add "Save as template…" to context menu |
| Modify | `SciQLop/user_api/plot/_panel.py` | Add `save_template()` method on `PlotPanel` |
| Create | `SciQLop/user_api/templates.py` | Public API: `load()`, `list_templates()` |
| Modify | `SciQLop/components/welcome/backend.py` | Add template listing/loading slots |
| Modify | `SciQLop/components/welcome/resources/welcome.html.j2` | Templates section with cards |
| Modify | `pyproject.toml` | Add `pyyaml` dependency |
| Create | `tests/test_panel_template.py` | Tests for models, I/O, path resolution |
| Create | `tests/test_panel_template_integration.py` | Tests for save/load with real panels |

---

### Task 1: Pydantic Models + Path Resolution

**Files:**
- Create: `SciQLop/components/plotting/panel_template.py`
- Create: `tests/test_panel_template.py`

- [ ] **Step 1: Write tests for Pydantic models and path resolution**

```python
# tests/test_panel_template.py
import json
import pytest
from pathlib import Path

from SciQLop.components.plotting.panel_template import (
    PanelTemplate, PlotModel, ProductModel, AxisModel,
    TimeRangeModel, IntervalModel, resolve_product_path,
)


def _minimal_template(**overrides):
    defaults = dict(
        name="test",
        time_range=TimeRangeModel(start="2025-01-15T00:00:00Z", stop="2025-01-16T00:00:00Z"),
        plots=[PlotModel(products=[ProductModel(path="amda/imf")])],
    )
    defaults.update(overrides)
    return PanelTemplate(**defaults)


class TestPydanticModels:
    def test_minimal_template_roundtrip(self):
        t = _minimal_template()
        data = json.loads(t.model_dump_json())
        t2 = PanelTemplate.model_validate(data)
        assert t2.name == "test"
        assert len(t2.plots) == 1
        assert t2.plots[0].products[0].path == "amda/imf"

    def test_speasy_proxy_format_is_valid(self):
        """A speasy_proxy preset JSON should parse as a valid PanelTemplate."""
        raw = {
            "name": "ACE IMF",
            "description": "ACE magnetic field",
            "version": 1,
            "time_range": {"start": "2025-01-15T00:00:00Z", "stop": "2025-01-16T00:00:00Z"},
            "plots": [
                {"products": [{"path": "amda/imf"}], "y_axis": {"log": False}}
            ],
        }
        t = PanelTemplate.model_validate(raw)
        assert t.name == "ACE IMF"
        assert t.plots[0].y_axis.log is False

    def test_defaults(self):
        t = _minimal_template()
        assert t.version == 1
        assert t.description == ""
        assert t.intervals == []
        assert t.plots[0].y_axis.log is False
        assert t.plots[0].log_z is False

    def test_intervals(self):
        t = _minimal_template(intervals=[
            IntervalModel(start="2025-01-15T06:00:00Z", stop="2025-01-15T12:00:00Z",
                          color="rgba(255, 120, 80, 0.12)", label="event1")
        ])
        assert len(t.intervals) == 1
        assert t.intervals[0].label == "event1"


class TestResolveProductPath:
    def test_double_slash_path(self):
        assert resolve_product_path("speasy//amda//b_gse") == ["speasy", "amda", "b_gse"]

    def test_single_slash_legacy(self):
        assert resolve_product_path("amda/imf") == ["speasy", "amda", "imf"]

    def test_no_slash(self):
        assert resolve_product_path("scalar_product") == ["speasy", "scalar_product"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_panel_template.py -v`
Expected: FAIL — module does not exist

- [ ] **Step 3: Implement Pydantic models and path resolution**

```python
# SciQLop/components/plotting/panel_template.py
from __future__ import annotations

from pydantic import BaseModel


class TimeRangeModel(BaseModel):
    start: str
    stop: str


class ProductModel(BaseModel):
    path: str
    label: str = ""


class AxisModel(BaseModel):
    log: bool = False
    range: tuple[float, float] | None = None


class PlotModel(BaseModel):
    products: list[ProductModel]
    y_axis: AxisModel = AxisModel()
    log_z: bool = False


class IntervalModel(BaseModel):
    start: str
    stop: str
    color: str = ""
    label: str = ""


class PanelTemplate(BaseModel):
    name: str
    description: str = ""
    version: int = 1
    time_range: TimeRangeModel
    plots: list[PlotModel]
    intervals: list[IntervalModel] = []


def resolve_product_path(path: str) -> list[str]:
    if '//' in path:
        return path.split('//')
    return ['speasy'] + path.split('/')
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_panel_template.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plotting/panel_template.py tests/test_panel_template.py
git commit -m "feat: add Pydantic models and path resolution for panel templates"
```

---

### Task 2: File I/O (JSON + YAML)

**Files:**
- Modify: `SciQLop/components/plotting/panel_template.py`
- Modify: `tests/test_panel_template.py`
- Modify: `pyproject.toml` (add `pyyaml`)

- [ ] **Step 1: Add pyyaml dependency and update lock file**

In `pyproject.toml`, add `"pyyaml"` to the `dependencies` list. Then run `uv lock` to update the lock file.

- [ ] **Step 2: Write tests for file I/O**

```python
# Append to tests/test_panel_template.py

class TestFileIO:
    def test_save_and_load_json(self, tmp_path):
        t = _minimal_template(name="json_test")
        path = str(tmp_path / "test.json")
        t.to_file(path)
        loaded = PanelTemplate.from_file(path)
        assert loaded.name == "json_test"
        assert loaded.plots[0].products[0].path == "amda/imf"

    def test_save_and_load_yaml(self, tmp_path):
        t = _minimal_template(name="yaml_test")
        path = str(tmp_path / "test.yaml")
        t.to_file(path)
        loaded = PanelTemplate.from_file(path)
        assert loaded.name == "yaml_test"

    def test_save_and_load_yml(self, tmp_path):
        t = _minimal_template(name="yml_test")
        path = str(tmp_path / "test.yml")
        t.to_file(path)
        loaded = PanelTemplate.from_file(path)
        assert loaded.name == "yml_test"

    def test_unknown_extension_raises(self, tmp_path):
        t = _minimal_template()
        with pytest.raises(ValueError, match="extension"):
            t.to_file(str(tmp_path / "test.txt"))

    def test_load_unknown_extension_raises(self, tmp_path):
        (tmp_path / "test.txt").write_text("{}")
        with pytest.raises(ValueError, match="extension"):
            PanelTemplate.from_file(str(tmp_path / "test.txt"))
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_panel_template.py::TestFileIO -v`
Expected: FAIL — `to_file` / `from_file` not defined

- [ ] **Step 4: Implement file I/O methods on PanelTemplate**

Add to `SciQLop/components/plotting/panel_template.py`:

```python
import json
from pathlib import Path

# On PanelTemplate class:

    @staticmethod
    def from_file(path: str) -> PanelTemplate:
        p = Path(path)
        text = p.read_text()
        if p.suffix == '.json':
            return PanelTemplate.model_validate_json(text)
        elif p.suffix in ('.yaml', '.yml'):
            import yaml
            return PanelTemplate.model_validate(yaml.safe_load(text))
        raise ValueError(f"Unsupported file extension: {p.suffix}")

    def to_file(self, path: str) -> None:
        p = Path(path)
        if p.suffix == '.json':
            p.write_text(self.model_dump_json(indent=2))
        elif p.suffix in ('.yaml', '.yml'):
            import yaml
            p.write_text(yaml.dump(self.model_dump(), default_flow_style=False, sort_keys=False))
        else:
            raise ValueError(f"Unsupported file extension: {p.suffix}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_panel_template.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock SciQLop/components/plotting/panel_template.py tests/test_panel_template.py
git commit -m "feat: add JSON/YAML file I/O for panel templates"
```

---

### Task 3: Template Storage Discovery

**Files:**
- Modify: `SciQLop/components/plotting/panel_template.py`
- Modify: `tests/test_panel_template.py`

- [ ] **Step 1: Write tests for template discovery**

```python
# Append to tests/test_panel_template.py
from SciQLop.components.plotting.panel_template import (
    templates_dir, list_templates, find_template,
)


class TestTemplateDiscovery:
    def test_list_templates_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr("SciQLop.components.plotting.panel_template.templates_dir", lambda: tmp_path)
        assert list_templates() == []

    def test_list_templates_finds_json_and_yaml(self, tmp_path, monkeypatch):
        monkeypatch.setattr("SciQLop.components.plotting.panel_template.templates_dir", lambda: tmp_path)
        _minimal_template(name="a").to_file(str(tmp_path / "a.json"))
        _minimal_template(name="b").to_file(str(tmp_path / "b.yaml"))
        names = [t.name for t in list_templates()]
        assert "a" in names
        assert "b" in names

    def test_find_template_by_name(self, tmp_path, monkeypatch):
        monkeypatch.setattr("SciQLop.components.plotting.panel_template.templates_dir", lambda: tmp_path)
        _minimal_template(name="target").to_file(str(tmp_path / "target.json"))
        t = find_template("target")
        assert t is not None
        assert t.name == "target"

    def test_find_template_json_priority(self, tmp_path, monkeypatch):
        """JSON takes priority when both .json and .yaml exist with same stem."""
        monkeypatch.setattr("SciQLop.components.plotting.panel_template.templates_dir", lambda: tmp_path)
        _minimal_template(name="json_version").to_file(str(tmp_path / "dup.json"))
        _minimal_template(name="yaml_version").to_file(str(tmp_path / "dup.yaml"))
        t = find_template("dup")
        assert t.name == "json_version"

    def test_find_template_not_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr("SciQLop.components.plotting.panel_template.templates_dir", lambda: tmp_path)
        assert find_template("nonexistent") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_panel_template.py::TestTemplateDiscovery -v`
Expected: FAIL — functions not defined

- [ ] **Step 3: Implement discovery functions**

Add to `SciQLop/components/plotting/panel_template.py`:

```python
_TEMPLATE_EXTENSIONS = ('.json', '.yaml', '.yml')


def templates_dir() -> Path:
    d = Path.home() / ".local" / "share" / "sciqlop" / "templates"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_templates() -> list[PanelTemplate]:
    d = templates_dir()
    seen_stems: set[str] = set()
    results: list[PanelTemplate] = []
    # JSON first for priority
    for ext in _TEMPLATE_EXTENSIONS:
        for f in sorted(d.glob(f"*{ext}")):
            if f.stem not in seen_stems:
                seen_stems.add(f.stem)
                try:
                    results.append(PanelTemplate.from_file(str(f)))
                except Exception:
                    pass
    return results


def find_template(name: str) -> PanelTemplate | None:
    d = templates_dir()
    for ext in _TEMPLATE_EXTENSIONS:
        p = d / f"{name}{ext}"
        if p.exists():
            return PanelTemplate.from_file(str(p))
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_panel_template.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plotting/panel_template.py tests/test_panel_template.py
git commit -m "feat: add template storage discovery (list, find)"
```

---

### Task 4: Product Traceability (setProperty on graph objects)

**Files:**
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py:74-98`

- [ ] **Step 1: Write test for product traceability**

Note: This requires a running Qt app and real panel, so it goes in the integration test file. The `main_window` fixture comes from `tests/fixtures.py` (module-scoped, auto-discovered by pytest via conftest).

```python
# tests/test_panel_template_integration.py
import pytest
from tests.fixtures import main_window, sciqlop_resources, qapp_cls  # noqa: F401
from SciQLop.components.plotting.panel_template import PanelTemplate, TimeRangeModel, PlotModel, ProductModel


@pytest.fixture
def panel(main_window):
    return main_window.new_plot_panel()


class TestProductTraceability:
    def test_plot_product_sets_property(self, panel, main_window):
        """After plotting a product, the graph object should have sqp_product_path."""
        from SciQLop.components.plotting.ui.time_sync_panel import plot_product
        r = plot_product(panel, ["speasy", "amda", "imf"])
        if r is None:
            pytest.skip("Product not available — speasy provider not loaded")
        graph = r[1] if hasattr(r, '__iter__') else r
        assert graph.property("sqp_product_path") == "speasy//amda//imf"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_panel_template_integration.py::TestProductTraceability -v`
Expected: FAIL — property not set (returns empty/None)

- [ ] **Step 3: Modify `plot_product` to store product path on graph objects**

In `SciQLop/components/plotting/ui/time_sync_panel.py`, modify `plot_product()` (lines 74-98). After each `p.plot()` call that succeeds, set the property on the graph object:

```python
def plot_product(p, product, **kwargs):
    if isinstance(product, list):
        node = ProductsModel.node(product)
        if node is not None:
            provider = providers.get(node.provider())
            log.debug(f"Provider: {provider}")
            if provider is not None:
                product_path_str = "//".join(product)
                log.debug(f"Parameter type: {node.parameter_type()}")
                if node.parameter_type() in (ParameterType.Scalar, ParameterType.Vector, ParameterType.Multicomponents):
                    callback = _plot_product_callback(provider, node)
                    labels = listify(provider.labels(node))
                    log.debug(f"Building plot for {node.name()} with labels: {labels}, kwargs: {kwargs}")
                    r = p.plot(callback, labels=labels, **kwargs)
                    if hasattr(r, '__iter__'):
                        r[1].set_name(node.name())
                        r[1].setProperty("sqp_product_path", product_path_str)
                    else:
                        r.set_name(node.name())
                        r.setProperty("sqp_product_path", product_path_str)
                    return r
                elif node.parameter_type() == ParameterType.Spectrogram:
                    callback = _specgram_callback(provider, node)
                    log.debug(f"Building spectrogram plot for {node.name()} with kwargs: {kwargs}")
                    r = p.plot(callback, name=node.name(), graph_type=GraphType.ColorMap, y_log_scale=True,
                               z_log_scale=True, **kwargs)
                    if hasattr(r, '__iter__'):
                        r[1].setProperty("sqp_product_path", product_path_str)
                    else:
                        r.setProperty("sqp_product_path", product_path_str)
                    return r
    log.debug(f"Product not found: {product}")
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_panel_template_integration.py::TestProductTraceability -v`
Expected: PASS (or skip if speasy provider not loaded)

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plotting/ui/time_sync_panel.py tests/test_panel_template_integration.py
git commit -m "feat: store product path on graph objects for template traceability"
```

---

### Task 5: `from_panel` and `create_panel`

**Files:**
- Modify: `SciQLop/components/plotting/panel_template.py`
- Modify: `tests/test_panel_template.py`

- [ ] **Step 1: Write tests for `from_panel` and `create_panel`**

These need Qt but not necessarily a full speasy provider. We test the pure logic separately and integration with a fixture.

```python
# Append to tests/test_panel_template.py

class TestFromPanelCreatePanel:
    def test_from_panel_empty(self, qtbot):
        """An empty panel produces a template with empty plots list."""
        from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
        from SciQLop.core import TimeRange
        panel = TimeSyncPanel("test_panel", time_range=TimeRange(1737000000.0, 1737086400.0))
        qtbot.addWidget(panel)
        t = PanelTemplate.from_panel(panel)
        assert t.name == "test_panel"
        assert t.plots == []
        assert t.time_range.start is not None

    def test_create_panel_sets_time_range(self, qtbot):
        """create_panel should produce a panel with the template's time range."""
        from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
        from SciQLop.core import TimeRange
        t = _minimal_template(name="create_test")
        # create_panel needs a factory; we test the lower-level apply() instead
        panel = TimeSyncPanel("target", time_range=TimeRange(0.0, 1.0))
        qtbot.addWidget(panel)
        t.apply(panel)
        tr = panel.time_range
        assert tr.start() > 1e9  # should be ~2025 epoch
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_panel_template.py::TestFromPanelCreatePanel -v`
Expected: FAIL — `from_panel` / `apply` not defined

- [ ] **Step 3: Implement `from_panel`, `create_panel`, and `apply`**

Add to `SciQLop/components/plotting/panel_template.py`. Add a module-level logger (`log = getLogger(__name__)`) and the `datetime` import at the top. Then add these methods to `PanelTemplate`:

```python
from datetime import datetime, timezone
from SciQLop.components.sciqlop_logging import getLogger
log = getLogger(__name__)

    @staticmethod
    def from_panel(panel) -> PanelTemplate:
        tr = panel.time_range
        time_range = TimeRangeModel(
            start=datetime.fromtimestamp(tr.start(), tz=timezone.utc).isoformat(),
            stop=datetime.fromtimestamp(tr.stop(), tz=timezone.utc).isoformat(),
        )
        plots = []
        for plot in panel.plots():
            products = []
            for graph in plot.plottables():
                path = graph.property("sqp_product_path")
                if path:
                    products.append(ProductModel(path=path, label=graph.name))
                else:
                    log.warning(f"Skipping graph without sqp_product_path: {graph.name}")
            if products:
                plots.append(PlotModel(products=products))
        return PanelTemplate(
            name=panel.windowTitle() or panel.objectName(),
            time_range=time_range,
            plots=plots,
        )

    def create_panel(self, main_window):
        panel = main_window.new_plot_panel()
        self.apply(panel._impl if hasattr(panel, '_impl') else panel)
        return panel

    def apply(self, panel) -> None:
        from SciQLop.components.plotting.ui.time_sync_panel import plot_product
        from SciQLop.core import TimeRange as TR
        panel.clear()
        start = datetime.fromisoformat(self.time_range.start).timestamp()
        stop = datetime.fromisoformat(self.time_range.stop).timestamp()
        panel.set_time_axis_range(TR(start, stop))
        for plot_model in self.plots:
            for product in plot_model.products:
                resolved = resolve_product_path(product.path)
                r = plot_product(panel, resolved)
                if r is None:
                    log.warning(f"Product not found, skipping: {product.path}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_panel_template.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plotting/panel_template.py tests/test_panel_template.py
git commit -m "feat: add from_panel, create_panel, and apply methods"
```

---

### Task 6: User API (`save_template`, `templates` module)

**Files:**
- Modify: `SciQLop/user_api/plot/_panel.py`
- Create: `SciQLop/user_api/templates.py`

- [ ] **Step 1: Write tests for user API**

```python
# Append to tests/test_panel_template.py
from SciQLop.user_api.templates import load, list_templates as api_list_templates


class TestUserAPI:
    def test_list_templates_api(self, tmp_path, monkeypatch):
        monkeypatch.setattr("SciQLop.components.plotting.panel_template.templates_dir", lambda: tmp_path)
        _minimal_template(name="api_test").to_file(str(tmp_path / "api_test.json"))
        results = api_list_templates()
        assert any(t.name == "api_test" for t in results)

    def test_load_by_name(self, tmp_path, monkeypatch):
        monkeypatch.setattr("SciQLop.components.plotting.panel_template.templates_dir", lambda: tmp_path)
        _minimal_template(name="by_name").to_file(str(tmp_path / "by_name.yaml"))
        t = load("by_name")
        assert t.name == "by_name"

    def test_load_by_path(self, tmp_path):
        path = str(tmp_path / "direct.json")
        _minimal_template(name="direct").to_file(path)
        t = load(path)
        assert t.name == "direct"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_panel_template.py::TestUserAPI -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement `SciQLop/user_api/templates.py`**

```python
# SciQLop/user_api/templates.py
"""Public API for panel templates."""
from pathlib import Path

from SciQLop.components.plotting.panel_template import (
    PanelTemplate,
    list_templates as _list_templates,
    find_template as _find_template,
)


def load(name_or_path: str) -> PanelTemplate | None:
    p = Path(name_or_path)
    if p.suffix in ('.json', '.yaml', '.yml') and p.exists():
        return PanelTemplate.from_file(str(p))
    return _find_template(name_or_path)


def list_templates() -> list[PanelTemplate]:
    return _list_templates()
```

- [ ] **Step 4: Add `save_template` to `PlotPanel`**

In `SciQLop/user_api/plot/_panel.py`, add this method to the `PlotPanel` class:

```python
    @on_main_thread
    def save_template(self, path: str) -> None:
        from SciQLop.components.plotting.panel_template import PanelTemplate, templates_dir
        t = PanelTemplate.from_panel(self._get_impl_or_raise())
        if '/' not in path and '\\' not in path:
            # Bare filename → save to default templates dir
            if not any(path.endswith(ext) for ext in ('.json', '.yaml', '.yml')):
                path = path + '.json'
            path = str(templates_dir() / path)
        t.to_file(path)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_panel_template.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add SciQLop/user_api/templates.py SciQLop/user_api/plot/_panel.py tests/test_panel_template.py
git commit -m "feat: add user API for panel templates (save_template, load, list)"
```

---

### Task 7: Panel Context Menu — "Save as template…"

**Files:**
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py:164-175`

- [ ] **Step 1: Extend the existing context menu**

In `TimeSyncPanel._show_catalog_menu()`, add a "Save as template…" action. Rename the method to `_show_context_menu` for clarity:

```python
    def _show_context_menu(self, global_pos):
        from PySide6.QtWidgets import QMenu
        menu = QMenu(self)
        self._catalog_manager.build_catalogs_menu(menu)
        menu.addSeparator()
        menu.addAction("Save as template…", self._save_as_template_dialog)
        menu.exec(global_pos)

    def _save_as_template_dialog(self):
        from PySide6.QtWidgets import QFileDialog
        from SciQLop.components.plotting.panel_template import PanelTemplate, templates_dir
        path, _ = QFileDialog.getSaveFileName(
            self, "Save panel template",
            str(templates_dir() / f"{self.windowTitle()}.json"),
            "JSON (*.json);;YAML (*.yaml *.yml)",
        )
        if path:
            PanelTemplate.from_panel(self).to_file(path)
```

Also update the `eventFilter` call from `_show_catalog_menu` to `_show_context_menu`.

- [ ] **Step 2: Commit**

```bash
git add SciQLop/components/plotting/ui/time_sync_panel.py
git commit -m "feat: add 'Save as template' to panel context menu"
```

---

### Task 8: Welcome Page Templates Section

**Files:**
- Modify: `SciQLop/components/welcome/backend.py`
- Modify: `SciQLop/components/welcome/resources/welcome.html.j2`

- [ ] **Step 1: Read current welcome page files to understand the pattern**

Read:
- `SciQLop/components/welcome/backend.py` — existing slots
- `SciQLop/components/welcome/resources/welcome.html.j2` — HTML structure
- `SciQLop/components/welcome/resources/welcome.js` — JS bridge calls

- [ ] **Step 2: Add template slots to WelcomeBackend**

In `SciQLop/components/welcome/backend.py`, add:

```python
    @Slot(result=str)
    def list_templates(self):
        import json
        from SciQLop.components.plotting.panel_template import list_templates
        return json.dumps([
            {"name": t.name, "description": t.description}
            for t in list_templates()
        ])

    @Slot(str)
    def load_template(self, name):
        from SciQLop.components.plotting.panel_template import find_template
        from SciQLop.user_api.gui import get_main_window
        t = find_template(name)
        if t:
            t.create_panel(get_main_window())

    @Slot()
    def import_template(self):
        from PySide6.QtWidgets import QFileDialog
        from SciQLop.components.plotting.panel_template import PanelTemplate, templates_dir
        import shutil
        path, _ = QFileDialog.getOpenFileName(
            None, "Import template",
            str(Path.home()),
            "Templates (*.json *.yaml *.yml)",
        )
        if path:
            dest = templates_dir() / Path(path).name
            shutil.copy2(path, dest)
```

- [ ] **Step 3: Add templates section to welcome HTML**

Add a "Templates" section to the Jinja2 template, following the existing card pattern. The section should:
- Call `backend.list_templates()` on load
- Render cards with name + description
- Click a card → `backend.load_template(name)`
- "Import…" card at the end → `backend.import_template()`

The exact HTML/JS follows whatever pattern the existing sections use (workspace cards, examples cards, etc.).

- [ ] **Step 4: Commit**

```bash
git add SciQLop/components/welcome/backend.py SciQLop/components/welcome/resources/welcome.html.j2
git commit -m "feat: add templates section to welcome page"
```

---

### Task 9: Final integration test

**Files:**
- Modify: `tests/test_panel_template_integration.py`

- [ ] **Step 1: Write integration test for full round-trip**

```python
# Append to tests/test_panel_template_integration.py

class TestFullRoundTrip:
    def test_save_and_load_template(self, tmp_path, qtbot):
        from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
        from SciQLop.core import TimeRange
        panel = TimeSyncPanel("roundtrip", time_range=TimeRange(1737000000.0, 1737086400.0))
        qtbot.addWidget(panel)
        t = PanelTemplate.from_panel(panel)
        path = str(tmp_path / "roundtrip.json")
        t.to_file(path)
        loaded = PanelTemplate.from_file(path)
        assert loaded.name == "roundtrip"
        assert loaded.time_range.start is not None
```

- [ ] **Step 2: Run all tests**

Run: `uv run pytest tests/test_panel_template.py tests/test_panel_template_integration.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_panel_template_integration.py
git commit -m "test: add full round-trip integration test for panel templates"
```
