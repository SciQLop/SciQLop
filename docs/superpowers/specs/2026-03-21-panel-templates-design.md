# Panel Templates Design Spec

## Goal

Save and load plot panel layouts as JSON/YAML files. Compatible with speasy_proxy preset format. Enables reusable plot configurations across sessions and sharing between users.

## Scope

- Single panel templates (multi-panel dock layouts are out of scope, future extension)
- Products from providers only (virtual products cannot be serialized)
- JSON and YAML support (detected by file extension)
- Bidirectional: create panels from templates AND save existing panels as templates

## Pydantic Models

All models live in `SciQLop/components/plotting/panel_template.py`.

```python
class TimeRangeModel(BaseModel):
    start: str  # ISO 8601 datetime
    stop: str   # ISO 8601 datetime

class ProductModel(BaseModel):
    path: str           # e.g. "speasy//amda//b_gse" or "amda/imf"
    label: str = ""     # optional display label

class AxisModel(BaseModel):
    log: bool = False
    range: tuple[float, float] | None = None  # optional fixed range

class PlotModel(BaseModel):
    """One PlotModel = one subplot (SciQLopPlot) in the panel.
    All products in the same PlotModel share the same Y axis."""
    products: list[ProductModel]
    y_axis: AxisModel = AxisModel()
    log_z: bool = False  # for spectrograms

class IntervalModel(BaseModel):
    start: str   # ISO 8601
    stop: str    # ISO 8601
    color: str = ""  # speasy_proxy format: "rgba(r, g, b, a)" e.g. "rgba(255, 120, 80, 0.12)"
    label: str = ""

class PanelTemplate(BaseModel):
    name: str
    description: str = ""
    version: int = 1
    time_range: TimeRangeModel
    plots: list[PlotModel]
    intervals: list[IntervalModel] = []
```

### speasy_proxy Compatibility

A speasy_proxy preset like:
```json
{
  "name": "ACE IMF",
  "description": "ACE magnetic field",
  "version": 1,
  "time_range": {"start": "2025-01-15T00:00:00Z", "stop": "2025-01-16T00:00:00Z"},
  "plots": [
    {"products": [{"path": "amda/imf"}], "y_axis": {"log": false}}
  ]
}
```

is a valid `PanelTemplate`. No conversion needed — the models are a superset of the speasy_proxy format.

## Product Path Resolution

Templates store product paths as-is (no normalization). At load time, a resolver function converts to SciQLop's internal path format:

- Paths containing `//` are split directly: `"speasy//amda//b_gse"` → `["speasy", "amda", "b_gse"]`
- Paths with single `/` separators are assumed to be speasy products (speasy_proxy convention): `"amda/imf"` → `["speasy", "amda", "imf"]`

This is provider-agnostic — new providers just use `//`-separated paths in templates. The speasy fallback only applies to legacy `/`-separated paths.

```python
def resolve_product_path(path: str) -> list[str]:
    """Convert a template path to a SciQLop product path list."""
    if '//' in path:
        return path.split('//')
    # Legacy speasy_proxy format: "amda/imf" → ["speasy", "amda", "imf"]
    return ['speasy'] + path.split('/')
```

If a resolved path doesn't match any known product, the product is skipped with a warning.

## Product Traceability

SciQLopPlots graph objects (`SQPQCPAbstractPlottableWrapper` and subclasses) are QObjects and support `setProperty`/`property`.

When `plot_product` is called (in `time_sync_panel.py`), store the product path on each graph object returned:

```python
# In plot_product(), after the p.plot() call:
# For scalar/vector/multicomponents: r is (plot, graph) tuple
if isinstance(r, tuple) and len(r) == 2:
    r[1].setProperty("sqp_product_path", "//".join(product_path))
# For spectrograms: r is the graph directly
else:
    r.setProperty("sqp_product_path", "//".join(product_path))
```

When saving a template via `from_panel`, enumerate graphs using `plot.plottables()` on each `SciQLopPlot`:

```python
for plot in panel.plots():
    products = []
    for graph in plot.plottables():
        path = graph.property("sqp_product_path")
        if path:
            products.append(ProductModel(path=path, label=graph.name))
    # ... build PlotModel from products + axis state
```

Graphs without `sqp_product_path` (static data, virtual products, functions) are skipped during save with a log warning.

## File I/O

```python
# On PanelTemplate:

@staticmethod
def from_file(path: str) -> "PanelTemplate":
    """Load from JSON or YAML based on file extension."""

def to_file(self, path: str) -> None:
    """Save as JSON or YAML based on file extension."""

@staticmethod
def from_panel(panel: TimeSyncPanel) -> "PanelTemplate":
    """Capture current panel state as a template.
    Walks panel.plots(), then plot.plottables() for each subplot."""

def create_panel(self, main_window) -> TimeSyncPanel:
    """Create a new panel from this template."""

def apply(self, panel: TimeSyncPanel) -> None:
    """Apply this template to an existing panel.
    Clears current plots and sets time range."""
```

`pyyaml` must be declared as a dependency in `pyproject.toml` (it's present transitively but not explicitly).

## Template Storage

Default location: `~/.local/share/sciqlop/templates/`

Templates are discovered by scanning this directory for `.json` and `.yaml`/`.yml` files. If multiple files share the same stem (e.g. `my_layout.json` and `my_layout.yaml`), the first found wins (JSON checked before YAML).

## User Interfaces

### 1. Jupyter API (`SciQLop/user_api/plot/_panel.py`)

```python
panel.save_template("my_layout.yaml")          # save to default dir
panel.save_template("/custom/path/layout.json") # save to specific path

from SciQLop.user_api import templates
templates.load("my_layout")                     # load from default dir by name
templates.load("/custom/path/layout.yaml")      # load from specific path
templates.list()                                 # list available templates
```

### 2. Panel Context Menu

Right-click on panel → "Save as template..." → dialog with:
- Name field (pre-filled with panel name)
- Description field
- Format toggle (JSON / YAML)
- Save button → writes to default templates dir

### 3. Welcome Page

A "Templates" section with cards showing:
- Template name + description
- Click → creates a new panel from the template
- "Import..." card at the end → file picker for external templates

Uses the same QWebEngineView + QWebChannel + Jinja2 pattern as existing welcome page sections.

## Edge Cases

- **Missing products**: if a resolved product path doesn't match a known product, skip it and log a warning. Don't fail the whole template load.
- **Virtual products**: `graph.property("sqp_product_path")` returns empty/None for VPs. Skip during save, warn the user.
- **Empty panel**: saving a panel with no plots produces a valid template with an empty `plots` list.
- **Time range**: saved as ISO 8601 strings. On load, parsed to epoch floats for `TimeRange()`.
- **`apply()` and time range**: `apply()` sets the panel's time range from the template. This is the expected behavior — if the user doesn't want to change the time range, they can modify the template or set it after.
- **Intervals**: stored in the template for speasy_proxy compat. SciQLop can use them to create catalog overlays (future), or ignore them on load initially.
- **Graph type auto-detection**: `PlotModel` does not store graph type explicitly. On load, `plot_product` auto-detects the graph type (line vs colormap) from the product's `ParameterType`, which is the existing behavior. The `log_z` field handles the spectrogram-specific axis setting.

## What's NOT in scope

- Multi-panel layouts / dock state
- Virtual product serialization
- Graph colors (auto-assigned by palette)
- Sub-panel hierarchies (future extension: add optional `sub_panels` field to `PlotModel`)
- Interval/catalog overlay rendering on load (just stored in the model for now)
- Schema migration (version field exists for future use, no migration logic needed for v1)
