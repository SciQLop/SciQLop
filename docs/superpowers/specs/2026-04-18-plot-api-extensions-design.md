# Plot API Extensions — Design

**Date:** 2026-04-18
**Status:** Approved (pending implementation plan)
**Scope:** Expose three new SciQLopPlots additions through SciQLop's public `user_api`.

## Goals

Expose the following SciQLopPlots additions through `SciQLop.user_api`:

1. **`SciQLopHistogram2D`** — 2D density histogram graph type.
2. **`SciQLopOverlay`** — per-plot in-canvas message overlay.
3. **`SciQLopPlots.dsp`** — server-side DSP module (13 functions).

All new surfaces are marked `@experimental_api()` so the contract can evolve.

## Out of scope

- **Waterfall graph** — exists in NeoQCP but not yet wrapped in SciQLopPlots Python bindings; will be addressed in a separate spec once wrapping lands upstream.
- **Histogram2D callable variant** — `add_histogram2d` currently only has the data-only signature in `SciQLopPlot.hpp:96`. The function/callback overload (analogous to `SciQLopColorMapFunction`) is pending upstream.
- **Theme, legend positioning, span items, span-creation mode** — separate specs.

## Section 1 — Histogram2D

### Files

- `SciQLop/user_api/plot/_graphs.py` — add `Histogram2D(Plottable)` class next to `ColorMap`.
- `SciQLop/user_api/plot/_plots.py` — add `histogram2d()` method to `XYPlot` and `TimeSeriesPlot`.
- `SciQLop/user_api/plot/_panel.py` — add `histogram2d()` method to `PlotPanel`.
- `SciQLop/user_api/plot/__init__.py` — export `Histogram2D`.

### `Histogram2D` class

Mirrors the `ColorMap` shape:

```python
class Histogram2D(Plottable):
    @on_main_thread
    def set_data(self, x, y): ...    # (x, y) scatter to bin

    @property
    def data(self): ...              # (key_axis, value_axis, counts)

    @property
    def visible(self) -> bool: ...
    @visible.setter
    def visible(self, v): ...

    @property
    def z_log_scale(self) -> bool: ...
    @z_log_scale.setter
    def z_log_scale(self, v): ...

    @property
    def gradient(self): ...
    @gradient.setter
    def gradient(self, g): ...
```

### Plot/Panel method

```python
@experimental_api()
@on_main_thread
def histogram2d(self, x, y, *, name="histogram", key_bins=100, value_bins=100,
                z_log_scale=False, plot_index=-1) -> Tuple[XYPlot, Histogram2D]:
    """Add a 2D density histogram. Bins (x, y) into a key_bins × value_bins
    grid asynchronously."""
```

- On `PlotPanel`: creates a new XY plot at `plot_index`, calls `plot.add_histogram2d(name, key_bins, value_bins)`, applies log-Z if requested, calls `set_data(x, y)`, returns `(XYPlot, Histogram2D)`.
- On `XYPlot` / `TimeSeriesPlot`: same but adds to the existing plot, returns just `Histogram2D`.

### Routing in `to_plottable`

Both `Histogram2D` and `ColorMap` impls expose `gradient`, so the existing `hasattr(impl, "gradient")` test in `_graphs.py:112` no longer disambiguates them. New logic:

```python
def to_plottable(impl) -> Optional[Plottable]:
    if impl is None:
        return None
    if isinstance(impl, _SciQLopHistogram2D):   # check histogram FIRST
        return Histogram2D(impl)
    if hasattr(impl, "gradient"):                # falls through to colormap
        return ColorMap(impl)
    return Graph(impl)
```

### Spec note

Callable/function variant is deferred until upstream `add_histogram2d(GetDataPyCallable, ...)` overload lands in SciQLopPlots.

## Section 2 — Overlay

### Files

- `SciQLop/user_api/plot/enums.py` — add `OverlayLevel`, `OverlaySizeMode`, `OverlayPosition` Python enums.
- `SciQLop/user_api/plot/_overlay.py` — new file, `Overlay` wrapper class.
- `SciQLop/user_api/plot/_plots.py` — add `overlay` property on `_BasePlot` (so all three plot types get it).
- `SciQLop/user_api/plot/__init__.py` — export `Overlay`, `OverlayLevel`, `OverlaySizeMode`, `OverlayPosition`.

### Why mirror enums

The C++ `OverlayLevel.Info` / `OverlaySizeMode.Compact` / `OverlayPosition.Top`/`Right` are currently absent from the Python stubs (must be constructed by integer value). Mirroring as Python enums hides this stub gap and gives a stable user-facing API.

### Enums

```python
class OverlayLevel(Enum):
    Info = 0
    Warning = 1
    Error = 2

class OverlaySizeMode(Enum):
    Compact = 0
    FitContent = 1
    FullWidget = 2

class OverlayPosition(Enum):
    Top = 0
    Bottom = 1
    Left = 2
    Right = 3
```

Internal `_to_sqp_*` translators live in `_overlay.py` (same pattern as `_to_sqp_plot_type` in `_panel.py`).

### `Overlay` class

```python
class Overlay:
    def __init__(self, impl):
        self._impl = impl

    @experimental_api()
    @on_main_thread
    def show(self, text: str, *,
             level: OverlayLevel = OverlayLevel.Info,
             size_mode: OverlaySizeMode = OverlaySizeMode.FitContent,
             position: OverlayPosition = OverlayPosition.Top) -> None: ...

    @experimental_api()
    @on_main_thread
    def clear(self) -> None: ...

    @property
    def text(self) -> str: ...
    @property
    def level(self) -> OverlayLevel: ...
    @property
    def position(self) -> OverlayPosition: ...
    @property
    def size_mode(self) -> OverlaySizeMode: ...

    @property
    def collapsible(self) -> bool: ...
    @collapsible.setter
    def collapsible(self, v: bool): ...

    @property
    def collapsed(self) -> bool: ...
    @collapsed.setter
    def collapsed(self, v: bool): ...

    @property
    def opacity(self) -> float: ...
    @opacity.setter
    def opacity(self, v: float): ...
```

### On `_BasePlot`

```python
@property
@on_main_thread
def overlay(self) -> Overlay:
    return Overlay(self._get_impl_or_raise().overlay())
```

A new `Overlay` wrapper is constructed each access — it's a thin handle around the same `SciQLopOverlay*`. Cheap and avoids stale-cache bugs when the underlying overlay is recreated.

### Naming

`show()` / `clear()` rather than `show_message()` / `clear_message()` — the `Overlay` namespace already implies "message".

## Section 3 — DSP Module (two-layer)

### Files

- `SciQLop/user_api/dsp/__init__.py` — public facade with `SpeasyVariable` adapters.
- `SciQLop/user_api/dsp/_arrays.py` — thin pass-through layer over `SciQLopPlots.dsp` with type hints + docstrings.
- `SciQLop/user_api/dsp/_speasy.py` — small helpers: `_unwrap(var)`, `_rewrap(...)`.
- `SciQLop/user_api/__init__.py` — `from SciQLop.user_api import dsp` so `dsp` is reachable as `SciQLop.user_api.dsp`.

### Layer 1 — `_arrays.py`

Thin pass-through layer over `SciQLopPlots.dsp`. Each function: typed signature, docstring (links to `SciQLopPlots.dsp` doc + scipy equivalent where applicable), delegates straight to `_dsp.<fn>`. Internal layer — **not** decorated `@experimental_api()`.

```python
from SciQLopPlots import dsp as _dsp

def filtfilt(x, y, taps, *, has_gaps=True): ...
def sosfiltfilt(x, y, sos, *, has_gaps=True): ...
def fir_filter(...): ...
def iir_sos(...): ...
def fft(x, y) -> tuple[np.ndarray, np.ndarray]: ...
def spectrogram(x, y, *, window, overlap, ...) -> tuple[np.ndarray, np.ndarray, np.ndarray]: ...
def resample(x, y, target_dt) -> tuple[np.ndarray, np.ndarray]: ...
def interpolate_nan(x, y) -> np.ndarray: ...
def rolling_mean(x, y, window) -> np.ndarray: ...
def rolling_std(x, y, window) -> np.ndarray: ...
def reduce(x, y, axis, op) -> np.ndarray: ...
def reduce_axes(x, y, shape, axes, op) -> np.ndarray: ...
def split_segments(x, y, gap_threshold) -> list[tuple[np.ndarray, np.ndarray]]: ...
```

### Layer 2 — `dsp/__init__.py`

Per-function explicit wrappers, all marked `@experimental_api()`. Each accepts `SpeasyVariable | np.ndarray` for the data argument:

| Function | Round-trip semantics |
|---|---|
| `filtfilt`, `sosfiltfilt`, `fir_filter`, `iir_sos`, `interpolate_nan`, `rolling_mean`, `rolling_std` | Same time axis, new values. Rewrap with template metadata, suffix name (e.g. `_filtfilt`). |
| `resample` | New time axis + new values. Rewrap with new time, preserve unit/name. |
| `fft` | Returns `(freq, amplitude)`. Returns a *new* `SpeasyVariable` with `freq` axis (not time) and unit-aware amplitude. Document: "axis 0 becomes frequency". |
| `spectrogram` | Returns `(time, freq, power)`. Rewrap as a 2D `SpeasyVariable` (time × freq) for use with `ColorMap` / `Histogram2D`. |
| `reduce`, `reduce_axes` | Shape changes. Best-effort rewrap; for arrays-only path, unchanged. |
| `split_segments` | Returns `list[SpeasyVariable]` (or `list[(x, y)]` if input was arrays). |

### Helpers (`_speasy.py`)

```python
def _unwrap(v: SpeasyVariable) -> tuple[np.ndarray, np.ndarray]:
    return datetime64_to_epoch(v.time), v.values

def _rewrap(template: SpeasyVariable, values: np.ndarray, *,
            time: np.ndarray | None = None, name_suffix: str = "",
            unit: str | None = None, axes: list | None = None) -> SpeasyVariable:
    """Build a SpeasyVariable preserving template's metadata, with overrides."""
    ...
```

### Out-of-scope nuances (called out here so users aren't surprised)

Sample-rate / window / `nperseg` kwargs that are scipy-specific aren't auto-derived from `SpeasyVariable`. The user must pass them explicitly even when input is a `SpeasyVariable`.

## Section 4 — Testing Strategy

Pattern: follow existing `tests/` conventions — `pytest-qt` + `pytest-xvfb` autoset; helpers in `tests/fixtures.py` and `tests/helpers.py`.

### New test files

**`tests/test_histogram2d.py`**
- Create panel, call `panel.histogram2d(x, y)` → returns `(XYPlot, Histogram2D)`.
- Verify `Histogram2D` has `gradient`, `visible`, `z_log_scale` properties round-trip.
- Verify `set_data` accepts arrays + `SpeasyVariable` (extracted via `_speasy_variable_to_arrays`).
- Sanity: histogram appears in `plot.plottables()`.

**`tests/test_overlay.py`**
- For each of `XYPlot`, `TimeSeriesPlot`, `ProjectionPlot`: `plot.overlay.show("hi", level=Warning)` → `plot.overlay.text == "hi"`, `plot.overlay.level == OverlayLevel.Warning`.
- `clear()` empties the overlay.
- `collapsible` / `collapsed` / `opacity` round-trip.
- Enum translation: each Python enum value maps to the right SciQLopPlots integer.

**`tests/test_dsp.py`** — split into two classes:
- `TestDspArrays` — calls `_arrays.<fn>` with numpy arrays, asserts shape/dtype contracts. Light correctness checks (e.g. `filtfilt` of identity = input within tolerance).
- `TestDspSpeasy` — calls `dsp.<fn>` with a `SpeasyVariable` built by a fixture, asserts:
  - Return type is `SpeasyVariable` (or `list[SpeasyVariable]` for `split_segments`).
  - Time axis preserved (or correctly transformed for `fft` / `resample` / `spectrogram`).
  - Metadata (`unit`, `name`) preserved with documented suffixing.

### Fixture additions (`tests/fixtures.py`)

- `synthetic_speasy_variable(n=1000, dt=1.0)` — small time series for DSP roundtrip tests.
- `synthetic_2d_scatter(n=10000)` — random `(x, y)` for histogram tests.

### Out of scope for tests

Numerical-equivalence testing against scipy — `SciQLopPlots` already has those tests; SciQLop tests just verify shape/wiring.

## Section 5 — File Map (final)

### New files (7)

- `SciQLop/user_api/plot/_overlay.py`
- `SciQLop/user_api/dsp/__init__.py`
- `SciQLop/user_api/dsp/_arrays.py`
- `SciQLop/user_api/dsp/_speasy.py`
- `tests/test_histogram2d.py`
- `tests/test_overlay.py`
- `tests/test_dsp.py`

### Modified files (7)

- `SciQLop/user_api/plot/_graphs.py` — add `Histogram2D` class; update `to_plottable` to detect histograms before colormaps (since both have `gradient`).
- `SciQLop/user_api/plot/_plots.py` — add `overlay` property on `_BasePlot`; add `histogram2d()` on `XYPlot` + `TimeSeriesPlot`.
- `SciQLop/user_api/plot/_panel.py` — add `histogram2d()` on `PlotPanel`.
- `SciQLop/user_api/plot/enums.py` — add `OverlayLevel`, `OverlaySizeMode`, `OverlayPosition`.
- `SciQLop/user_api/plot/__init__.py` — export `Histogram2D`, `Overlay`, three overlay enums.
- `SciQLop/user_api/__init__.py` — `from SciQLop.user_api import dsp`.
- `tests/fixtures.py` — add `synthetic_speasy_variable`, `synthetic_2d_scatter`.

### Build order (bottom-up, each independently testable)

1. **Enums + Overlay** (smallest, no dependencies on others) — write tests, ship.
2. **Histogram2D** (depends only on existing `_graphs.py` + `_plots.py` shape) — tests, ship.
3. **DSP `_arrays.py`** (independent layer, no SciQLop wiring) — tests.
4. **DSP `_speasy.py` + facade** — tests.

Each piece can land separately if desired; PRs stay small.
