# Plot API Extensions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose `SciQLopHistogram2D`, `SciQLopOverlay`, and the `SciQLopPlots.dsp` module through `SciQLop.user_api`, all marked `@experimental_api()`.

**Architecture:** Three independent surfaces in four bottom-up phases. Histogram2D mirrors the `ColorMap` plottable shape. Overlay is a thin wrapper class accessed via a property on plot classes. DSP is a two-layer facade: `_arrays.py` (typed pass-through) + `__init__.py` (per-function `SpeasyVariable` adapters).

**Tech Stack:** Python 3.13, PySide6, SciQLopPlots Python bindings, speasy, pytest + pytest-qt + pytest-xvfb.

---

## Important deltas from spec (verified against current bindings)

These supersede the spec where they conflict — use them as authoritative:

1. **`SciQLopNDProjectionPlot` has NO `overlay()` method.** Only `SciQLopPlot` and `SciQLopTimeSeriesPlot` do. So the `overlay` property goes on `_BasePlot` (parent of `XYPlot` / `TimeSeriesPlot`); `ProjectionPlot` does **not** get it. Tests must skip `ProjectionPlot` for overlay.

2. **Real DSP signatures** (from `SciQLopPlots.dsp` introspection):

   | Function | Real signature | Returns |
   |---|---|---|
   | `fft(x, y, gap_factor=3.0, window='hann')` | per-segment | `list[(freqs, magnitude)]` |
   | `filtfilt(x, y, coeffs, gap_factor=3.0, has_gaps=True)` | scipy-equiv | `(x_out, y_out)` |
   | `sosfiltfilt(x, y, sos, gap_factor=3.0, has_gaps=True)` | scipy-equiv | `(x_out, y_out)` |
   | `fir_filter(x, y, coeffs, gap_factor=3.0)` | per-segment | `(x_out, y_out)` |
   | `iir_sos(x, y, sos, gap_factor=3.0)` | per-segment | `(x_out, y_out)` |
   | `resample(x, y, gap_factor=3.0, target_dt=0.0)` | uniform grid | `(x_out, y_out)` |
   | `interpolate_nan(x, y, max_consecutive=1)` | NaN runs | `y_out` (no x) |
   | `rolling_mean(x, y, window, gap_factor=3.0)` | gap-aware | `(x_out, y_out)` |
   | `rolling_std(x, y, window, gap_factor=3.0)` | gap-aware | `(x_out, y_out)` |
   | `spectrogram(x, y, col=0, window_size=256, overlap=0, gap_factor=3.0, window='hann')` | per-segment | `list[(t, f, power)]` |
   | `reduce(x, y, op, gap_factor=3.0)` | column → 1 | `(x_out, y_out)` |
   | `reduce_axes(x, y, shape, axes, op='sum', has_gaps=False)` | n-dim | `(x_out, y_out)` |
   | `split_segments(x, y, gap_factor=3.0)` | gap detection | `list[(start, end)]` index ranges |

   Per-segment returns (`fft`, `spectrogram`) become `list[SpeasyVariable]` in the speasy layer. `split_segments` → if input is `SpeasyVariable`, returns `list[SpeasyVariable]` of slices; if input is arrays, returns the raw `list[(start, end)]`.

3. **`SciQLopHistogram2D` inherits from `SciQLopColorMapBase`** — so `isinstance(impl, _SciQLopHistogram2D)` correctly disambiguates from `SciQLopColorMap` (sibling), but the `_SciQLopHistogram2D` import must use the public binding name.

---

## Conventions

- **Always** prefix every command with `uv run` (project rule).
- **Tests** use `pytest-qt` (`qtbot`) and the existing `plot_panel` fixture from `tests/fixtures.py`.
- **Commits**: one per task. Use Conventional Commits (`feat(user_api): ...`, `test(user_api): ...`).
- **Imports of SciQLopPlots types** in `user_api/` files use the `_SciQLop…` aliasing convention (see `_plots.py:8` for the pattern).
- **Threading**: every public method touching Qt MUST have `@on_main_thread`. Properties: decorator goes on getter and setter separately.
- **Docstrings**: numpy-style, matching existing classes (see `_plots.py:94-103`).

---

# Phase 1 — Overlay (Tasks 1–4)

## Task 1: Add overlay enums to `enums.py`

**Files:**
- Modify: `SciQLop/user_api/plot/enums.py`

- [ ] **Step 1: Append the three overlay enums to the file**

Append to `SciQLop/user_api/plot/enums.py`:

```python


class OverlayLevel(Enum):
    """Severity level of an overlay message."""
    Info = 0
    Warning = 1
    Error = 2


class OverlaySizeMode(Enum):
    """How the overlay sizes itself relative to the plot."""
    Compact = 0
    FitContent = 1
    FullWidget = 2


class OverlayPosition(Enum):
    """Where the overlay anchors inside the plot."""
    Top = 0
    Bottom = 1
    Left = 2
    Right = 3
```

- [ ] **Step 2: Verify the enums import**

Run: `uv run python -c "from SciQLop.user_api.plot.enums import OverlayLevel, OverlaySizeMode, OverlayPosition; print(OverlayLevel.Info, OverlaySizeMode.FitContent, OverlayPosition.Top)"`
Expected: `OverlayLevel.Info OverlaySizeMode.FitContent OverlayPosition.Top`

- [ ] **Step 3: Commit**

```bash
git add SciQLop/user_api/plot/enums.py
git commit -m "feat(user_api): add overlay enums (Level, SizeMode, Position)"
```

---

## Task 2: Create `Overlay` wrapper class

**Files:**
- Create: `SciQLop/user_api/plot/_overlay.py`

- [ ] **Step 1: Create the file with the wrapper class**

Create `SciQLop/user_api/plot/_overlay.py` with full content:

```python
from SciQLopPlots import (SciQLopOverlay as _SciQLopOverlay,
                          OverlayLevel as _OverlayLevel,
                          OverlaySizeMode as _OverlaySizeMode,
                          OverlayPosition as _OverlayPosition)

from .enums import OverlayLevel, OverlaySizeMode, OverlayPosition
from .._annotations import experimental_api
from ._thread_safety import on_main_thread

__all__ = ['Overlay']


def _to_sqp_level(level: OverlayLevel) -> _OverlayLevel:
    return _OverlayLevel(level.value)


def _from_sqp_level(level: _OverlayLevel) -> OverlayLevel:
    return OverlayLevel(int(level))


def _to_sqp_size_mode(size_mode: OverlaySizeMode) -> _OverlaySizeMode:
    return _OverlaySizeMode(size_mode.value)


def _from_sqp_size_mode(size_mode: _OverlaySizeMode) -> OverlaySizeMode:
    return OverlaySizeMode(int(size_mode))


def _to_sqp_position(position: OverlayPosition) -> _OverlayPosition:
    return _OverlayPosition(position.value)


def _from_sqp_position(position: _OverlayPosition) -> OverlayPosition:
    return OverlayPosition(int(position))


class Overlay:
    """A class wrapping the in-canvas message overlay attached to a plot.

    Use `plot.overlay` to access it. The overlay can show informational, warning,
    or error messages at a chosen position with a chosen sizing behavior, and can
    be made user-collapsible.
    """

    def __init__(self, impl: _SciQLopOverlay):
        self._impl = impl

    @experimental_api()
    @on_main_thread
    def show(self, text: str, *,
             level: OverlayLevel = OverlayLevel.Info,
             size_mode: OverlaySizeMode = OverlaySizeMode.FitContent,
             position: OverlayPosition = OverlayPosition.Top) -> None:
        """Show a message in the overlay.

        Parameters
        ----------
        text : str
            The message to display.
        level : OverlayLevel
            Severity level (Info, Warning, Error).
        size_mode : OverlaySizeMode
            Sizing behavior (Compact, FitContent, FullWidget).
        position : OverlayPosition
            Anchor position (Top, Bottom, Left, Right).
        """
        self._impl.show_message(text,
                                _to_sqp_level(level),
                                _to_sqp_size_mode(size_mode),
                                _to_sqp_position(position))

    @experimental_api()
    @on_main_thread
    def clear(self) -> None:
        """Clear the overlay message."""
        self._impl.clear_message()

    @property
    @on_main_thread
    def text(self) -> str:
        return self._impl.text()

    @property
    @on_main_thread
    def level(self) -> OverlayLevel:
        return _from_sqp_level(self._impl.level())

    @property
    @on_main_thread
    def position(self) -> OverlayPosition:
        return _from_sqp_position(self._impl.position())

    @property
    @on_main_thread
    def size_mode(self) -> OverlaySizeMode:
        return _from_sqp_size_mode(self._impl.size_mode())

    @property
    @on_main_thread
    def collapsible(self) -> bool:
        return self._impl.is_collapsible()

    @collapsible.setter
    @on_main_thread
    def collapsible(self, v: bool) -> None:
        self._impl.set_collapsible(v)

    @property
    @on_main_thread
    def collapsed(self) -> bool:
        return self._impl.is_collapsed()

    @collapsed.setter
    @on_main_thread
    def collapsed(self, v: bool) -> None:
        self._impl.set_collapsed(v)

    @property
    @on_main_thread
    def opacity(self) -> float:
        return self._impl.opacity()

    @opacity.setter
    @on_main_thread
    def opacity(self, v: float) -> None:
        self._impl.set_opacity(v)

    def _repr_pretty_(self, p, cycle):
        if cycle:
            p.text("Overlay(...)")
        else:
            p.text(f"Overlay(text={self.text!r}, level={self.level.name})")
```

- [ ] **Step 2: Verify the file imports**

Run: `uv run python -c "from SciQLop.user_api.plot._overlay import Overlay; print(Overlay)"`
Expected: `<class 'SciQLop.user_api.plot._overlay.Overlay'>`

- [ ] **Step 3: Commit**

```bash
git add SciQLop/user_api/plot/_overlay.py
git commit -m "feat(user_api): add Overlay wrapper class"
```

---

## Task 3: Wire `overlay` property into `_BasePlot` + exports

**Files:**
- Modify: `SciQLop/user_api/plot/_plots.py` (add `overlay` property on `_BasePlot`, ~line 80–92)
- Modify: `SciQLop/user_api/plot/__init__.py`

- [ ] **Step 1: Add `Overlay` import and `overlay` property to `_BasePlot`**

In `SciQLop/user_api/plot/_plots.py`, after the existing imports (around line 14) add:

```python
from ._overlay import Overlay
```

Then in the `_BasePlot` class (around line 80), add the `overlay` property at the end of the class (before the `class XYPlot(_BasePlot):` line):

```python
    @property
    @on_main_thread
    def overlay(self) -> Overlay:
        """Access the in-canvas message overlay for this plot.

        Returns a fresh Overlay handle on each access — the wrapper is cheap
        and avoids stale-reference issues if the underlying overlay is
        recreated.
        """
        return Overlay(self._get_impl_or_raise().overlay())
```

- [ ] **Step 2: Export from the package**

Modify `SciQLop/user_api/plot/__init__.py`. Replace the `from .enums import` line and `__all__` list:

```python
"""Plotting API. This module provides the public API for plotting data and managing plot panels.
"""
from .enums import ScaleType, PlotType, OverlayLevel, OverlaySizeMode, OverlayPosition
from .protocol import Plot, Plottable

from SciQLop.components.sciqlop_logging import getLogger as _getLogger
from ._plots import XYPlot, TimeSeriesPlot, ProjectionPlot, TimeRange
from ._panel import PlotPanel, create_plot_panel, plot_panel
from ._graphic_primitives import Ellipse, Text, CurvedLine
from ._overlay import Overlay
from . import _fluent as fluent

log = _getLogger(__name__)

__all__ = ['ScaleType', 'PlotType', 'Plot', 'Plottable', 'XYPlot', 'TimeSeriesPlot', 'ProjectionPlot', 'PlotPanel',
           'create_plot_panel', 'plot_panel', 'TimeRange', 'Ellipse', 'fluent',
           'Overlay', 'OverlayLevel', 'OverlaySizeMode', 'OverlayPosition']
```

- [ ] **Step 3: Smoke test the wiring**

Run:
```bash
uv run python -c "
from SciQLop.user_api.plot import Overlay, OverlayLevel, OverlaySizeMode, OverlayPosition, XYPlot, TimeSeriesPlot
print('Overlay:', Overlay)
print('Levels:', list(OverlayLevel))
assert hasattr(XYPlot, 'overlay')
assert hasattr(TimeSeriesPlot, 'overlay')
print('OK')
"
```
Expected: ends with `OK`.

- [ ] **Step 4: Commit**

```bash
git add SciQLop/user_api/plot/_plots.py SciQLop/user_api/plot/__init__.py
git commit -m "feat(user_api): expose overlay property on plots and re-export"
```

---

## Task 4: Tests for Overlay

**Files:**
- Create: `tests/test_overlay.py`

- [ ] **Step 1: Write the test file**

Create `tests/test_overlay.py`:

```python
"""Tests for the Overlay wrapper exposed via plot.overlay."""
import pytest
import numpy as np

from SciQLop.user_api.plot import (Overlay, OverlayLevel, OverlaySizeMode, OverlayPosition,
                                   PlotType, GraphType)
from SciQLop.user_api.plot._overlay import (_to_sqp_level, _from_sqp_level,
                                            _to_sqp_size_mode, _from_sqp_size_mode,
                                            _to_sqp_position, _from_sqp_position)


@pytest.fixture
def time_series_plot(plot_panel):
    """A TimeSeriesPlot inside the panel, ready for overlay tests."""
    x = np.linspace(0, 100, 50)
    y = np.sin(x)
    plot, _graph = plot_panel.plot_data(x, y, plot_type=PlotType.TimeSeries)
    return plot


@pytest.fixture
def xy_plot(plot_panel):
    x = np.linspace(0, 100, 50)
    y = np.sin(x)
    plot, _graph = plot_panel.plot_data(x, y, plot_type=PlotType.XY,
                                        graph_type=GraphType.Curve)
    return plot


class TestEnumTranslation:
    def test_level_round_trip(self):
        for lvl in OverlayLevel:
            assert _from_sqp_level(_to_sqp_level(lvl)) == lvl

    def test_size_mode_round_trip(self):
        for sm in OverlaySizeMode:
            assert _from_sqp_size_mode(_to_sqp_size_mode(sm)) == sm

    def test_position_round_trip(self):
        for pos in OverlayPosition:
            assert _from_sqp_position(_to_sqp_position(pos)) == pos


class TestOverlayOnTimeSeriesPlot:
    def test_overlay_property_returns_wrapper(self, time_series_plot):
        ov = time_series_plot.overlay
        assert isinstance(ov, Overlay)

    def test_show_text_round_trip(self, time_series_plot):
        time_series_plot.overlay.show("hello", level=OverlayLevel.Warning)
        assert time_series_plot.overlay.text == "hello"
        assert time_series_plot.overlay.level == OverlayLevel.Warning

    def test_show_with_size_mode_and_position(self, time_series_plot):
        time_series_plot.overlay.show("alert",
                                      level=OverlayLevel.Error,
                                      size_mode=OverlaySizeMode.FullWidget,
                                      position=OverlayPosition.Bottom)
        ov = time_series_plot.overlay
        assert ov.text == "alert"
        assert ov.level == OverlayLevel.Error
        assert ov.size_mode == OverlaySizeMode.FullWidget
        assert ov.position == OverlayPosition.Bottom

    def test_clear_empties_text(self, time_series_plot):
        time_series_plot.overlay.show("temporary")
        assert time_series_plot.overlay.text == "temporary"
        time_series_plot.overlay.clear()
        assert time_series_plot.overlay.text == ""

    def test_collapsible_round_trip(self, time_series_plot):
        time_series_plot.overlay.collapsible = True
        assert time_series_plot.overlay.collapsible is True
        time_series_plot.overlay.collapsible = False
        assert time_series_plot.overlay.collapsible is False

    def test_collapsed_round_trip(self, time_series_plot):
        time_series_plot.overlay.collapsible = True
        time_series_plot.overlay.collapsed = True
        assert time_series_plot.overlay.collapsed is True
        time_series_plot.overlay.collapsed = False
        assert time_series_plot.overlay.collapsed is False

    def test_opacity_round_trip(self, time_series_plot):
        time_series_plot.overlay.opacity = 0.42
        assert time_series_plot.overlay.opacity == pytest.approx(0.42, abs=1e-3)


class TestOverlayOnXYPlot:
    def test_overlay_available_on_xy_plot(self, xy_plot):
        xy_plot.overlay.show("xy hi")
        assert xy_plot.overlay.text == "xy hi"
```

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/test_overlay.py -v`
Expected: all tests pass. If a test fails because the underlying `SciQLopOverlay` API differs from what the wrapper assumes (e.g. `text()` accessor not available immediately after `show_message`), fix the wrapper in `_overlay.py` accordingly — do NOT silently weaken the test.

- [ ] **Step 3: Commit**

```bash
git add tests/test_overlay.py
git commit -m "test(user_api): cover Overlay wrapper round-trips"
```

---

# Phase 2 — Histogram2D (Tasks 5–8)

## Task 5: Add `Histogram2D` plottable + update `to_plottable`

**Files:**
- Modify: `SciQLop/user_api/plot/_graphs.py`

- [ ] **Step 1: Add the import for `_SciQLopHistogram2D`**

In `SciQLop/user_api/plot/_graphs.py`, add at the top of the file (after the existing `from ..virtual_products import VirtualProduct` line):

```python
from SciQLopPlots import SciQLopHistogram2D as _SciQLopHistogram2D
```

- [ ] **Step 2: Add `Histogram2D` class**

Append to `SciQLop/user_api/plot/_graphs.py` (just before the `def to_plottable` function):

```python
class Histogram2D(Plottable):
    """A 2D density histogram. Bins (x, y) scatter into a key_bins x value_bins grid."""

    def __init__(self, impl):
        self._impl: _SciQLopHistogram2D = impl

    def _get_impl_or_raise(self):
        if self._impl is None:
            raise ValueError("The histogram does not exist anymore.")
        return self._impl

    @on_main_thread
    def set_data(self, x, y):
        self._impl.set_data(*ensure_arrays_of_double(x, y))

    @property
    @on_main_thread
    def data(self):
        return self._impl.data()

    @data.setter
    @on_main_thread
    def data(self, data):
        self.set_data(*data)

    @property
    @on_main_thread
    def visible(self) -> bool:
        return self._impl.visible()

    @visible.setter
    @on_main_thread
    def visible(self, visible: bool):
        self._impl.set_visible(visible)

    @property
    @on_main_thread
    def z_log_scale(self) -> bool:
        return self._impl.z_log_scale()

    @z_log_scale.setter
    @on_main_thread
    def z_log_scale(self, v: bool):
        self._impl.set_z_log_scale(v)

    @property
    @on_main_thread
    def gradient(self):
        return self._impl.gradient()

    @gradient.setter
    @on_main_thread
    def gradient(self, g):
        self._impl.set_gradient(g)

    def _repr_pretty_(self, p, cycle):
        if cycle:
            p.text("Histogram2D(...)")
        else:
            p.text(f"Histogram2D({self._impl})")
```

- [ ] **Step 3: Update `to_plottable` to disambiguate**

Replace the existing `to_plottable` function in `SciQLop/user_api/plot/_graphs.py` (currently at lines 109–115) with:

```python
def to_plottable(impl) -> Optional[Plottable]:
    if impl is None:
        return None
    if isinstance(impl, _SciQLopHistogram2D):
        return Histogram2D(impl)
    if hasattr(impl, "gradient"):
        return ColorMap(impl)
    return Graph(impl)
```

- [ ] **Step 4: Update `__all__`**

In the same file, change the `__all__` line to:

```python
__all__ = ['Graph', 'ColorMap', 'Histogram2D']
```

- [ ] **Step 5: Smoke test**

Run: `uv run python -c "from SciQLop.user_api.plot._graphs import Histogram2D; print(Histogram2D)"`
Expected: `<class 'SciQLop.user_api.plot._graphs.Histogram2D'>`

- [ ] **Step 6: Commit**

```bash
git add SciQLop/user_api/plot/_graphs.py
git commit -m "feat(user_api): add Histogram2D plottable + route in to_plottable"
```

---

## Task 6: Add `histogram2d()` to `PlotPanel`

**Files:**
- Modify: `SciQLop/user_api/plot/_panel.py`

- [ ] **Step 1: Add `histogram2d` method**

In `SciQLop/user_api/plot/_panel.py`, add a method to the `PlotPanel` class. Place it after `plot_function` (around line 188, before the `plot()` dispatch method):

First, add this import near the existing graphs import (around line 18):

```python
from ._graphs import ensure_arrays_of_double, Histogram2D
```

Then add the method to `PlotPanel`:

```python
    @experimental_api()
    @on_main_thread
    def histogram2d(self, x, y, *, name: str = "histogram",
                    key_bins: int = 100, value_bins: int = 100,
                    z_log_scale: bool = False, plot_index: int = -1) -> Tuple[XYPlot, Histogram2D]:
        """Add a 2D density histogram in a new XY plot.

        Bins (x, y) into a key_bins x value_bins grid asynchronously.

        Parameters
        ----------
        x, y : array-like
            Scatter data to bin.
        name : str
            Histogram label (shown in legend).
        key_bins : int
            Number of bins along the X axis.
        value_bins : int
            Number of bins along the Y axis.
        z_log_scale : bool
            Use a logarithmic color scale.
        plot_index : int
            Index in the panel where the new plot is created. -1 = append.

        Returns
        -------
        Tuple[XYPlot, Histogram2D]
            The newly created plot and the histogram plottable.

        Notes
        -----
        Callable / function-source variant pending upstream support in
        ``SciQLopPlot::add_histogram2d(GetDataPyCallable, ...)``.
        """
        impl = self._get_impl_or_raise()
        plot_impl = impl.create_plot(plot_index, _PlotType.BasicXY)
        hist_impl = plot_impl.add_histogram2d(name, key_bins, value_bins)
        if z_log_scale:
            hist_impl.set_z_log_scale(True)
        x_arr, y_arr = ensure_arrays_of_double(x, y)
        hist_impl.set_data(x_arr, y_arr)
        return XYPlot(plot_impl), Histogram2D(hist_impl)
```

(`experimental_api` and `Tuple` are already imported in `_panel.py` — see lines 4 and 6 — no new imports required at the top of the file.)

- [ ] **Step 2: Smoke test the wiring**

Run:
```bash
uv run python -c "
from SciQLop.user_api.plot import PlotPanel
print('histogram2d method exists:', hasattr(PlotPanel, 'histogram2d'))
"
```
Expected: `histogram2d method exists: True`

- [ ] **Step 3: Commit**

```bash
git add SciQLop/user_api/plot/_panel.py
git commit -m "feat(user_api): add PlotPanel.histogram2d() method"
```

---

## Task 7: Add `histogram2d()` to `XYPlot` and `TimeSeriesPlot`

**Files:**
- Modify: `SciQLop/user_api/plot/_plots.py`

- [ ] **Step 1: Add `Histogram2D` import**

In `SciQLop/user_api/plot/_plots.py`, modify the existing `_graphs` import (around line 3) to add `Histogram2D`:

```python
from ._graphs import Graph, ColorMap, Histogram2D, to_plottable, ensure_arrays_of_double
```

Add the experimental decorator import near the top (after the existing imports):

```python
from .._annotations import experimental_api
```

- [ ] **Step 2: Add `histogram2d` method to `XYPlot`**

In the `XYPlot` class in `_plots.py` (currently around lines 94–185), add this method after `plot()` and before `set_x_range`:

```python
    @experimental_api()
    @on_main_thread
    def histogram2d(self, x, y, *, name: str = "histogram",
                    key_bins: int = 100, value_bins: int = 100,
                    z_log_scale: bool = False) -> Histogram2D:
        """Add a 2D density histogram to this plot.

        Parameters
        ----------
        x, y : array-like
            Scatter data to bin.
        name : str
            Histogram label.
        key_bins, value_bins : int
            Bin counts along X and Y.
        z_log_scale : bool
            Use a logarithmic color scale.

        Returns
        -------
        Histogram2D
            The histogram plottable.
        """
        impl = self._get_impl_or_raise()
        hist_impl = impl.add_histogram2d(name, key_bins, value_bins)
        if z_log_scale:
            hist_impl.set_z_log_scale(True)
        x_arr, y_arr = ensure_arrays_of_double(x, y)
        hist_impl.set_data(x_arr, y_arr)
        return Histogram2D(hist_impl)
```

- [ ] **Step 3: Add the same method to `TimeSeriesPlot`**

In the `TimeSeriesPlot` class, add the identical method after `plot()`:

```python
    @experimental_api()
    @on_main_thread
    def histogram2d(self, x, y, *, name: str = "histogram",
                    key_bins: int = 100, value_bins: int = 100,
                    z_log_scale: bool = False) -> Histogram2D:
        """Add a 2D density histogram to this plot. See XYPlot.histogram2d."""
        impl = self._get_impl_or_raise()
        hist_impl = impl.add_histogram2d(name, key_bins, value_bins)
        if z_log_scale:
            hist_impl.set_z_log_scale(True)
        x_arr, y_arr = ensure_arrays_of_double(x, y)
        hist_impl.set_data(x_arr, y_arr)
        return Histogram2D(hist_impl)
```

- [ ] **Step 4: Re-export `Histogram2D` from the plot package**

In `SciQLop/user_api/plot/__init__.py` add `Histogram2D` to the exports. Update the imports/__all__ to include:

```python
from ._graphs import Histogram2D
```

(at the appropriate position) and add `'Histogram2D'` to `__all__`.

- [ ] **Step 5: Smoke test**

Run:
```bash
uv run python -c "
from SciQLop.user_api.plot import Histogram2D, XYPlot, TimeSeriesPlot
assert hasattr(XYPlot, 'histogram2d')
assert hasattr(TimeSeriesPlot, 'histogram2d')
print('OK', Histogram2D)
"
```
Expected: ends with `OK <class ...>`.

- [ ] **Step 6: Commit**

```bash
git add SciQLop/user_api/plot/_plots.py SciQLop/user_api/plot/__init__.py
git commit -m "feat(user_api): add histogram2d() on XYPlot and TimeSeriesPlot, export Histogram2D"
```

---

## Task 8: Tests for Histogram2D

**Files:**
- Create: `tests/test_histogram2d.py`

- [ ] **Step 1: Write the test file**

Create `tests/test_histogram2d.py`:

```python
"""Tests for Histogram2D plottable and panel/plot histogram2d() methods."""
import numpy as np
import pytest

from SciQLop.user_api.plot import Histogram2D, XYPlot


def _scatter(n: int = 5000, seed: int = 0):
    rng = np.random.default_rng(seed)
    x = rng.normal(0.0, 1.0, n)
    y = rng.normal(0.0, 1.0, n)
    return x, y


class TestPanelHistogram2D:
    def test_creates_xy_plot_and_histogram(self, plot_panel):
        x, y = _scatter()
        plot, hist = plot_panel.histogram2d(x, y, name="density",
                                            key_bins=64, value_bins=32)
        assert isinstance(plot, XYPlot)
        assert isinstance(hist, Histogram2D)

    def test_z_log_scale_round_trip(self, plot_panel):
        x, y = _scatter()
        _plot, hist = plot_panel.histogram2d(x, y, z_log_scale=True)
        assert hist.z_log_scale is True
        hist.z_log_scale = False
        assert hist.z_log_scale is False

    def test_visible_round_trip(self, plot_panel):
        x, y = _scatter()
        _plot, hist = plot_panel.histogram2d(x, y)
        assert hist.visible is True
        hist.visible = False
        assert hist.visible is False

    def test_set_data_replaces_arrays(self, plot_panel):
        x, y = _scatter(1000, seed=1)
        _plot, hist = plot_panel.histogram2d(x, y)
        x2, y2 = _scatter(2000, seed=2)
        hist.set_data(x2, y2)
        # No exception means success; data() returns binned grid.

    def test_gradient_accessor(self, plot_panel):
        x, y = _scatter()
        _plot, hist = plot_panel.histogram2d(x, y)
        g = hist.gradient
        assert g is not None


class TestXYPlotHistogram2D:
    def test_adds_histogram_to_existing_plot(self, plot_panel):
        x, y = _scatter()
        plot, _h1 = plot_panel.histogram2d(x, y, name="h1")
        h2 = plot.histogram2d(x, y, name="h2", key_bins=20, value_bins=20)
        assert isinstance(h2, Histogram2D)
```

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/test_histogram2d.py -v`
Expected: all tests pass. The visible-toggle test is checking initial true → false after setting; if the underlying impl reports visible False initially, adjust the assertion (do NOT skip the test).

- [ ] **Step 3: Commit**

```bash
git add tests/test_histogram2d.py
git commit -m "test(user_api): cover Histogram2D plottable and histogram2d() methods"
```

---

# Phase 3 — DSP arrays layer (Tasks 9–12)

## Task 9: Create `dsp/_arrays.py` (typed pass-through)

**Files:**
- Create: `SciQLop/user_api/dsp/__init__.py` (empty placeholder, full content in Task 14)
- Create: `SciQLop/user_api/dsp/_arrays.py`

- [ ] **Step 1: Create the package directory marker**

Create `SciQLop/user_api/dsp/__init__.py` with placeholder content (will be filled in Task 14):

```python
"""SciQLop DSP user API. Two-layer facade over SciQLopPlots.dsp.

Layer 1 (this package's public surface): SpeasyVariable-aware wrappers.
Layer 2 (_arrays.py): thin numpy pass-through.

All public functions are marked @experimental_api().
"""
from . import _arrays as arrays  # noqa: F401  (re-exported below in Task 14)
```

- [ ] **Step 2: Create the arrays layer**

Create `SciQLop/user_api/dsp/_arrays.py`:

```python
"""Thin typed pass-through layer over SciQLopPlots.dsp.

This module is internal — public users should import from
``SciQLop.user_api.dsp`` (the SpeasyVariable-aware facade in __init__.py).
Functions here accept and return numpy arrays only.
"""
from __future__ import annotations
from typing import Tuple, List

import numpy as np

from SciQLopPlots import dsp as _dsp

__all__ = [
    'fft', 'filtfilt', 'sosfiltfilt', 'fir_filter', 'iir_sos',
    'resample', 'interpolate_nan', 'rolling_mean', 'rolling_std',
    'spectrogram', 'reduce', 'reduce_axes', 'split_segments',
]


def fft(x: np.ndarray, y: np.ndarray, *,
        gap_factor: float = 3.0, window: str = 'hann') -> List[Tuple[np.ndarray, np.ndarray]]:
    """Per-segment FFT. See ``SciQLopPlots.dsp.fft``.

    Returns
    -------
    list of (freqs, magnitude) per segment.
    """
    return _dsp.fft(x, y, gap_factor=gap_factor, window=window)


def filtfilt(x: np.ndarray, y: np.ndarray, coeffs: np.ndarray, *,
             gap_factor: float = 3.0, has_gaps: bool = True) -> Tuple[np.ndarray, np.ndarray]:
    """Zero-phase FIR filter (forward-backward). Equivalent to scipy.signal.filtfilt."""
    return _dsp.filtfilt(x, y, coeffs, gap_factor=gap_factor, has_gaps=has_gaps)


def sosfiltfilt(x: np.ndarray, y: np.ndarray, sos: np.ndarray, *,
                gap_factor: float = 3.0, has_gaps: bool = True) -> Tuple[np.ndarray, np.ndarray]:
    """Zero-phase IIR filter (forward-backward SOS). Equivalent to scipy.signal.sosfiltfilt."""
    return _dsp.sosfiltfilt(x, y, sos, gap_factor=gap_factor, has_gaps=has_gaps)


def fir_filter(x: np.ndarray, y: np.ndarray, coeffs: np.ndarray, *,
               gap_factor: float = 3.0) -> Tuple[np.ndarray, np.ndarray]:
    """FIR filter per segment."""
    return _dsp.fir_filter(x, y, coeffs, gap_factor=gap_factor)


def iir_sos(x: np.ndarray, y: np.ndarray, sos: np.ndarray, *,
            gap_factor: float = 3.0) -> Tuple[np.ndarray, np.ndarray]:
    """IIR filter per segment. ``sos`` is an (n_sections, 6) SOS matrix."""
    return _dsp.iir_sos(x, y, sos, gap_factor=gap_factor)


def resample(x: np.ndarray, y: np.ndarray, *,
             gap_factor: float = 3.0, target_dt: float = 0.0) -> Tuple[np.ndarray, np.ndarray]:
    """Resample to uniform grid per segment."""
    return _dsp.resample(x, y, gap_factor=gap_factor, target_dt=target_dt)


def interpolate_nan(x: np.ndarray, y: np.ndarray, *,
                    max_consecutive: int = 1) -> np.ndarray:
    """Linearly interpolate isolated NaN runs (up to ``max_consecutive``).

    Returns the interpolated y only; the time axis x is unchanged.
    """
    return _dsp.interpolate_nan(x, y, max_consecutive=max_consecutive)


def rolling_mean(x: np.ndarray, y: np.ndarray, window: int, *,
                 gap_factor: float = 3.0) -> Tuple[np.ndarray, np.ndarray]:
    """Gap-aware rolling mean."""
    return _dsp.rolling_mean(x, y, window, gap_factor=gap_factor)


def rolling_std(x: np.ndarray, y: np.ndarray, window: int, *,
                gap_factor: float = 3.0) -> Tuple[np.ndarray, np.ndarray]:
    """Gap-aware rolling standard deviation."""
    return _dsp.rolling_std(x, y, window, gap_factor=gap_factor)


def spectrogram(x: np.ndarray, y: np.ndarray, *,
                col: int = 0, window_size: int = 256, overlap: int = 0,
                gap_factor: float = 3.0, window: str = 'hann') -> List[Tuple[np.ndarray, np.ndarray, np.ndarray]]:
    """Per-segment spectrogram. Returns a list of ``(t, f, power)`` per segment."""
    return _dsp.spectrogram(x, y, col=col, window_size=window_size, overlap=overlap,
                            gap_factor=gap_factor, window=window)


def reduce(x: np.ndarray, y: np.ndarray, op: str, *,
           gap_factor: float = 3.0) -> Tuple[np.ndarray, np.ndarray]:
    """Reduce columns of y to 1. ``op`` selects the reduction (e.g. 'sum', 'mean', 'norm')."""
    return _dsp.reduce(x, y, op, gap_factor=gap_factor)


def reduce_axes(x: np.ndarray, y: np.ndarray, shape: Tuple[int, ...], axes: Tuple[int, ...], *,
                op: str = 'sum', has_gaps: bool = False) -> Tuple[np.ndarray, np.ndarray]:
    """Reduce arbitrary axes of an n-dim row layout. ``shape`` decomposes ``n_cols``; ``axes`` selects axes to reduce."""
    return _dsp.reduce_axes(x, y, shape, axes, op=op, has_gaps=has_gaps)


def split_segments(x: np.ndarray, y: np.ndarray, *,
                   gap_factor: float = 3.0) -> List[Tuple[int, int]]:
    """Detect gaps and return ``[(start, end), ...]`` index ranges (half-open)."""
    return _dsp.split_segments(x, y, gap_factor=gap_factor)
```

- [ ] **Step 3: Smoke test the import**

Run: `uv run python -c "from SciQLop.user_api.dsp import _arrays; print(_arrays.__all__)"`
Expected: list of 13 function names.

- [ ] **Step 4: Commit**

```bash
git add SciQLop/user_api/dsp/__init__.py SciQLop/user_api/dsp/_arrays.py
git commit -m "feat(user_api): add dsp._arrays typed pass-through layer"
```

---

## Task 10: Wire `SciQLop.user_api.dsp` export

**Files:**
- Modify: `SciQLop/user_api/__init__.py`

- [ ] **Step 1: Add the dsp re-export**

Replace `SciQLop/user_api/__init__.py` with:

```python
"""SciQLop user API package. This package provides the public API for SciQLop users to interact with the application.
While SciQLop internal API is subject to change, the user API is meant to be stable and should not change without notice.
All functions and classes are simplified Facades to the internal API, and are designed to be easy to use and understand.
"""

from SciQLop.core import TimeRange
from . import dsp

__all__ = ["TimeRange", "dsp"]
```

- [ ] **Step 2: Smoke test**

Run:
```bash
uv run python -c "
from SciQLop.user_api import dsp
import numpy as np
x = np.arange(100, dtype=np.float64)
y = np.sin(x).astype(np.float64)
seg = dsp.arrays.split_segments(x, y)
print('segments:', seg)
"
```
Expected: prints `segments: [(0, 100)]` (or similar single-segment ranges).

- [ ] **Step 3: Commit**

```bash
git add SciQLop/user_api/__init__.py
git commit -m "feat(user_api): expose dsp module from user_api root"
```

---

## Task 11: Tests for `dsp._arrays`

**Files:**
- Create: `tests/test_dsp_arrays.py`

- [ ] **Step 1: Write the test file**

Create `tests/test_dsp_arrays.py`:

```python
"""Tests for the dsp arrays layer (numpy pass-through to SciQLopPlots.dsp)."""
import numpy as np
import pytest

from SciQLop.user_api.dsp import _arrays as dsp


@pytest.fixture
def synthetic_signal():
    """A 1000-sample signal: 1 Hz sine + DC, sampled at 100 Hz."""
    t = np.arange(0, 10, 0.01, dtype=np.float64)
    y = (np.sin(2 * np.pi * 1.0 * t) + 0.5).astype(np.float64)
    return t, y


@pytest.fixture
def signal_with_gap():
    t1 = np.arange(0, 5, 0.01, dtype=np.float64)
    t2 = np.arange(10, 15, 0.01, dtype=np.float64)  # 5s gap
    t = np.concatenate([t1, t2])
    y = np.sin(2 * np.pi * 1.0 * t).astype(np.float64)
    return t, y


class TestPassthrough:
    def test_split_segments_no_gap(self, synthetic_signal):
        t, y = synthetic_signal
        segs = dsp.split_segments(t, y)
        assert len(segs) == 1
        assert segs[0] == (0, len(t))

    def test_split_segments_with_gap(self, signal_with_gap):
        t, y = signal_with_gap
        segs = dsp.split_segments(t, y)
        assert len(segs) == 2

    def test_interpolate_nan_returns_y_only(self, synthetic_signal):
        t, y = synthetic_signal
        y_with_nan = y.copy()
        y_with_nan[100] = np.nan
        out = dsp.interpolate_nan(t, y_with_nan, max_consecutive=2)
        assert isinstance(out, np.ndarray)
        assert out.shape == y.shape
        assert not np.isnan(out[100])

    def test_filtfilt_returns_xy_pair(self, synthetic_signal):
        t, y = synthetic_signal
        coeffs = np.array([0.25, 0.5, 0.25], dtype=np.float64)
        x_out, y_out = dsp.filtfilt(t, y, coeffs)
        assert x_out.shape == t.shape
        assert y_out.shape == y.shape

    def test_rolling_mean_returns_xy_pair(self, synthetic_signal):
        t, y = synthetic_signal
        x_out, y_out = dsp.rolling_mean(t, y, window=5)
        assert x_out.shape[0] == y_out.shape[0]

    def test_resample_target_dt(self, synthetic_signal):
        t, y = synthetic_signal
        x_out, y_out = dsp.resample(t, y, target_dt=0.02)
        assert x_out.shape[0] == y_out.shape[0]
        # ~half the samples since dt doubled
        assert 400 <= x_out.shape[0] <= 600

    def test_fft_returns_list_of_segments(self, synthetic_signal):
        t, y = synthetic_signal
        result = dsp.fft(t, y)
        assert isinstance(result, list)
        assert len(result) >= 1
        freqs, mag = result[0]
        assert freqs.dtype == np.float64
        assert mag.shape[0] == freqs.shape[0]

    def test_spectrogram_returns_list_of_triples(self, synthetic_signal):
        t, y = synthetic_signal
        result = dsp.spectrogram(t, y, window_size=128, overlap=64)
        assert isinstance(result, list)
        assert len(result) >= 1
        st, sf, sp = result[0]
        assert sp.shape == (sf.shape[0], st.shape[0]) or sp.shape == (st.shape[0], sf.shape[0])

    def test_reduce_norm(self, synthetic_signal):
        t, y = synthetic_signal
        y2 = np.column_stack([y, y, y]).astype(np.float64)
        x_out, y_out = dsp.reduce(t, y2, 'norm')
        assert y_out.ndim == 1
        assert y_out.shape[0] == y.shape[0]
```

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/test_dsp_arrays.py -v`
Expected: all tests pass. If `dsp.spectrogram` returns power with a different axis order than the assertion checks, the test already accepts both orientations.

- [ ] **Step 3: Commit**

```bash
git add tests/test_dsp_arrays.py
git commit -m "test(user_api): cover dsp._arrays pass-through layer"
```

---

## Task 12: Smoke-test the public DSP namespace

**Files:** (no source changes — this is a verification task to confirm Phase 3 lands cleanly before Phase 4)

- [ ] **Step 1: Run the existing test suite to confirm no regressions**

Run: `uv run pytest tests/test_dsp_arrays.py tests/test_overlay.py tests/test_histogram2d.py -v`
Expected: all green.

- [ ] **Step 2: Confirm dsp namespace is reachable from `SciQLop.user_api`**

Run: `uv run python -c "from SciQLop.user_api import dsp; print(dir(dsp))"`
Expected: includes `arrays` (the `_arrays` module re-exported as `arrays`).

(No commit needed for this checkpoint task.)

---

# Phase 4 — DSP SpeasyVariable facade (Tasks 13–16)

## Task 13: Create `dsp/_speasy.py` helpers

**Files:**
- Create: `SciQLop/user_api/dsp/_speasy.py`

- [ ] **Step 1: Write the helpers file**

Create `SciQLop/user_api/dsp/_speasy.py`:

```python
"""Helpers to round-trip between SpeasyVariable and (x, y) numpy arrays.

These helpers are internal to ``SciQLop.user_api.dsp``.
"""
from __future__ import annotations
from typing import Optional, Tuple, List

import numpy as np

from speasy.products import SpeasyVariable, VariableTimeAxis, VariableAxis
from speasy.core import datetime64_to_epoch, epoch_to_datetime64
from speasy.core.data_containers import DataContainer


def unwrap(v: SpeasyVariable) -> Tuple[np.ndarray, np.ndarray]:
    """Extract (epoch_seconds, values) from a SpeasyVariable as float64 numpy arrays."""
    return datetime64_to_epoch(v.time), np.asarray(v.values)


def rewrap_time_series(template: SpeasyVariable, values: np.ndarray, *,
                       time_epoch: Optional[np.ndarray] = None,
                       name_suffix: str = "") -> SpeasyVariable:
    """Build a new SpeasyVariable preserving template's metadata and unit.

    Parameters
    ----------
    template : SpeasyVariable
        Source variable used for axis/metadata templating.
    values : np.ndarray
        New value array (shape may differ when resampling/filtering).
    time_epoch : np.ndarray or None
        New time axis as float64 epoch seconds. If None, the template's
        time axis is kept.
    name_suffix : str
        Appended to the template's name (e.g. ``"_filtfilt"``).
    """
    time = template.time if time_epoch is None else epoch_to_datetime64(time_epoch)
    time_axis = VariableTimeAxis(values=time)
    other_axes = list(template.axes[1:])
    data = DataContainer(values=values, meta=dict(template.meta),
                         name=template.name + name_suffix)
    return SpeasyVariable(
        axes=[time_axis] + other_axes,
        values=data,
        columns=template.columns,
    )


def rewrap_spectrogram(template: SpeasyVariable,
                       t: np.ndarray, f: np.ndarray, power: np.ndarray, *,
                       name_suffix: str = "_spectrogram",
                       power_units: str = "") -> SpeasyVariable:
    """Wrap a spectrogram segment as a 2D SpeasyVariable (time x frequency).

    Power may be returned as ``(n_freq, n_time)`` and is transposed so the
    first axis is time. When ``n_freq == n_time`` the orientation is
    ambiguous; callers must ensure power is already ``(n_time, n_freq)``
    in that case.

    ``power_units`` overrides the unit of the output values — spectrogram
    power has different units than the input signal (e.g. ``nT^2/Hz``),
    so the template's ``UNITS`` is not propagated.
    """
    time_axis = VariableTimeAxis(values=epoch_to_datetime64(t))
    freq_axis = VariableAxis(name="frequency", meta={"UNITS": "Hz"}, values=f)
    if power.shape[0] == f.shape[0] and power.shape[1] == t.shape[0]:
        power = power.T
    meta = dict(template.meta)
    meta["UNITS"] = power_units
    data = DataContainer(values=power, meta=meta,
                         name=template.name + name_suffix)
    return SpeasyVariable(
        axes=[time_axis, freq_axis],
        values=data,
    )


def slice_segments(v: SpeasyVariable, segs: List[Tuple[int, int]]) -> List[SpeasyVariable]:
    """Slice a SpeasyVariable along its time axis using ``[(start, end), ...]`` index ranges."""
    return [v[start:end] for start, end in segs]
```

- [ ] **Step 2: Smoke test**

Run:
```bash
uv run python -c "
from SciQLop.user_api.dsp._speasy import unwrap, rewrap_time_series
import numpy as np
from speasy.products import SpeasyVariable, VariableTimeAxis
from speasy.core import epoch_to_datetime64
t = epoch_to_datetime64(np.arange(10, dtype=np.float64))
v = SpeasyVariable(axes=[VariableTimeAxis(values=t)], values=np.arange(10, dtype=np.float64), name='test')
xt, yv = unwrap(v)
print('unwrap shapes:', xt.shape, yv.shape)
v2 = rewrap_time_series(v, yv * 2, name_suffix='_x2')
print('rewrap name:', v2.name)
"
```
Expected: prints shapes and `rewrap name: test_x2`.

- [ ] **Step 3: Commit**

```bash
git add SciQLop/user_api/dsp/_speasy.py
git commit -m "feat(user_api): add SpeasyVariable round-trip helpers for dsp"
```

---

## Task 14: Wire SpeasyVariable-aware wrappers in `dsp/__init__.py`

**Files:**
- Modify: `SciQLop/user_api/dsp/__init__.py`

- [ ] **Step 1: Replace the placeholder `__init__.py` with the full facade**

Replace `SciQLop/user_api/dsp/__init__.py` with:

```python
"""SciQLop DSP user API.

Public functions accept either numpy arrays or a SpeasyVariable. When given
a SpeasyVariable, the result is rewrapped as a new SpeasyVariable preserving
metadata; for arrays, the result mirrors ``SciQLopPlots.dsp``.

Functions whose semantics change the time axis (``fft``, ``spectrogram``,
``resample``) document their rewrap behavior in the per-function docstring.

All public functions are marked @experimental_api().
"""
from __future__ import annotations
from typing import Tuple, List, Union

import numpy as np
from speasy.products import SpeasyVariable

from .._annotations import experimental_api
from . import _arrays as arrays
from . import _speasy as _sp


__all__ = [
    'arrays',
    'fft', 'filtfilt', 'sosfiltfilt', 'fir_filter', 'iir_sos',
    'resample', 'interpolate_nan', 'rolling_mean', 'rolling_std',
    'spectrogram', 'reduce', 'reduce_axes', 'split_segments',
]


def _is_var(o) -> bool:
    return isinstance(o, SpeasyVariable)


# --- Same-axis transforms (filtfilt, sosfiltfilt, fir_filter, iir_sos,
#     interpolate_nan, rolling_mean, rolling_std)
#     Rewrap with template metadata + name suffix.

@experimental_api()
def filtfilt(data, coeffs: np.ndarray, *, gap_factor: float = 3.0, has_gaps: bool = True):
    """Zero-phase FIR filter (forward-backward). Equivalent to scipy.signal.filtfilt.

    Accepts a SpeasyVariable (returns a new SpeasyVariable suffixed ``_filtfilt``).
    For raw arrays, use ``SciQLop.user_api.dsp.arrays.filtfilt(x, y, coeffs, ...)``.
    """
    if _is_var(data):
        x, y = _sp.unwrap(data)
        x_out, y_out = arrays.filtfilt(x, y, coeffs, gap_factor=gap_factor, has_gaps=has_gaps)
        return _sp.rewrap_time_series(data, y_out, time_epoch=x_out, name_suffix='_filtfilt')
    raise TypeError("filtfilt(data, coeffs, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.filtfilt(x, y, coeffs) for arrays.")


@experimental_api()
def sosfiltfilt(data, sos: np.ndarray, *, gap_factor: float = 3.0, has_gaps: bool = True):
    """Zero-phase IIR (SOS) filter. Equivalent to scipy.signal.sosfiltfilt."""
    if _is_var(data):
        x, y = _sp.unwrap(data)
        x_out, y_out = arrays.sosfiltfilt(x, y, sos, gap_factor=gap_factor, has_gaps=has_gaps)
        return _sp.rewrap_time_series(data, y_out, time_epoch=x_out, name_suffix='_sosfiltfilt')
    raise TypeError("sosfiltfilt(data, sos, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.sosfiltfilt(x, y, sos) for arrays.")


@experimental_api()
def fir_filter(data, coeffs: np.ndarray, *, gap_factor: float = 3.0):
    """FIR filter per segment."""
    if _is_var(data):
        x, y = _sp.unwrap(data)
        x_out, y_out = arrays.fir_filter(x, y, coeffs, gap_factor=gap_factor)
        return _sp.rewrap_time_series(data, y_out, time_epoch=x_out, name_suffix='_fir')
    raise TypeError("fir_filter(data, coeffs, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.fir_filter(x, y, coeffs) for arrays.")


@experimental_api()
def iir_sos(data, sos: np.ndarray, *, gap_factor: float = 3.0):
    """IIR (SOS) filter per segment."""
    if _is_var(data):
        x, y = _sp.unwrap(data)
        x_out, y_out = arrays.iir_sos(x, y, sos, gap_factor=gap_factor)
        return _sp.rewrap_time_series(data, y_out, time_epoch=x_out, name_suffix='_iir')
    raise TypeError("iir_sos(data, sos, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.iir_sos(x, y, sos) for arrays.")


@experimental_api()
def interpolate_nan(data, *, max_consecutive: int = 1):
    """Linearly interpolate NaN runs of length up to ``max_consecutive``."""
    if _is_var(data):
        x, y = _sp.unwrap(data)
        y_out = arrays.interpolate_nan(x, y, max_consecutive=max_consecutive)
        return _sp.rewrap_time_series(data, y_out, name_suffix='_interp_nan')
    raise TypeError("interpolate_nan(data, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.interpolate_nan(x, y, ...) for arrays.")


@experimental_api()
def rolling_mean(data, window: int, *, gap_factor: float = 3.0):
    """Gap-aware rolling mean."""
    if _is_var(data):
        x, y = _sp.unwrap(data)
        x_out, y_out = arrays.rolling_mean(x, y, window, gap_factor=gap_factor)
        return _sp.rewrap_time_series(data, y_out, time_epoch=x_out, name_suffix='_rmean')
    raise TypeError("rolling_mean(data, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.rolling_mean(x, y, w) for arrays.")


@experimental_api()
def rolling_std(data, window: int, *, gap_factor: float = 3.0):
    """Gap-aware rolling standard deviation."""
    if _is_var(data):
        x, y = _sp.unwrap(data)
        x_out, y_out = arrays.rolling_std(x, y, window, gap_factor=gap_factor)
        return _sp.rewrap_time_series(data, y_out, time_epoch=x_out, name_suffix='_rstd')
    raise TypeError("rolling_std(data, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.rolling_std(x, y, w) for arrays.")


# --- New-axis transforms (resample, fft, spectrogram, split_segments)

@experimental_api()
def resample(data, *, target_dt: float = 0.0, gap_factor: float = 3.0):
    """Resample to a uniform grid with sample spacing ``target_dt`` (seconds)."""
    if _is_var(data):
        x, y = _sp.unwrap(data)
        x_out, y_out = arrays.resample(x, y, gap_factor=gap_factor, target_dt=target_dt)
        return _sp.rewrap_time_series(data, y_out, time_epoch=x_out, name_suffix='_resample')
    raise TypeError("resample(data, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.resample(x, y) for arrays.")


@experimental_api()
def fft(data, *, gap_factor: float = 3.0, window: str = 'hann') -> List[Tuple[np.ndarray, np.ndarray]]:
    """Per-segment FFT.

    Returns
    -------
    list of (freqs, magnitude)
        One per detected segment. ``SpeasyVariable`` cannot represent a
        frequency-only sample (its first axis must be time), so the FFT
        path returns raw numpy tuples even for SpeasyVariable inputs.
        Use ``spectrogram`` if you need a time-resolved spectrum wrapped
        as a ``SpeasyVariable``.
    """
    if _is_var(data):
        x, y = _sp.unwrap(data)
        return arrays.fft(x, y, gap_factor=gap_factor, window=window)
    raise TypeError("fft(data, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.fft(x, y) for arrays.")


@experimental_api()
def spectrogram(data, *, col: int = 0, window_size: int = 256, overlap: int = 0,
                gap_factor: float = 3.0, window: str = 'hann') -> List[SpeasyVariable]:
    """Per-segment spectrogram.

    Returns
    -------
    list of SpeasyVariable
        One per detected segment, each 2D (time x frequency). Suitable as
        input to ColorMap / Histogram2D plot wrappers.
    """
    if _is_var(data):
        x, y = _sp.unwrap(data)
        segs = arrays.spectrogram(x, y, col=col, window_size=window_size,
                                  overlap=overlap, gap_factor=gap_factor, window=window)
        return [_sp.rewrap_spectrogram(data, t, f, p) for t, f, p in segs]
    raise TypeError("spectrogram(data, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.spectrogram(x, y) for arrays.")


@experimental_api()
def reduce(data, op: str, *, gap_factor: float = 3.0):
    """Reduce columns of multi-column y to 1. ``op`` selects the reduction (e.g. 'sum', 'mean', 'norm')."""
    if _is_var(data):
        x, y = _sp.unwrap(data)
        x_out, y_out = arrays.reduce(x, y, op, gap_factor=gap_factor)
        return _sp.rewrap_time_series(data, y_out, time_epoch=x_out, name_suffix=f'_reduce_{op}')
    raise TypeError("reduce(data, op, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.reduce(x, y, op) for arrays.")


@experimental_api()
def reduce_axes(data, shape: Tuple[int, ...], axes: Tuple[int, ...], *,
                op: str = 'sum', has_gaps: bool = False):
    """Reduce arbitrary axes within each row of a multi-column SpeasyVariable."""
    if _is_var(data):
        x, y = _sp.unwrap(data)
        x_out, y_out = arrays.reduce_axes(x, y, shape, axes, op=op, has_gaps=has_gaps)
        return _sp.rewrap_time_series(data, y_out, time_epoch=x_out, name_suffix=f'_reduce_axes_{op}')
    raise TypeError("reduce_axes(data, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.reduce_axes(x, y, ...) for arrays.")


@experimental_api()
def split_segments(data, *, gap_factor: float = 3.0):
    """Detect gaps and slice the SpeasyVariable into segments.

    For arrays, see ``SciQLop.user_api.dsp.arrays.split_segments`` which returns
    raw ``[(start, end), ...]`` index ranges.
    """
    if _is_var(data):
        x, y = _sp.unwrap(data)
        segs = arrays.split_segments(x, y, gap_factor=gap_factor)
        return _sp.slice_segments(data, segs)
    raise TypeError("split_segments(data, ...) requires a SpeasyVariable; "
                    "use SciQLop.user_api.dsp.arrays.split_segments(x, y) for arrays.")
```

- [ ] **Step 2: Smoke test the public namespace**

Run: `uv run python -c "from SciQLop.user_api.dsp import filtfilt, fft, spectrogram, split_segments, arrays; print('OK')"`
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add SciQLop/user_api/dsp/__init__.py
git commit -m "feat(user_api): add SpeasyVariable-aware dsp facade (13 functions)"
```

---

## Task 15: Tests for the SpeasyVariable facade

**Files:**
- Create: `tests/test_dsp_speasy.py`

- [ ] **Step 1: Write the test file**

Create `tests/test_dsp_speasy.py`:

```python
"""Tests for the SciQLop.user_api.dsp facade with SpeasyVariable inputs."""
from .fixtures import *  # noqa: F401, F403  (qapp + plot fixtures)
import numpy as np
import pytest
from speasy.products import SpeasyVariable, VariableTimeAxis
from speasy.core.data_containers import DataContainer
from speasy.core import epoch_to_datetime64


def _make_var(n: int = 1000, dt: float = 0.01, name: str = "test") -> SpeasyVariable:
    epoch = np.arange(n, dtype=np.float64) * dt
    time = epoch_to_datetime64(epoch)
    values = np.sin(2 * np.pi * 1.0 * epoch).astype(np.float64)
    data = DataContainer(values=values, meta={"UNITS": "nT"}, name=name)
    return SpeasyVariable(axes=[VariableTimeAxis(values=time)], values=data)


@pytest.fixture
def dsp(qapp):
    """Defer SciQLop.user_api import past Qt static-init."""
    from SciQLop.user_api import dsp as _dsp
    return _dsp


@pytest.fixture
def var():
    return _make_var()


@pytest.fixture
def var_with_nan():
    v = _make_var()
    v.values[100, 0] = np.nan
    return v


class TestSameAxisTransforms:
    def test_filtfilt_returns_speasy_variable(self, dsp, var):
        coeffs = np.array([0.25, 0.5, 0.25], dtype=np.float64)
        out = dsp.filtfilt(var, coeffs)
        assert isinstance(out, SpeasyVariable)
        assert out.name.endswith("_filtfilt")
        assert out.values.shape == var.values.shape

    def test_interpolate_nan_returns_var(self, dsp, var_with_nan):
        out = dsp.interpolate_nan(var_with_nan, max_consecutive=2)
        assert isinstance(out, SpeasyVariable)
        assert out.name.endswith("_interp_nan")
        assert not np.isnan(out.values[100, 0])

    def test_rolling_mean_returns_var(self, dsp, var):
        out = dsp.rolling_mean(var, window=5)
        assert isinstance(out, SpeasyVariable)
        assert out.name.endswith("_rmean")

    def test_rolling_std_returns_var(self, dsp, var):
        out = dsp.rolling_std(var, window=5)
        assert isinstance(out, SpeasyVariable)
        assert out.name.endswith("_rstd")


class TestNewAxisTransforms:
    def test_resample_changes_time_axis(self, dsp, var):
        out = dsp.resample(var, target_dt=0.02)
        assert isinstance(out, SpeasyVariable)
        assert out.name.endswith("_resample")
        # Roughly half the samples (dt doubled).
        assert 400 <= out.values.shape[0] <= 600

    def test_fft_returns_list_of_tuples(self, dsp, var):
        # fft() returns raw (freqs, magnitude) tuples — SpeasyVariable
        # cannot represent a frequency-only axis.
        result = dsp.fft(var)
        assert isinstance(result, list)
        assert len(result) >= 1
        freqs, magnitude = result[0]
        assert isinstance(freqs, np.ndarray)
        assert isinstance(magnitude, np.ndarray)
        assert freqs.ndim == 1

    def test_spectrogram_returns_list_of_2d_vars(self, dsp, var):
        result = dsp.spectrogram(var, window_size=128, overlap=64)
        assert isinstance(result, list)
        assert len(result) >= 1
        first = result[0]
        assert isinstance(first, SpeasyVariable)
        assert first.name.endswith("_spectrogram")
        assert first.values.ndim == 2
        assert first.axes[1].unit == "Hz"

    def test_split_segments_no_gap(self, dsp, var):
        result = dsp.split_segments(var)
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], SpeasyVariable)


class TestRejectsRawArrays:
    def test_filtfilt_rejects_arrays(self, dsp):
        x = np.arange(10, dtype=np.float64)
        with pytest.raises(TypeError):
            dsp.filtfilt(x, np.array([1.0]))
```

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/test_dsp_speasy.py -v`
Expected: all pass under CI's Xvfb. Local headless execution segfaults (Qt static-init via `SciQLop.core` triggered through the `dsp(qapp)` fixture); the test file deliberately defers the SciQLop import behind `qapp` for that reason. Static collection should succeed locally — verify with `uv run pytest tests/test_dsp_speasy.py --collect-only -q`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_dsp_speasy.py
git commit -m "test(user_api): cover SpeasyVariable-aware dsp facade"
```

---

## Task 16: Final integration check

**Files:** (no source changes)

- [ ] **Step 1: Run the full new-test suite**

Run: `uv run pytest tests/test_overlay.py tests/test_histogram2d.py tests/test_dsp_arrays.py tests/test_dsp_speasy.py -v`
Expected: all green.

- [ ] **Step 2: Run a focused regression on existing plot tests**

Run: `uv run pytest tests/ -k "plot or panel or graph" -v`
Expected: all green. Any failure here indicates the `to_plottable` change in Task 5 misrouted an existing plot.

- [ ] **Step 3: Sanity-check the public surface**

Run:
```bash
uv run python -c "
from SciQLop.user_api.plot import (XYPlot, TimeSeriesPlot, ProjectionPlot, PlotPanel,
                                   Histogram2D, Overlay,
                                   OverlayLevel, OverlaySizeMode, OverlayPosition)
from SciQLop.user_api import dsp
expected_dsp = ['fft','filtfilt','sosfiltfilt','fir_filter','iir_sos',
                'resample','interpolate_nan','rolling_mean','rolling_std',
                'spectrogram','reduce','reduce_axes','split_segments']
missing = [n for n in expected_dsp if not hasattr(dsp, n)]
assert not missing, f'Missing dsp functions: {missing}'
print('Public surface OK.')
"
```
Expected: `Public surface OK.`

(No commit for this checkpoint task.)

---

# Done

All four phases land cleanly: new test files cover the new surface, no regressions in existing plot tests, and the public API matches the spec (with the documented deltas).
