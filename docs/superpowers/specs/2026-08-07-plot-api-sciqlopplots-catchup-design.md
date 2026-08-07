# Plot API — SciQLopPlots Catch-up Design

**Date:** 2026-08-07  
**Status:** Design  
**Scope:** Close the remaining gaps between SciQLopPlots 0.34.0 capabilities and the public `SciQLop.user_api.plot` surface, driven by the v0.13 website gallery shots.

## Goals

Expose enough of SciQLopPlots 0.34.0 through `SciQLop.user_api.plot` so that every gallery shot can be reproduced from a notebook or plugin script without touching internal modules.

Specifically:

1. **Waterfall plot** — public API for stacked spectral traces with offset/gain/normalize.
2. **2D histogram log bins** — add `BinStrategy` for log/symlog bin spacing.
3. **Projection plot controls** — implement stubbed axis range/scale methods and add time-colored parametric curves.
4. **Catalog overlay attachment** — script API to attach a catalog overlay to a panel.
5. **Runtime theme switching** — public API to apply the four built-in palettes.
6. **Additional graphic primitives** — wrap `VerticalLine`, `StraightLine`, `RectangularSpan`, `HorizontalSpan` from SciQLopPlots.
7. **Small SciQLopPlots enum additions** — `GraphLineStyle` and `AxisType`.

## Out of scope

- Generic remote-graph / `DataSource` facade — too much new surface without a concrete user workflow; leave internal until a plugin needs it.
- Explicit function-plot helpers — existing `plot_function` covers the common case.
- Full inspector/property/pipeline subsystem exposure — speculative; revisit when a concrete use case appears.
- `GraphType.SingleLine` — deferred until a concrete performance need is demonstrated.

## Guiding principles

- No breaking changes to existing public signatures.
- New features get explicit typed methods *and* entries in the omnibus `panel.plot(...)` dispatcher.
- Follow existing conventions in `SciQLop/user_api/plot/` (wrapper classes, `@experimental_api()`, `on_main_thread`, palette-aware defaults).
- Every new public symbol is a long-term promise — keep the surface small.

---

## Phase 1 — Gallery-ready APIs

### 1.1 Waterfall plot

#### Files

- `SciQLop/user_api/plot/_graphs.py` — add `Waterfall` plottable wrapper.
- `SciQLop/user_api/plot/_plots.py` — add `waterfall()` method to `XYPlot` and `TimeSeriesPlot`.
- `SciQLop/user_api/plot/_panel.py` — add `waterfall()` method to `PlotPanel`.
- `SciQLop/user_api/plot/enums.py` — add `GraphType.Waterfall`.
- `SciQLop/user_api/plot/__init__.py` — export `Waterfall`.

#### `Waterfall` class

```python
class Waterfall(Plottable):
    @on_main_thread
    def set_data(self, x: np.ndarray, y: np.ndarray, z: np.ndarray, /) -> None: ...

    @property
    def data(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]: ...

    @property
    def offsets(self) -> np.ndarray: ...
    @offsets.setter
    def offsets(self, values: ArrayLike) -> None: ...

    @property
    def gain(self) -> float: ...
    @gain.setter
    def gain(self, value: float) -> None: ...

    @property
    def normalize(self) -> bool: ...
    @normalize.setter
    def normalize(self, value: bool) -> None: ...

    @property
    def color(self) -> str: ...
    @color.setter
    def color(self, value: str | ColorType) -> None: ...
```

#### Plot/Panel methods

```python
@experimental_api()
@on_main_thread
def waterfall(
    self,
    x: ArrayLike,        # 1D shared axis (e.g. frequency)
    y: ArrayLike,        # 1D per-trace coordinate (e.g. time)
    z: ArrayLike,        # 2D array, shape (len(y), len(x))
    *,
    name: str | None = None,
    offsets: ArrayLike | float | None = None,  # None = auto-derived from y spacing
    gain: float = 1.0,
    normalize: bool = False,
    color: str | ColorType | None = None,      # None = palette-aware default
) -> Waterfall: ...
```

- On `PlotPanel`: creates or reuses a plot at `plot_index`, dispatches to `plot.waterfall(...)`, returns `Waterfall`.
- On `XYPlot` / `TimeSeriesPlot`: adds the upstream `SciQLopWaterfallGraph`, calls `set_data`, applies styling.

Also add `GraphType.Waterfall` so `panel.plot(x, y, z, graph_type=GraphType.Waterfall)` works.

#### `PlotPanel.waterfall` signature

Same as the plot-level method, plus `plot_index`:

```python
def waterfall(
    self,
    x: ArrayLike,
    y: ArrayLike,
    z: ArrayLike,
    *,
    plot_index: int = -1,
    name: str | None = None,
    offsets: ArrayLike | float | None = None,
    gain: float = 1.0,
    normalize: bool = False,
    color: str | ColorType | None = None,
) -> Waterfall: ...
```

---

### 1.2 2D histogram log bins

#### Files

- `SciQLop/user_api/plot/enums.py` — add `BinStrategy`.
- `SciQLop/user_api/plot/_panel.py`, `_plots.py`, `_graphs.py` — extend `histogram2d()` signatures.

#### `BinStrategy` enum

```python
class BinStrategy(Enum):
    Linear = "linear"
    Log = "log"
    SymLog = "symlog"
```

#### Revised `histogram2d` signature

```python
@experimental_api()
@on_main_thread
def histogram2d(
    self,
    x: ArrayLike,
    y: ArrayLike,
    *,
    x_bins: int | ArrayLike = 100,
    y_bins: int | ArrayLike = 100,
    x_bin_strategy: BinStrategy = BinStrategy.Linear,
    y_bin_strategy: BinStrategy = BinStrategy.Linear,
    z_log_scale: bool = False,
    name: str = "histogram",
    plot_index: int = -1,
) -> Histogram2D: ...  # PlotPanel returns Tuple[XYPlot, Histogram2D]
```

- `x_bins` / `y_bins` = number of bins **or** explicit bin edges, matching NumPy convention.
- `x_bin_strategy` / `y_bin_strategy` are applied only when bins are given as an integer.
- `BinStrategy.Log` generates edges via `np.geomspace`; `SymLog` uses `symlog` linthresh derived from data range.

---

### 1.3 Projection plot controls

#### Files

- `SciQLop/user_api/plot/_plots.py` — implement stubs and add `plot_time_colored_curve`.

#### Axis range/scale

The following methods are currently no-ops. Implement them by delegating to the underlying `SciQLopNDProjectionPlot`:

```python
class ProjectionPlot:
    def set_x_range(self, lo: float, hi: float) -> None: ...
    def set_y_range(self, lo: float, hi: float) -> None: ...
    def set_x_scale_type(self, scale: ScaleType) -> None: ...
    def set_y_scale_type(self, scale: ScaleType) -> None: ...
```

#### Time-colored parametric curve

```python
@experimental_api()
@on_main_thread
def plot_time_colored_curve(
    self,
    x: ArrayLike,
    y: ArrayLike,
    t: ArrayLike,
    *,
    name: str | None = None,
    colormap: str | ColorGradient = "viridis",
    line_width: float = 2.0,
) -> Graph: ...
```

`x`, `y`, `t` are 1D arrays of equal length. The curve is colored by `t` using the upstream parametric-curve + colormap support.

---

### 1.4 Catalog overlay attachment

#### Files

- `SciQLop/user_api/catalogs/_overlay.py` — new file with `CatalogOverlay` wrapper and attach helpers.
- `SciQLop/user_api/catalogs/__init__.py` — export `add_catalog_overlay`, `remove_catalog_overlay`.
- `SciQLop/user_api/plot/_panel.py` — add `add_catalog_overlay` / `remove_catalog_overlay` methods on `PlotPanel`.

#### API

```python
class CatalogOverlay:
    @property
    def catalog_path(self) -> str: ...

    @property
    def override_color(self) -> str | None: ...
    @override_color.setter
    def override_color(self, value: str | None) -> None: ...

    @property
    def label(self) -> str | None: ...
    @label.setter
    def label(self, value: str | None) -> None: ...

    def remove(self) -> None: ...


def add_catalog_overlay(
    panel: PlotPanel,
    catalog_path: str,
    *,
    override_color: str | None = None,
    label: str | None = None,
) -> CatalogOverlay: ...


def remove_catalog_overlay(panel: PlotPanel, overlay: CatalogOverlay) -> None: ...
```

On `PlotPanel`:

```python
@experimental_api()
def add_catalog_overlay(
    self,
    catalog_path: str,
    *,
    override_color: str | None = None,
    label: str | None = None,
) -> CatalogOverlay: ...

@experimental_api()
def remove_catalog_overlay(self, overlay: CatalogOverlay) -> None: ...
```

Implementation delegates to the existing `PanelCatalogManager` (`SciQLop/components/catalogs/backend/panel_manager.py`).

---

### 1.5 Runtime theme switching

#### Files

- `SciQLop/user_api/themes/__init__.py` — new module.
- `SciQLop/user_api/__init__.py` — re-export `themes`.

#### API

```python
from typing import Literal

PaletteName = Literal["light", "dark", "neutral", "space"]


def apply_theme(name: PaletteName) -> None:
    """Switch the running application to the named palette."""
    ...


def current_theme() -> PaletteName: ...


def list_themes() -> list[PaletteName]: ...
```

`apply_theme` delegates to `sciqlop_app().apply_theme(name)` (`SciQLop/core/sciqlop_application.py`).

---

### 1.6 Additional graphic primitives

#### Files

- `SciQLop/user_api/plot/_graphic_primitives.py` — add wrappers.
- `SciQLop/user_api/plot/__init__.py` — export new classes.

#### New classes

```python
class VerticalLine(GraphicPrimitive):
    def __init__(self, x: float, *, color: ColorType | None = None, width: float = 1.0): ...


class StraightLine(GraphicPrimitive):
    def __init__(self, x1: float, y1: float, x2: float, y2: float, *,
                 color: ColorType | None = None, width: float = 1.0,
                 termination: LineTermination | None = None): ...


class RectangularSpan(GraphicPrimitive):
    def __init__(self, x1: float, y1: float, x2: float, y2: float, *,
                 color: ColorType | None = None, fill: bool = True,
                 opacity: float = 0.3): ...


class HorizontalSpan(GraphicPrimitive):
    def __init__(self, y1: float, y2: float, *,
                 color: ColorType | None = None, fill: bool = True,
                 opacity: float = 0.3): ...
```

Each wrapper delegates to the matching `SciQLopPlots` item and uses the existing palette-aware color default logic.

---

## Phase 2 — Small SciQLopPlots enum additions

### 2.1 GraphLineStyle

#### Files

- `SciQLop/user_api/plot/enums.py` — add `GraphLineStyle`.
- `SciQLop/user_api/plot/_graphs.py` / `_panel.py` — accept `line_style` in plotting methods.

#### API

```python
class GraphLineStyle(Enum):
    Solid = _SQP.GraphLineStyle.Solid.value
    Dash = _SQP.GraphLineStyle.Dash.value
    Dot = _SQP.GraphLineStyle.Dot.value
    DashDot = _SQP.GraphLineStyle.DashDot.value
    DashDotDot = _SQP.GraphLineStyle.DashDotDot.value
```

(Exact member names follow `SciQLopPlots.GraphLineStyle`; adjust if upstream naming differs.)

Add `line_style: GraphLineStyle | None = None` keyword-only argument to:

- `PlotPanel.plot_data`
- `XYPlot.plot`
- `TimeSeriesPlot.plot`
- `Graph` constructor/setters (where applicable)

`None` means upstream default.

### 2.2 AxisType

#### Files

- `SciQLop/user_api/plot/enums.py` — add `AxisType`.
- `SciQLop/user_api/plot/_plots.py` — add `set_axis_type` on `_BasePlot`.

#### API

```python
class AxisType(Enum):
    Linear = _SQP.AxisType.Linear.value
    Logarithmic = _SQP.AxisType.Logarithmic.value
    DateTime = _SQP.AxisType.DateTime.value
```

(Exact member names follow `SciQLopPlots.AxisType`; adjust if upstream naming differs.)

```python
def set_axis_type(self, axis: Literal["x", "y", "y2"], axis_type: AxisType) -> None: ...
```

This complements the existing `set_axis_scale` (which only toggles linear/log) by allowing explicit datetime axis configuration where supported.

---

## Error handling

- Invalid enum values raise `ValueError` with the accepted values listed.
- Shape mismatches (e.g., `z.shape != (len(y), len(x))` for waterfall) raise `ValueError` describing expected vs. actual shape.
- Calling projection-axis methods when the upstream object does not support them raises `RuntimeError`.
- Missing upstream classes at import time raise `ImportError` with a message indicating the required SciQLopPlots version.

---

## Testing strategy

Follow existing `tests/` conventions (`pytest-qt`, `pytest-xvfb`, fixtures in `tests/fixtures.py`).

### New test files

**`tests/test_waterfall.py`**
- `panel.waterfall(x, y, z)` returns `Waterfall`.
- Shape mismatch raises `ValueError`.
- `offsets`, `gain`, `normalize`, `color` round-trip via getters/setters.
- `panel.plot(..., graph_type=GraphType.Waterfall)` produces the same result.

**`tests/test_histogram2d_bins.py`**
- `histogram2d(..., x_bin_strategy=BinStrategy.Log)` produces monotonic log-spaced bin edges.
- `histogram2d(..., x_bins=np.logspace(...))` ignores strategy and uses provided edges.
- `BinStrategy.SymLog` does not crash on data with negative values.

**`tests/test_projection_controls.py`**
- `ProjectionPlot.set_x_range` / `set_y_range` update the visible range.
- `ProjectionPlot.set_x_scale_type` / `set_y_scale_type` toggle linear/log.
- `plot_time_colored_curve(x, y, t)` returns a `Graph` and accepts a colormap name.

**`tests/test_catalog_overlay_api.py`**
- `panel.add_catalog_overlay("My Catalogs//events")` returns `CatalogOverlay`.
- `overlay.remove()` detaches it.
- `override_color` and `label` round-trip.

**`tests/test_theme_api.py`**
- `apply_theme("dark")` does not crash on an existing panel.
- `current_theme()` returns one of the four valid names.
- `list_themes()` returns all four names.

**`tests/test_graphic_primitives.py`**
- `VerticalLine`, `StraightLine`, `RectangularSpan`, `HorizontalSpan` can be added to a plot and removed.
- Default colors are palette-aware.

**`tests/test_line_style_axis_type.py`**
- `GraphLineStyle` values map correctly to SciQLopPlots integers.
- `line_style=GraphLineStyle.Dashed` applies to a line plot.
- `AxisType` values map correctly and `set_axis_type` does not crash.

### Fixture additions

- `synthetic_waterfall_data()` — small 2D spectral array.
- `synthetic_projection_data()` — small 2D trajectory array with time vector.

---

## File map

### New files

- (none; `Waterfall` lands in the existing `_graphs.py`)
- `SciQLop/user_api/catalogs/_overlay.py` — `CatalogOverlay` + attach helpers.
- `SciQLop/user_api/themes/__init__.py` — theme facade.
- `tests/test_waterfall.py`
- `tests/test_histogram2d_bins.py`
- `tests/test_projection_controls.py`
- `tests/test_catalog_overlay_api.py`
- `tests/test_theme_api.py`
- `tests/test_graphic_primitives.py`
- `tests/test_line_style_axis_type.py`

### Modified files

- `SciQLop/user_api/plot/enums.py` — add `GraphType.Waterfall`, `BinStrategy`, `GraphLineStyle`, `AxisType`.
- `SciQLop/user_api/plot/_graphic_primitives.py` — add `VerticalLine`, `StraightLine`, `RectangularSpan`, `HorizontalSpan`.
- `SciQLop/user_api/plot/_plots.py` — add `waterfall()`, implement projection stubs, add `plot_time_colored_curve()`, add `set_axis_type()`.
- `SciQLop/user_api/plot/_panel.py` — add `waterfall()`, `add_catalog_overlay()`, `remove_catalog_overlay()`, accept `line_style` in `plot_data()`.
- `SciQLop/user_api/plot/__init__.py` — export new classes and enums.
- `SciQLop/user_api/catalogs/__init__.py` — export overlay helpers.
- `SciQLop/user_api/__init__.py` — re-export `themes`.
- `tests/fixtures.py` — add synthetic data helpers.

---

## Build order

1. **Enums + graphic primitives** — small, independent, testable.
2. **Theme API** — independent facade.
3. **Histogram log bins** — extends existing `histogram2d`.
4. **Projection controls + time-colored curve** — extends `ProjectionPlot`.
5. **Waterfall** — new graph type.
6. **Catalog overlay attachment** — wraps existing backend manager.
7. **Line style + axis type** — small additive enum wiring.

Each item can land in its own PR; Phase 1 items should precede Phase 2.
