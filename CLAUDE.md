# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is SciQLop

SciQLop (Scientific Qt application for Learning from Observations of Plasmas) is a PySide6 desktop application for interactive visualization and labeling of in-situ space plasma time series. It embeds a full Jupyter/IPython kernel and integrates with the `speasy` data access library.

## Commands

All commands should be run with `uv run` (e.g., `uv run pytest`, `uv run python`).

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run the application
sciqlop
# or
python -m SciQLop.app

# Run all tests (Linux: requires Xvfb, auto-used via pytest-xvfb)
pytest

# Run a specific test
pytest tests/test_creating_plots.py
pytest -k test_virtual_products
```

No linter is enforced beyond flake8 (configured in `setup.cfg`, excludes `docs/`).

## Architecture

### Startup sequence

`app.py` → `sciqlop_launcher.py` (checks deps, restarts on exit code 64) → `sciqlop_app.py` (creates Qt app, loads theming, creates `SciQLopMainWindow`, loads plugins, starts async event loop via `qasync`).

### Key layers

**`SciQLop/core/`** — Qt infrastructure: `SciQLopApp` (QApplication subclass with palette/stylesheet management), `SciQLopMainWindow` (dock manager host using PySide6-QtAds), drag-and-drop base classes, Qt data models.

**`SciQLop/components/`** — Self-contained feature modules. Each typically has `backend/` (logic) and `ui/` (widgets) subdirs. Key components:
- `theming/` — palette loading, auto-invert icons, stylesheet generation
- `settings/` — Pydantic-based config persisted to YAML in `~/.config/sciqlop/`
- `plugins/` — dynamic plugin loader
- `workspaces/` — Jupyter workspace management
- `jupyter/` — embedded IPython kernel + JupyterLab server

**`SciQLop/plugins/`** — Built-in plugins (speasy data provider, catalogs, collaborative features). Each plugin exposes a `load(main_window)` function and optionally a `plugin.json` descriptor.

**`SciQLop/user_api/`** — Public Python API surface (plot creation, virtual products, GUI helpers) intended for use from the embedded Jupyter console.

**`SciQLop/Jupyter/`** — Custom Jupyter kernel provisioner (`SciQLopProvisioner`) that connects notebooks to SciQLop's running IPython kernel via `SCIQLOP_IPYTHON_CONNECTION_FILE`.

### Settings system

Config entries are Pydantic `BaseModel` subclasses that extend `ConfigEntry`. Every subclass **must** declare two `ClassVar[str]` attributes:
- `category` — top-level group (use `SettingsCategory` enum values)
- `subcategory` — sub-group string

Subclasses are auto-registered in `ConfigEntry._entries_` on class creation and serialized to `~/.config/sciqlop/<ClassName>.lower().yaml`. Use as a context manager to auto-save on exit:
```python
with SomeSettings() as s:
    s.some_field = new_value
```

### Settings UI delegates

`SciQLop/components/settings/ui/settings_delegates/` provides a registry for mapping Python types to editor widgets. Register a delegate with:
```python
from SciQLop.components.settings.ui.settings_delegates import register_delegate, SettingDelegate

@register_delegate(MyType)
class MyTypeDelegate(SettingDelegate):
    ...
```
The registry is keyed by `type.__name__`. `get_delegate_for_field()` uses the registry as the final fallback after handling Literal, Enum, `str` with widget hints, and list types.

### Plugin system

Plugins are Python packages/modules discovered in:
1. `SciQLop/plugins/` (built-in)
2. `~/.local/share/sciqlop/plugins/` (user)
3. Paths from `SciQLopPluginsSettings.extra_plugins_folders`

Each plugin's `load(main_window)` is called at startup. Enabled/disabled state is stored in `SciQLopPluginsSettings.plugins`.