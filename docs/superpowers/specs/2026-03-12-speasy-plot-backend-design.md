# SciQLop Backend for Speasy Plot API — Design Spec

## Goal

Register a SciQLop plotting backend into speasy's pluggable plot API so that `variable.plot()` (or `variable.plot['sciqlop'].line()`) renders directly into SciQLop plot panels instead of matplotlib, when running inside SciQLop's embedded Jupyter console.

## Module Structure

```
SciQLop/user_api/plot/_speasy_backend.py   # SciQLopBackend class
SciQLop/components/settings/entries/       # PlotBackendSettings ConfigEntry
```

## Concepts Mapping

| matplotlib | SciQLop | speasy parameter |
|------------|---------|------------------|
| Figure | PlotPanel | — |
| Axes | TimeSeriesPlot | `ax=` |

## Backend Class

`SciQLopBackend` implements speasy's two-method backend contract:

### `.line(x, y, ax=None, labels=None, units=None, xaxis_label=None, yaxis_label=None, *args, **kwargs)`

- Plots each column of `y` as a separate `Graph` on the target plot
- Returns `(TimeSeriesPlot, Graph)` — the plot and the last graph added

### `.colormap(x, y, z, ax=None, logy=True, logz=True, xaxis_label=None, yaxis_label=None, yaxis_units=None, zaxis_label=None, zaxis_units=None, cmap=None, vmin=None, vmax=None, *args, **kwargs)`

- Plots a spectrogram/colormap into the target plot
- Returns `(TimeSeriesPlot, ColorMap)`

### `ax` Parameter Resolution

- `ax=None` → get or create a default panel (module-level "current panel"), add a new plot to it
- `ax=TimeSeriesPlot` → add a graph to that existing plot
- `ax=PlotPanel` → add a new plot to that panel
- Other types → `TypeError`

The "current panel" is tracked as a module-level variable — last panel created or used. No state machine.

## Setting

```python
class PlotBackendSettings(ConfigEntry):
    category: ClassVar[str] = SettingsCategory.General
    subcategory: ClassVar[str] = "Plotting"

    default_speasy_backend: Literal["matplotlib", "sciqlop"] = "matplotlib"
```

Default is `"matplotlib"`. When set to `"sciqlop"`, the backend is also registered as the default (`__backends__[None]`).

The `Literal` type gives a dropdown in the settings UI via the existing delegate system.

## Registration

During the speasy plugin's `load()` at startup:

```python
import speasy.plotting as splt
from SciQLop.user_api.plot._speasy_backend import SciQLopBackend

splt.__backends__["sciqlop"] = SciQLopBackend
if PlotBackendSettings().default_speasy_backend == "sciqlop":
    splt.__backends__[None] = SciQLopBackend
```

No changes to speasy. No entry points. Just dict insertion into speasy's existing `__backends__` registry.

## Usage Examples

```python
import speasy as spz

# Explicit backend selection
data = spz.get_data('amda/imf', "2016-06-02", "2016-06-05")
data.plot['sciqlop'].line()       # renders in SciQLop panel

# If setting is "sciqlop" as default
data.plot.line()                   # renders in SciQLop panel
data.plot['matplotlib'].line()     # still available

# Target specific plot/panel
plot, graph = data.plot['sciqlop'].line(ax=my_panel)
data2.plot['sciqlop'].line(ax=plot)  # add to same plot
```

## Error Handling

- speasy not installed: registration silently skipped
- Invalid `ax` type: `TypeError`
- Multi-column `.line()`: one `Graph` per column on the same plot, returns plot + last graph

## Testing

- Unit test: mock the SciQLop plot API, verify backend calls `panel.plot()` with correct arrays
- Integration test (pytest-qt): create a real panel, call `var.plot['sciqlop'].line()`, verify graph appears

## Scope Boundaries

**Not in this version:**
- `live_update=True` kwarg — future extension to register a virtual product backed by speasy, enabling re-fetch on pan/zoom. Default would be `False`.
- `figure()` / `subplot()` state machine for richer matplotlib parity
- `Dataset.plot()` support (iterating over variables)
- No changes to speasy itself
