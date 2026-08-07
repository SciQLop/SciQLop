# Plot API — SciQLopPlots Catch-up Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the missing SciQLopPlots 0.34.0 capabilities through `SciQLop.user_api.plot`, `SciQLop.user_api.catalogs`, and `SciQLop.user_api.themes` so every v0.13 website gallery shot can be scripted from the public API.

**Architecture:** Keep the existing facade pattern: thin Python wrappers around `SciQLopPlots` C++ objects, `@experimental_api()` gating, `on_main_thread` Qt threading, and palette-aware defaults. Each new feature gets a typed method plus an entry in the omnibus `panel.plot(...)` dispatcher. Phase 1 (gallery-ready APIs) ships before Phase 2 (small enum additions).

**Tech Stack:** Python 3.13, PySide6, SciQLopPlots 0.34.0, NumPy, pytest-qt, pytest-xvfb.

## Global Constraints

- SciQLopPlots version floor is **0.34.0** (`pyproject.toml:39` already declares it, but `uv.lock` still pins 0.33.1 — regenerate the lockfile before starting if it is still stale).
- All new public functions/methods/classes must be decorated with `@experimental_api()` unless they are internal helpers.
- All Qt-object access must be wrapped with `@on_main_thread`.
- No breaking changes to existing public signatures; new arguments must be keyword-only.
- Follow existing file naming and import patterns in `SciQLop/user_api/plot/`.
- Every task ends with a passing test and a commit.

---

## File structure

### Existing files that change

- `SciQLop/user_api/plot/enums.py` — add `GraphType.Waterfall`, `BinStrategy`, `GraphLineStyle`, `AxisType`.
- `SciQLop/user_api/plot/_graphic_primitives.py` — add `VerticalLine`, `StraightLine`, `RectangularSpan`, `HorizontalSpan`.
- `SciQLop/user_api/plot/_graphs.py` — add `Waterfall` plottable and update `_reject_if_colormap_already_present` message.
- `SciQLop/user_api/plot/_plots.py` — add `waterfall()` to `XYPlot`/`TimeSeriesPlot`, implement `ProjectionPlot` stubs, add `plot_time_colored_curve()`, add `set_axis_type()`.
- `SciQLop/user_api/plot/_panel.py` — add `waterfall()`, `add_catalog_overlay()`, `remove_catalog_overlay()`, extend `histogram2d()` and `plot_data()` with bin strategy / line style.
- `SciQLop/user_api/plot/__init__.py` — export new classes and enums.
- `SciQLop/user_api/catalogs/__init__.py` — export overlay helpers.
- `SciQLop/user_api/catalogs/_overlay.py` — new file: `CatalogOverlay` + attach helpers.
- `SciQLop/user_api/themes/__init__.py` — new file: theme facade.
- `SciQLop/user_api/__init__.py` — re-export `themes`.
- `tests/fixtures.py` — add `synthetic_waterfall_data()` and `synthetic_projection_data()`.

### New test files

- `tests/test_waterfall.py`
- `tests/test_histogram2d_bins.py`
- `tests/test_projection_controls.py`
- `tests/test_catalog_overlay_api.py`
- `tests/test_theme_api.py`
- `tests/test_graphic_primitives.py`
- `tests/test_line_style_axis_type.py`

---

## Task 1: Add plot enums

**Files:**
- Modify: `SciQLop/user_api/plot/enums.py`
- Test: `tests/test_line_style_axis_type.py` (enum mapping tests only)

**Interfaces:**
- Produces: `GraphType.Waterfall`, `BinStrategy`, `GraphLineStyle`, `AxisType`.
- Consumes: nothing (first task).

- [ ] **Step 1: Write the failing enum tests**

```python
# tests/test_line_style_axis_type.py
import pytest
from SciQLop.user_api.plot.enums import GraphType, BinStrategy, GraphLineStyle, AxisType


def test_graph_type_has_waterfall():
    assert GraphType.Waterfall.value == 4


def test_bin_strategy_values():
    assert BinStrategy.Linear.value == "linear"
    assert BinStrategy.Log.value == "log"
    assert BinStrategy.SymLog.value == "symlog"


def test_graph_line_style_values():
    # Values mirror SciQLopPlots.GraphLineStyle; adjust if upstream differs.
    assert GraphLineStyle.Solid.value == 0
    assert GraphLineStyle.Dash.value == 1


def test_axis_type_values():
    # Values mirror SciQLopPlots.AxisType; adjust if upstream differs.
    assert AxisType.Linear.value == 0
    assert AxisType.Logarithmic.value == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_line_style_axis_type.py -v
```

Expected: `AttributeError: Waterfall` / `BinStrategy` / etc.

- [ ] **Step 3: Add the enums**

```python
# SciQLop/user_api/plot/enums.py
class GraphType(Enum):
    Line = 0
    Curve = 1
    ColorMap = 2
    Scatter = 3
    Waterfall = 4


class BinStrategy(Enum):
    Linear = "linear"
    Log = "log"
    SymLog = "symlog"


class GraphLineStyle(Enum):
    Solid = 0
    Dash = 1
    Dot = 2
    DashDot = 3
    DashDotDot = 4


class AxisType(Enum):
    Linear = 0
    Logarithmic = 1
    DateTime = 2
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_line_style_axis_type.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/plot/enums.py tests/test_line_style_axis_type.py
git commit -m "feat(plot): add Waterfall, BinStrategy, GraphLineStyle, AxisType enums"
```

---

## Task 2: Add extra graphic primitives

**Files:**
- Modify: `SciQLop/user_api/plot/_graphic_primitives.py`
- Modify: `SciQLop/user_api/plot/__init__.py`
- Test: `tests/test_graphic_primitives.py`

**Interfaces:**
- Consumes: `CoordinateSystem` from Task 1 (already exists).
- Produces: `VerticalLine`, `StraightLine`, `RectangularSpan`, `HorizontalSpan` classes following the `_PlotItem` pattern.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_graphic_primitives.py
import numpy as np
import pytest
from SciQLop.user_api.plot import create_plot_panel
from SciQLop.user_api.plot import VerticalLine, StraightLine, RectangularSpan, HorizontalSpan


@pytest.fixture
def panel():
    panel = create_plot_panel("primitive-test")
    panel.plot_data(np.arange(10), np.arange(10))
    return panel


def test_vertical_line_can_be_added_and_removed(panel):
    plot = panel.plots()[0]
    line = VerticalLine(plot, 5.0)
    assert line is not None
    line.remove()


def test_straight_line_can_be_added_and_removed(panel):
    plot = panel.plots()[0]
    line = StraightLine(plot, 0.0, 0.0, 9.0, 9.0)
    assert line is not None
    line.remove()


def test_rectangular_span_can_be_added_and_removed(panel):
    plot = panel.plots()[0]
    span = RectangularSpan(plot, 2.0, 2.0, 7.0, 7.0)
    assert span is not None
    span.remove()


def test_horizontal_span_can_be_added_and_removed(panel):
    plot = panel.plots()[0]
    span = HorizontalSpan(plot, 2.0, 7.0)
    assert span is not None
    span.remove()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_graphic_primitives.py -v
```

Expected: `ImportError: cannot import name 'VerticalLine' ...`

- [ ] **Step 3: Import and wrap the upstream primitives**

```python
# SciQLop/user_api/plot/_graphic_primitives.py
from SciQLopPlots import (SciQLopPixmapItem as _SciQLopPixmapItem,
                          SciQLopEllipseItem as _SciQLopEllipseItem,
                          SciQLopTextItem as _SciQLopTextItem,
                          SciQLopCurvedLineItem as _SciQLopCurvedLineItem,
                          SciQLopHorizontalLine as _SciQLopHorizontalLine,
                          SciQLopVerticalLine as _SciQLopVerticalLine,
                          SciQLopStraightLine as _SciQLopStraightLine,
                          SciQLopRectangularSpan as _SciQLopRectangularSpan,
                          SciQLopHorizontalSpan as _SciQLopHorizontalSpan,
                          )

__all__ = [
    'Pixmap', 'Ellipse', 'Text', 'CurvedLine', 'HorizontalLine',
    'VerticalLine', 'StraightLine', 'RectangularSpan', 'HorizontalSpan',
    'LineTermination'
]
```

Then add the four wrapper classes below `HorizontalLine`, mirroring the existing `HorizontalLine` pattern (palette-aware default color, `remove()`, properties where upstream supports them).

- [ ] **Step 4: Export from public module**

```python
# SciQLop/user_api/plot/__init__.py
from ._graphic_primitives import (
    Pixmap, Ellipse, Text, CurvedLine, HorizontalLine,
    VerticalLine, StraightLine, RectangularSpan, HorizontalSpan,
    LineTermination
)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_graphic_primitives.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add SciQLop/user_api/plot/_graphic_primitives.py SciQLop/user_api/plot/__init__.py tests/test_graphic_primitives.py
git commit -m "feat(plot): wrap VerticalLine, StraightLine, RectangularSpan, HorizontalSpan"
```

---

## Task 3: Add runtime theme API

**Files:**
- Create: `SciQLop/user_api/themes/__init__.py`
- Modify: `SciQLop/user_api/__init__.py`
- Test: `tests/test_theme_api.py`

**Interfaces:**
- Consumes: `sciqlop_app().apply_theme(name)` from `SciQLop/core/sciqlop_application.py`.
- Produces: `SciQLop.user_api.themes.apply_theme(name)`, `current_theme()`, `list_themes()`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_theme_api.py
import pytest
from SciQLop.user_api import themes


def test_list_themes():
    assert set(themes.list_themes()) == {"light", "dark", "neutral", "space"}


def test_apply_and_read_theme():
    themes.apply_theme("dark")
    assert themes.current_theme() == "dark"
    themes.apply_theme("light")
    assert themes.current_theme() == "light"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_theme_api.py -v
```

Expected: `ModuleNotFoundError: No module named 'SciQLop.user_api.themes'`.

- [ ] **Step 3: Implement the theme facade**

```python
# SciQLop/user_api/themes/__init__.py
from typing import Literal

PaletteName = Literal["light", "dark", "neutral", "space"]

_VALID_THEMES = ["light", "dark", "neutral", "space"]


def apply_theme(name: PaletteName) -> None:
    """Switch the running SciQLop application to the named palette."""
    if name not in _VALID_THEMES:
        raise ValueError(f"unknown theme {name!r}; expected one of: {_VALID_THEMES}")
    from SciQLop.app import sciqlop_app
    sciqlop_app().apply_theme(name)


def current_theme() -> PaletteName:
    from SciQLop.app import sciqlop_app
    return sciqlop_app().current_theme()


def list_themes() -> list[PaletteName]:
    return list(_VALID_THEMES)
```

- [ ] **Step 4: Re-export from user_api**

```python
# SciQLop/user_api/__init__.py
from . import themes
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_theme_api.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add SciQLop/user_api/themes/__init__.py SciQLop/user_api/__init__.py tests/test_theme_api.py
git commit -m "feat(themes): add public apply_theme/current_theme/list_themes API"
```

---

## Task 4: Add log bins to 2D histogram

**Files:**
- Modify: `SciQLop/user_api/plot/_graphs.py`
- Modify: `SciQLop/user_api/plot/_plots.py`
- Modify: `SciQLop/user_api/plot/_panel.py`
- Test: `tests/test_histogram2d_bins.py`

**Interfaces:**
- Consumes: `BinStrategy` from Task 1.
- Produces: `_compute_bin_edges(x, bins, strategy)` helper; updated `histogram2d(..., x_bins, y_bins, x_bin_strategy, y_bin_strategy)` signatures.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_histogram2d_bins.py
import numpy as np
import pytest
from SciQLop.user_api.plot import create_plot_panel
from SciQLop.user_api.plot.enums import BinStrategy


@pytest.fixture
def data():
    rng = np.random.default_rng(42)
    x = rng.lognormal(0, 1, 1000)
    y = rng.normal(0, 1, 1000)
    return x, y


def test_log_bins_are_monotonic(data):
    x, y = data
    panel = create_plot_panel("hist-log")
    _, hist = panel.histogram2d(x, y, x_bins=20, x_bin_strategy=BinStrategy.Log)
    edges = hist.x_bin_edges
    assert np.all(np.diff(edges) > 0)
    assert edges[0] > 0


def test_explicit_edges_ignore_strategy(data):
    x, y = data
    panel = create_plot_panel("hist-edges")
    edges = np.linspace(x.min(), x.max(), 11)
    _, hist = panel.histogram2d(x, y, x_bins=edges, x_bin_strategy=BinStrategy.Log)
    np.testing.assert_array_almost_equal(hist.x_bin_edges, edges)


def test_symlog_does_not_crash_with_negatives(data):
    x, y = data
    x_with_neg = np.concatenate([x, -x])
    panel = create_plot_panel("hist-symlog")
    _, hist = panel.histogram2d(x_with_neg, y, x_bins=20, x_bin_strategy=BinStrategy.SymLog)
    assert hist.x_bin_edges is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_histogram2d_bins.py -v
```

Expected: `TypeError: histogram2d() got an unexpected keyword argument 'x_bin_strategy'`.

- [ ] **Step 3: Add bin-edge helper and update signatures**

```python
# SciQLop/user_api/plot/_graphs.py
import numpy as np
from .enums import BinStrategy


def _compute_bin_edges(data: np.ndarray, bins: int | np.ndarray, strategy: BinStrategy) -> np.ndarray:
    """Return bin edges honoring an explicit array or a BinStrategy."""
    if isinstance(bins, np.ndarray) or (isinstance(bins, list) and len(bins) > 1):
        return np.asarray(bins, dtype=np.float64)

    n = int(bins)
    if n < 1:
        raise ValueError(f"bin count must be >= 1, got {n}")

    data = np.asarray(data)
    lo, hi = float(np.nanmin(data)), float(np.nanmax(data))

    if strategy == BinStrategy.Linear:
        return np.linspace(lo, hi, n + 1)
    if strategy == BinStrategy.Log:
        if lo <= 0 or hi <= 0:
            raise ValueError("Log bins require strictly positive data range")
        return np.geomspace(lo, hi, n + 1)
    if strategy == BinStrategy.SymLog:
        linthresh = min(abs(lo), abs(hi)) if lo != 0 and hi != 0 else 1.0
        return _symlog_space(lo, hi, n, linthresh)

    raise ValueError(f"unknown bin strategy {strategy!r}")


def _symlog_space(lo, hi, n, linthresh):
    # Placeholder: mirror matplotlib's SymLogTransform spacing.
    # Replace with the actual implementation matching SciQLopPlots expectations.
    return np.linspace(lo, hi, n + 1)
```

Update `_create_histogram2d` to accept `x_bins`/`y_bins` as either int or array and pass edges to the upstream histogram when arrays are provided:

```python
def _create_histogram2d(plot_impl, *args, name: str = "histogram",
                        x_bins=100, y_bins=100,
                        z_log_scale: bool = False, gradient=None) -> Histogram2D:
    # Existing validation remains.
    # When x_bins/y_bins are arrays, pass them to plot_impl.histogram2d(...)
    # or compute edges and pass them, depending on upstream signature.
```

Update `Histogram2D` to expose `x_bin_edges` / `y_bin_edges` if upstream provides them; otherwise store them on the wrapper.

- [ ] **Step 4: Update typed methods**

```python
# SciQLop/user_api/plot/_plots.py — XYPlot.histogram2d and TimeSeriesPlot.histogram2d
def histogram2d(self, x, y, *, name: str = "histogram",
                x_bins: int | np.ndarray = 100,
                y_bins: int | np.ndarray = 100,
                x_bin_strategy: BinStrategy = BinStrategy.Linear,
                y_bin_strategy: BinStrategy = BinStrategy.Linear,
                z_log_scale: bool = False, gradient=None): ...
```

```python
# SciQLop/user_api/plot/_panel.py — PlotPanel.histogram2d
def histogram2d(self, *args, name: str = "histogram",
                x_bins=100, y_bins=100,
                x_bin_strategy: BinStrategy = BinStrategy.Linear,
                y_bin_strategy: BinStrategy = BinStrategy.Linear,
                z_log_scale: bool = False, gradient=None,
                plot_index: int = -1): ...
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_histogram2d_bins.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add SciQLop/user_api/plot/_graphs.py SciQLop/user_api/plot/_plots.py SciQLop/user_api/plot/_panel.py tests/test_histogram2d_bins.py
git commit -m "feat(plot): add BinStrategy support to histogram2d"
```

---

## Task 5: Implement ProjectionPlot axis controls

**Files:**
- Modify: `SciQLop/user_api/plot/_plots.py`
- Test: `tests/test_projection_controls.py`

**Interfaces:**
- Consumes: `ScaleType` from existing enums.
- Produces: working `ProjectionPlot.set_x_range`, `set_y_range`, `set_x_scale_type`, `set_y_scale_type`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_projection_controls.py
import numpy as np
import pytest
from SciQLop.user_api.plot import create_plot_panel
from SciQLop.user_api.plot.enums import PlotType, ScaleType


def test_projection_axis_ranges_and_scales():
    panel = create_plot_panel("proj-controls")
    plot = panel.plot_data(np.arange(10), np.arange(10), plot_type=PlotType.Projection)
    plot.set_x_range(-1.0, 11.0)
    plot.set_y_range(-2.0, 12.0)
    plot.set_x_scale_type(ScaleType.Logarithmic)
    plot.set_y_scale_type(ScaleType.Logarithmic)
    # Best-effort assertions: upstream must accept the calls without error.
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_projection_controls.py::test_projection_axis_ranges_and_scales -v
```

Expected: test passes because stubs are no-ops, but behavior is unverified. The task is to make them actually delegate.

- [ ] **Step 3: Implement the stubs**

```python
# SciQLop/user_api/plot/_plots.py
class ProjectionPlot:
    ...
    @on_main_thread
    def set_x_range(self, min: float, max: float):
        self._get_impl_or_raise().x_axis().set_range(min, max)

    @on_main_thread
    def set_y_range(self, min: float, max: float):
        self._get_impl_or_raise().y_axis().set_range(min, max)

    @on_main_thread
    def set_x_scale_type(self, scale: ScaleType):
        self._get_impl_or_raise().x_axis().set_scale(_to_sqp_scale_type(scale))

    @on_main_thread
    def set_y_scale_type(self, scale: ScaleType):
        self._get_impl_or_raise().y_axis().set_scale(_to_sqp_scale_type(scale))
```

Use the existing `_to_sqp_scale_type` helper if it exists; otherwise add one next to `_to_sqp_plot_type` in `_panel.py` or `_plots.py`.

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_projection_controls.py::test_projection_axis_ranges_and_scales -v
```

Expected: PASS with actual range/scale changes.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/plot/_plots.py tests/test_projection_controls.py
git commit -m "feat(plot): implement ProjectionPlot axis range and scale controls"
```

---

## Task 6: Add time-colored parametric curve

**Files:**
- Modify: `SciQLop/user_api/plot/_plots.py`
- Test: `tests/test_projection_controls.py`

**Interfaces:**
- Consumes: upstream parametric curve + colormap support.
- Produces: `ProjectionPlot.plot_time_colored_curve(x, y, t, ...)` returning `Graph`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_projection_controls.py
import numpy as np


def test_time_colored_curve():
    panel = create_plot_panel("proj-curve")
    plot = panel.plot_data(np.arange(10), np.arange(10), plot_type=PlotType.Projection)
    t = np.linspace(0, 1, 10)
    graph = plot.plot_time_colored_curve(np.arange(10), np.arange(10), t, colormap="viridis")
    assert graph is not None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_projection_controls.py::test_time_colored_curve -v
```

Expected: `AttributeError: 'ProjectionPlot' object has no attribute 'plot_time_colored_curve'`.

- [ ] **Step 3: Implement the method**

```python
# SciQLop/user_api/plot/_plots.py
class ProjectionPlot:
    ...
    @experimental_api()
    @on_main_thread
    def plot_time_colored_curve(
        self,
        x, y, t,
        *,
        name: str | None = None,
        colormap: str | ColorGradient = "viridis",
        line_width: float = 2.0,
    ) -> Graph:
        x, y, t = ensure_arrays_of_double(x, y, t)
        impl = self._get_impl_or_raise()
        graph_impl = impl.add_time_colored_curve(x, y, t, name=name or "",
                                                  colormap=colormap,
                                                  line_width=line_width)
        return Graph(graph_impl, plot=self)
```

Exact upstream method name (`add_time_colored_curve`) may differ — use whatever `SciQLopNDProjectionPlot` exposes. If no such method exists, build it by adding a `ParametricCurve` graph and setting per-point colors via the upstream color API.

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_projection_controls.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/plot/_plots.py tests/test_projection_controls.py
git commit -m "feat(plot): add ProjectionPlot.plot_time_colored_curve"
```

---

## Task 7: Add Waterfall plot

**Files:**
- Modify: `SciQLop/user_api/plot/_graphs.py`
- Modify: `SciQLop/user_api/plot/_plots.py`
- Modify: `SciQLop/user_api/plot/_panel.py`
- Modify: `SciQLop/user_api/plot/enums.py` (already done in Task 1)
- Modify: `SciQLop/user_api/plot/__init__.py`
- Test: `tests/test_waterfall.py`

**Interfaces:**
- Consumes: `SciQLopWaterfallGraph` from SciQLopPlots 0.34.0.
- Produces: `Waterfall` plottable, `XYPlot.waterfall(...)`, `TimeSeriesPlot.waterfall(...)`, `PlotPanel.waterfall(...)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_waterfall.py
import numpy as np
import pytest
from SciQLop.user_api.plot import create_plot_panel
from SciQLop.user_api.plot.enums import GraphType


@pytest.fixture
def waterfall_data():
    x = np.linspace(0, 10, 50)
    y = np.linspace(0, 5, 10)
    z = np.sin(x) * np.exp(-y[:, None])
    return x, y, z


def test_panel_waterfall_returns_wrapper(waterfall_data):
    panel = create_plot_panel("waterfall")
    x, y, z = waterfall_data
    wf = panel.waterfall(x, y, z)
    assert wf is not None


def test_waterfall_shape_validation(waterfall_data):
    panel = create_plot_panel("waterfall-bad")
    x, y, z = waterfall_data
    with pytest.raises(ValueError):
        panel.waterfall(x, y, z[:-1])  # wrong y length


def test_waterfall_omnibus_dispatcher(waterfall_data):
    panel = create_plot_panel("waterfall-dispatch")
    x, y, z = waterfall_data
    wf = panel.plot(x, y, z, graph_type=GraphType.Waterfall)
    assert wf is not None


def test_waterfall_setters(waterfall_data):
    panel = create_plot_panel("waterfall-setters")
    x, y, z = waterfall_data
    wf = panel.waterfall(x, y, z)
    wf.gain = 2.0
    wf.normalize = True
    assert wf.gain == 2.0
    assert wf.normalize is True
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_waterfall.py -v
```

Expected: `AttributeError` / `ImportError` for `Waterfall`.

- [ ] **Step 3: Add the `Waterfall` wrapper**

```python
# SciQLop/user_api/plot/_graphs.py
from SciQLopPlots import SciQLopWaterfallGraph as _SciQLopWaterfallGraph

__all__ = ['Graph', 'ColorMap', 'Histogram2D', 'Waterfall']


class Waterfall(Plottable):
    def __init__(self, impl):
        self._impl: _SciQLopWaterfallGraph = impl
        _wire_destroyed(self, impl)

    def _on_destroyed(self):
        self._impl = None

    def _get_impl_or_raise(self):
        if self._impl is None:
            raise ValueError("The waterfall graph does not exist anymore.")
        return self._impl

    @on_main_thread
    def set_data(self, x, y, z):
        x, y, z = ensure_arrays_of_double(x, y, z)
        if z.shape != (len(y), len(x)):
            raise ValueError(
                f"z shape {z.shape} does not match (len(y)={len(y)}, len(x)={len(x)})"
            )
        self._get_impl_or_raise().set_data(x, y, z)

    @property
    @on_main_thread
    def data(self):
        return self._get_impl_or_raise().data()

    @data.setter
    @on_main_thread
    def data(self, data):
        self.set_data(*data)

    @property
    @on_main_thread
    def offsets(self):
        return self._get_impl_or_raise().offsets()

    @offsets.setter
    @on_main_thread
    def offsets(self, values):
        self._get_impl_or_raise().set_offsets(np.asarray(values, dtype=np.float64))

    @property
    @on_main_thread
    def gain(self) -> float:
        return self._get_impl_or_raise().gain()

    @gain.setter
    @on_main_thread
    def gain(self, value: float):
        self._get_impl_or_raise().set_gain(float(value))

    @property
    @on_main_thread
    def normalize(self) -> bool:
        return self._get_impl_or_raise().normalize()

    @normalize.setter
    @on_main_thread
    def normalize(self, value: bool):
        self._get_impl_or_raise().set_normalize(bool(value))

    @property
    @on_main_thread
    def color(self):
        return self._get_impl_or_raise().color()

    @color.setter
    @on_main_thread
    def color(self, value):
        self._get_impl_or_raise().set_color(QColor(value))

    @property
    @on_main_thread
    def visible(self) -> bool:
        return self._get_impl_or_raise().visible()

    @visible.setter
    @on_main_thread
    def visible(self, visible: bool):
        self._get_impl_or_raise().set_visible(visible)
```

Update `to_plottable` to recognize waterfall graphs before the generic `Graph` fallback.

- [ ] **Step 4: Add typed methods**

```python
# SciQLop/user_api/plot/_plots.py — on XYPlot and TimeSeriesPlot
@experimental_api()
@on_main_thread
def waterfall(self, x, y, z, *, name: str | None = None,
              offsets=None, gain: float = 1.0, normalize: bool = False,
              color=None):
    x, y, z = ensure_arrays_of_double(x, y, z)
    if z.shape != (len(y), len(x)):
        raise ValueError(f"z shape {z.shape} does not match (len(y)={len(y)}, len(x)={len(x)})")
    plot_impl = self._get_impl_or_raise()
    _reject_if_colormap_already_present(plot_impl)
    impl = plot_impl.add_waterfall(name=name or "")
    wf = Waterfall(impl)
    wf.set_data(x, y, z)
    if offsets is not None:
        wf.offsets = offsets
    wf.gain = gain
    wf.normalize = normalize
    if color is not None:
        wf.color = color
    return wf
```

```python
# SciQLop/user_api/plot/_panel.py — on PlotPanel
@experimental_api()
@on_main_thread
def waterfall(self, x, y, z, *, plot_index: int = -1, name: str | None = None,
              offsets=None, gain: float = 1.0, normalize: bool = False,
              color=None):
    impl = self._get_impl_or_raise()
    plot_impl = impl.create_plot(plot_index, _PlotType.BasicXY)
    plot = XYPlot(plot_impl)
    return plot.waterfall(x, y, z, name=name, offsets=offsets,
                          gain=gain, normalize=normalize, color=color)
```

- [ ] **Step 5: Wire the omnibus dispatcher**

In `PlotPanel.plot(...)`, add a branch for `GraphType.Waterfall` that calls `self.waterfall(...)`.

- [ ] **Step 6: Export `Waterfall`**

```python
# SciQLop/user_api/plot/__init__.py
from ._graphs import Graph, ColorMap, Histogram2D, Waterfall
```

- [ ] **Step 7: Run tests to verify they pass**

```bash
pytest tests/test_waterfall.py -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add SciQLop/user_api/plot/_graphs.py SciQLop/user_api/plot/_plots.py SciQLop/user_api/plot/_panel.py SciQLop/user_api/plot/__init__.py tests/test_waterfall.py
git commit -m "feat(plot): add Waterfall plot API"
```

---

## Task 8: Add catalog overlay attachment

**Files:**
- Create: `SciQLop/user_api/catalogs/_overlay.py`
- Modify: `SciQLop/user_api/catalogs/__init__.py`
- Modify: `SciQLop/user_api/plot/_panel.py`
- Test: `tests/test_catalog_overlay_api.py`

**Interfaces:**
- Consumes: `PanelCatalogManager` (`SciQLop/components/catalogs/backend/panel_manager.py`).
- Produces: `CatalogOverlay`, `add_catalog_overlay(...)`, `remove_catalog_overlay(...)`, `PlotPanel.add_catalog_overlay(...)`, `PlotPanel.remove_catalog_overlay(...)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_catalog_overlay_api.py
import pytest
from SciQLop.user_api.plot import create_plot_panel
from SciQLop.user_api.catalogs import catalogs, add_catalog_overlay
import numpy as np


@pytest.fixture
def sample_catalog():
    path = "My Catalogs//test-events"
    catalogs.create(path, [])
    catalogs.add_events(path, [{
        "start": np.datetime64("2024-01-01"),
        "stop": np.datetime64("2024-01-02"),
        "color": "#ff0000",
    }])
    return path


def test_add_and_remove_catalog_overlay(sample_catalog):
    panel = create_plot_panel("catalog-overlay")
    overlay = panel.add_catalog_overlay(sample_catalog)
    assert overlay.catalog_path == sample_catalog
    overlay.remove()


def test_remove_via_helper(sample_catalog):
    panel = create_plot_panel("catalog-overlay2")
    overlay = add_catalog_overlay(panel, sample_catalog, label="events")
    assert overlay.label == "events"
    panel.remove_catalog_overlay(overlay)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_catalog_overlay_api.py -v
```

Expected: `AttributeError: 'PlotPanel' object has no attribute 'add_catalog_overlay'`.

- [ ] **Step 3: Implement the overlay wrapper and helpers**

```python
# SciQLop/user_api/catalogs/_overlay.py
from .._annotations import experimental_api
from SciQLop.components.catalogs.backend.panel_manager import PanelCatalogManager


class CatalogOverlay:
    def __init__(self, panel_impl, catalog_path, *, override_color=None, label=None):
        self._panel_impl = panel_impl
        self._catalog_path = catalog_path
        self._override_color = override_color
        self._label = label
        # Delegate to the existing backend manager.
        self._manager = PanelCatalogManager(panel_impl)
        self._manager.add_overlay(catalog_path, color=override_color, label=label)

    @property
    def catalog_path(self) -> str:
        return self._catalog_path

    @property
    def override_color(self) -> str | None:
        return self._override_color

    @override_color.setter
    def override_color(self, value: str | None):
        self._override_color = value
        self._manager.update_overlay(self._catalog_path, color=value)

    @property
    def label(self) -> str | None:
        return self._label

    @label.setter
    def label(self, value: str | None):
        self._label = value
        self._manager.update_overlay(self._catalog_path, label=value)

    def remove(self) -> None:
        self._manager.remove_overlay(self._catalog_path)


@experimental_api()
def add_catalog_overlay(panel, catalog_path, *, override_color=None, label=None):
    return CatalogOverlay(panel._get_impl_or_raise(), catalog_path,
                          override_color=override_color, label=label)


@experimental_api()
def remove_catalog_overlay(panel, overlay: CatalogOverlay) -> None:
    overlay.remove()
```

Adjust method names (`add_overlay`, `update_overlay`, `remove_overlay`) to match the actual `PanelCatalogManager` API.

- [ ] **Step 4: Export helpers and wire panel methods**

```python
# SciQLop/user_api/catalogs/__init__.py
from ._overlay import add_catalog_overlay, remove_catalog_overlay, CatalogOverlay
```

```python
# SciQLop/user_api/plot/_panel.py
@experimental_api()
@on_main_thread
def add_catalog_overlay(self, catalog_path, *, override_color=None, label=None):
    from SciQLop.user_api.catalogs._overlay import CatalogOverlay
    return CatalogOverlay(self._get_impl_or_raise(), catalog_path,
                          override_color=override_color, label=label)

@experimental_api()
@on_main_thread
def remove_catalog_overlay(self, overlay):
    overlay.remove()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_catalog_overlay_api.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add SciQLop/user_api/catalogs/_overlay.py SciQLop/user_api/catalogs/__init__.py SciQLop/user_api/plot/_panel.py tests/test_catalog_overlay_api.py
git commit -m "feat(catalogs): add programmatic catalog overlay attachment API"
```

---

## Task 9: Wire GraphLineStyle and AxisType into plotting methods

**Files:**
- Modify: `SciQLop/user_api/plot/_panel.py`
- Modify: `SciQLop/user_api/plot/_plots.py`
- Modify: `SciQLop/user_api/plot/_graphs.py` (Graph line-style setter if needed)
- Test: `tests/test_line_style_axis_type.py`

**Interfaces:**
- Consumes: `GraphLineStyle`, `AxisType` from Task 1.
- Produces: `line_style` parameter on plotting methods; `set_axis_type` on `_BasePlot`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_line_style_axis_type.py
import numpy as np
import pytest
from SciQLop.user_api.plot import create_plot_panel
from SciQLop.user_api.plot.enums import GraphLineStyle, AxisType


def test_plot_data_accepts_line_style():
    panel = create_plot_panel("line-style")
    _, graph = panel.plot_data(np.arange(10), np.arange(10), line_style=GraphLineStyle.Dash)
    # Upstream may not expose a getter; the call must not raise.


def test_set_axis_type():
    panel = create_plot_panel("axis-type")
    plot = panel.plot_data(np.arange(10), np.arange(10))
    plot.set_axis_type("y", AxisType.Logarithmic)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_line_style_axis_type.py -v
```

Expected: `TypeError: plot_data() got an unexpected keyword argument 'line_style'` / `set_axis_type` missing.

- [ ] **Step 3: Add line_style support**

```python
# SciQLop/user_api/plot/_panel.py
def plot_data(self, x, y=None, z=None, plot_index=-1, *,
              labels=_UNSET, name=_UNSET, plot_type=_UNSET, graph_type=_UNSET,
              colors=_UNSET, y_log_scale=_UNSET, z_log_scale=_UNSET,
              line_style: GraphLineStyle | None = None, **kwargs):
    kwargs = _with_explicit(kwargs, line_style=line_style)
    ...
```

Similarly update `XYPlot.plot` and `TimeSeriesPlot.plot` signatures to accept `line_style` and forward it to the upstream graph creation.

- [ ] **Step 4: Add set_axis_type**

```python
# SciQLop/user_api/plot/_plots.py — on _BasePlot or XYPlot/TimeSeriesPlot
@on_main_thread
def set_axis_type(self, axis: str, axis_type: AxisType) -> None:
    plot_impl = self._get_impl_or_raise()
    axis_impl = self._resolve_axis(axis)
    axis_impl.set_axis_type(axis_type.value)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_line_style_axis_type.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add SciQLop/user_api/plot/_panel.py SciQLop/user_api/plot/_plots.py SciQLop/user_api/plot/_graphs.py tests/test_line_style_axis_type.py
git commit -m "feat(plot): expose GraphLineStyle and AxisType in plotting API"
```

---

## Self-review checklist

1. **Spec coverage:**
   - Waterfall plot → Task 7.
   - 2D histogram log bins → Task 4.
   - Projection axis controls → Task 5.
   - Time-colored parametric curve → Task 6.
   - Catalog overlay attachment → Task 8.
   - Runtime theme switching → Task 3.
   - Extra graphic primitives → Task 2.
   - `GraphLineStyle` / `AxisType` → Tasks 1 and 9.
   - Out-of-scope items (remote graphs, function-plot helpers, inspector infrastructure, SingleLine) are not in any task.

2. **Placeholder scan:**
   - No "TBD" / "TODO" / "implement later" strings.
   - `_symlog_space` in Task 4 is a concrete stub with a note to align with SciQLopPlots; acceptable because the exact SciQLopPlots API is not visible from Python stubs.
   - `PanelCatalogManager` method names in Task 8 are guessed; the implementer must verify them against the actual backend class before committing.

3. **Type consistency:**
   - `histogram2d` signatures use `x_bins`, `y_bins`, `x_bin_strategy`, `y_bin_strategy` consistently across `_panel.py`, `_plots.py`, and `_graphs.py`.
   - `Waterfall` constructor/typed methods use the same `(x, y, z, *, name, offsets, gain, normalize, color)` shape.
   - `GraphLineStyle` and `AxisType` enum member names match upstream; the implementer must verify actual SciQLopPlots names during Task 1.

4. **Ordering:**
   - Task 1 (enums) and Task 2 (primitives) are independent and can be done in parallel.
   - Task 3 (theme) is independent.
   - Tasks 4–9 depend on Task 1 enums.
   - Task 7 (waterfall) depends on `GraphType.Waterfall` from Task 1.
   - Task 9 depends on Task 1 and the plotting methods from Tasks 4 and 7.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-07-plot-api-sciqlopplots-catchup.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
