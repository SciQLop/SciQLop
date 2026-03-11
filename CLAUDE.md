# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is SciQLop

SciQLop (Scientific Qt application for Learning from Observations of Plasmas) is a PySide6 desktop application for interactive visualization and labeling of in-situ space plasma time series. It embeds a full Jupyter/IPython kernel and integrates with the `speasy` data access library.

## Commands

All commands should be run with `uv run` (e.g., `uv run pytest`, `uv run python`).

```bash
# Install in editable mode with dev dependencies
uv pip install -e ".[dev]"

# Run the application
uv run sciqlop
# or
uv run python -m SciQLop.app

# Run all tests (Linux: requires Xvfb, auto-used via pytest-xvfb)
uv run pytest

# Run a specific test file or test by name
uv run pytest tests/test_creating_plots.py
uv run pytest -k test_virtual_products
```

No linter is enforced beyond flake8 (configured in `setup.cfg`, excludes `docs/`).

## Code Style

- **KISS** — prefer the simplest solution that works; avoid over-engineering.
- **Functional over imperative** — favor pure functions and transformations over mutation and side effects.
- **Data over code** — prefer declarative approaches; drive behavior with data structures and configuration, not sprawling logic. Pydantic models are encouraged.
- **Uniform abstraction levels** — a function should operate at one level of abstraction. Never mix high-level orchestration with low-level details in the same function.
- **Small units** — keep files, classes, and functions short. Avoid deep folder hierarchies with many files.
- **Locality of reasoning** — code should be understandable from what you can see, without chasing references across the codebase.
- **No comment-decorated code blocks** — if a block of code needs a comment to explain what it does, extract it into a well-named function instead.
- **Self-explanatory code** — comments are only for: (1) links to algorithm documentation, (2) justifying non-obvious decisions ("why Y instead of X").
- **Pragmatic factorization** — DRY is good until it makes the code too abstract for no real benefit. Three similar lines are better than a premature abstraction.

## Architecture

### Startup sequence

`app.py` → `sciqlop_launcher.py` (prepares workspace venv, migrates workspace.json→workspace.sciqlop, installs deps, spawns subprocess with `SCIQLOP_WORKSPACE_DIR` env var) → `sciqlop_app.py` (creates Qt app, loads theming, creates `SciQLopMainWindow`, auto-loads workspace from env var, loads plugins, starts async event loop via `qasync`). Exit code 64 = restart same workspace, 65 = switch workspace (reads target from `.sciqlop_switch_target` file). Non-default workspaces auto-start JupyterLab.

### Key layers

**`SciQLop/core/`** — Shared infrastructure: `SciQLopApp` (QApplication subclass), `SciQLopMainWindow` (dock manager host using PySide6-QtAds), shared data types/enums, MIME types, generic UI widgets, and small utilities.

**`SciQLop/components/`** — Self-contained feature modules. Each typically has `backend/` (logic) and `ui/` (widgets) subdirs. Key components:
- `catalogs/` — catalog browsing, creation, editing, and overlay on plots
- `plotting/` — plot panel management, axes configuration, data rendering
- `theming/` — palette loading, auto-invert icons, stylesheet generation
- `settings/` — Pydantic-based config persisted to YAML in `~/.config/sciqlop/`
- `plugins/` — dynamic plugin loader, plugin dependency resolution
- `workspaces/` — workspace management via `WorkspaceManifest` (TOML `.sciqlop` files), environment setup (venv, migration from old JSON format, archive), examples
- `jupyter/` — embedded IPython kernel + JupyterLab server
- `welcome/` — welcome page (QWebEngineView + QWebChannel + Jinja2)
- `appstore/` — plugin app store (same QWebEngine pattern as welcome)

**`SciQLop/plugins/`** — Built-in plugins (speasy data provider, catalogs, collaborative features). Each plugin exposes a `load(main_window)` function and optionally a `plugin.json` descriptor.

**`SciQLop/user_api/`** — Public Python API surface (plot creation, virtual products, GUI helpers) intended for use from the embedded Jupyter console.

**`SciQLop/Jupyter/`** — Custom Jupyter kernel provisioner (`SciQLopProvisioner`) that connects notebooks to SciQLop's running IPython kernel via `SCIQLOP_IPYTHON_CONNECTION_FILE`.

### Resources convention

Shared resources (icons, palettes, splash) live in `SciQLop/resources/`. Component-specific assets (templates, CSS, JS) go in `SciQLop/components/<name>/resources/` next to their owning component.

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

### Testing

Tests use `pytest-qt` for Qt widget testing and `pytest-xvfb` on Linux (auto-configured in `conftest.py` at 2560x1440). Test helpers and fixtures are in `tests/fixtures.py` and `tests/helpers.py`.
