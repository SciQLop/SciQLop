# SciQLop Plugin Development Skill + Copier Template

**Date:** 2026-03-12
**Status:** Approved

## Goal

Make it easy for both end-users and contributors to create SciQLop plugins by providing:

1. A **copier template** for quick scaffolding
2. A **Claude Code skill** that makes Claude an expert on the plugin system

## Plugin Archetypes Covered

- **Data provider** — extends `DataProvider`, registers in product tree, supplies time series data
- **UI extension** — adds toolbar actions, side panels, dock widgets, menus
- **Combined** — a single plugin can do both

Not covered: async/networked plugins (too specialized), app store publishing (future work).

## Component 1: Copier Template

### Location

`templates/plugin/` in the SciQLop repo.

### Copier Prompts

| Prompt | Type | Default | Description |
|--------|------|---------|-------------|
| `plugin_name` | str | required | Human-readable name, e.g., "My Instrument Provider" |
| `plugin_slug` | str | derived from name | Python package name, e.g., `my_instrument_provider` |
| `provides_data` | bool | false | Include `DataProvider` subclass + product tree registration |
| `has_ui` | bool | false | Include toolbar action and side panel scaffold |
| `author_name` | str | required | Author name for plugin.json |
| `author_email` | str | required | Author email for plugin.json |
| `author_organization` | str | "" | Author organization for plugin.json |
| `python_dependencies` | str | "" | Comma-separated pip dependencies |
| `output_dir` | path | `~/.local/share/sciqlop/plugins/` | Where to generate the plugin |

### Generated Structure

```
{{plugin_slug}}/
├── __init__.py              # imports load()
├── plugin.json              # filled from prompts
└── {{plugin_slug}}.py       # load() + conditional DataProvider / UI code
```

### Generated Code Patterns

#### plugin.json

```json
{
  "name": "{{plugin_name}}",
  "version": "0.1.0",
  "description": "",
  "authors": [{"name": "{{author_name}}", "email": "{{author_email}}", "organization": "{{author_organization}}"}],
  "license": "MIT",
  "python_dependencies": [{{python_dependencies}}],
  "dependencies": [],
  "disabled": false
}
```

#### __init__.py

```python
from .{{plugin_slug}} import load
```

#### Data provider (when `provides_data` is true)

Generates a `DataProvider` subclass with:

- `__init__`: calls `super().__init__(name=..., data_order=DataOrder.Y_FIRST, cacheable=True)`, registers a `ProductsModelNode` in `ProductsModel.instance()`
- `get_data(self, product, start, stop)`: stub returning a `SpeasyVariable` with placeholder data
- `labels(self, product)`: returns component labels from product metadata
- `graph_type(self, product)`: returns `GraphType.MultiLines` by default

#### UI extension (when `has_ui` is true)

Generates a `QObject`-based plugin class with:

- `__init__(self, main_window)`: creates a toolbar action and optionally a side panel widget
- Toolbar action connected to a stub slot
- Optional `async close(self)` for cleanup

#### Combined (both true)

Single class that inherits from `DataProvider` and includes UI setup in `load()`. The `load()` function wires both the data registration and UI elements.

#### load() function

```python
def load(main_window):
    return PluginClass(main_window)
```

`load()` **must** always accept `main_window` even for data-only plugins (the loader always passes it). Data-only plugins can simply ignore it. Returns the plugin instance so SciQLop can call `close()` on shutdown.

## Component 2: Claude Code Skill

### Name

`sciqlop-plugin-dev`

### Trigger

When the user asks to create, modify, debug, or extend a SciQLop plugin.

### Knowledge Loaded

The skill provides Claude with reference knowledge about the plugin system (patterns and contracts, not full source code):

**Plugin lifecycle:**
- Discovery paths: `SciQLop/plugins/` (built-in), `~/.local/share/sciqlop/plugins/` (user), extra folders from settings
- Contract: `load(main_window: SciQLopMainWindow)` → return plugin object or None
- Cleanup: optional `async close(self)` called with 5s timeout on app exit
- Enable/disable: `SciQLopPluginsSettings.plugins` dict, also `"disabled": true` in plugin.json

**plugin.json schema:**
- All fields from `PluginDesc` Pydantic model: name, version, description, authors, license, python_dependencies, dependencies, disabled

**DataProvider API:**
- Base class: `SciQLop.components.plotting.backend.data_provider.DataProvider`
- Constructor: `name`, `data_order` (Y_FIRST or X_FIRST, default is X_FIRST), `cacheable`
- Methods: `get_data(node, start, stop)`, `labels(node)`, `graph_type(node)` — the `node` argument is a `ProductsModelNode` (access metadata via `node.metadata("key")`)
- Return types: `SpeasyVariable`, or tuple of numpy arrays
- Product tree: `ProductsModel.instance().add_node(path, node)` with `ProductsModelNode` hierarchy
- `ProductsModelNode` constructors: `(name)` for group nodes, `(name, provider_name, metadata_dict, node_type, parameter_type)` for leaf nodes
- Node types: `ProductsModelNodeType.PARAMETER`, parameter types: `ParameterType.Vector`, `Scalar`, `Spectrogram`

**Main window integration:**
- `main_window.addToolBar(title)` → QToolBar
- `main_window.toolBar` — default toolbar
- `main_window.toolsMenu`, `main_window.viewMenu` — menus
- `main_window.add_side_pan(widget, location, icon)` — side panels (`location` is a `QtAds.PySide6QtAds.ads.SideBarLocation` enum, defaults to `SideBarLeft`)
- `main_window.addWidgetIntoDock(area, widget)` — dock widgets
- Signals: `panel_added(TimeSyncPanel)`, `panels_list_changed(list)`
- `main_window.new_plot_panel(name=...)` → `TimeSyncPanel`
- `main_window.push_variables_to_console(dict)` — expose variables in Jupyter

**User API (what plugin authors can use):**
- `SciQLop.user_api.plot`: `plot_panel()`, `create_plot_panel()`, plot types
- `SciQLop.user_api.virtual_products`: `create_virtual_product()`
- `SciQLop.user_api.gui`: `get_main_window()`

**Settings integration:**
- Extend `ConfigEntry` (Pydantic BaseModel) with `category` and `subcategory` ClassVars
- Auto-persisted to `~/.config/sciqlop/<classname>.yaml`
- Use as context manager for auto-save

### Behavior

- **New plugin requests:** invoke copier template to scaffold, then customize the generated code
- **Existing plugin work:** use reference knowledge to assist with modifications, debugging, adding features
- **Validation:** ensure `load()` signature is correct, `plugin.json` is valid, data provider return types match expected formats

### Prerequisites

- `copier` must be available in the environment. If not installed, the skill falls back to generating files directly.

### Known Limitations

- The `dependencies` field in `plugin.json` is not yet used for load ordering — plugins load in discovery order regardless.

### Skill Does NOT Cover

- Async/networked plugin patterns
- App store publishing workflow
- Plugin testing scaffolding (could be added later as a copier option)
