# SciQLop Backend for Speasy Plot API — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Register a SciQLop plotting backend into speasy's `__backends__` dict so `variable.plot['sciqlop'].line()` renders into SciQLop panels.

**Architecture:** One backend class (`SciQLopBackend`) implementing speasy's `.line()` / `.colormap()` contract, one `ConfigEntry` for the default backend setting, and registration in the speasy plugin's `load()`. The backend delegates to SciQLop's existing `PlotPanel` / `TimeSeriesPlot` user API.

**Tech Stack:** PySide6, speasy, SciQLop user API, pytest-qt

**Note:** The spec mentions settings path as `SciQLop/components/settings/entries/` but the actual codebase structure uses `SciQLop/components/settings/backend/` — this plan follows the codebase.

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `SciQLop/user_api/plot/_speasy_backend.py` | `SciQLopBackend` class + module-level current panel tracking |
| Create | `SciQLop/components/settings/backend/plot_backend_settings.py` | `PlotBackendSettings` ConfigEntry |
| Modify | `SciQLop/plugins/speasy_provider/speasy_provider.py:203-209` | Register backend in `load()` |
| Create | `tests/test_speasy_plot_backend.py` | Unit + integration tests |

---

## Chunk 1: Setting + Backend + Registration

### Task 1: PlotBackendSettings ConfigEntry

**Files:**
- Create: `SciQLop/components/settings/backend/plot_backend_settings.py`
- Test: `tests/test_speasy_plot_backend.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_speasy_plot_backend.py
from .fixtures import *
import pytest


def test_plot_backend_settings_defaults():
    from SciQLop.components.settings.backend.plot_backend_settings import PlotBackendSettings
    settings = PlotBackendSettings()
    assert settings.default_speasy_backend == "matplotlib"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_speasy_plot_backend.py::test_plot_backend_settings_defaults -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write the setting**

```python
# SciQLop/components/settings/backend/plot_backend_settings.py
from typing import ClassVar, Literal
from .entry import ConfigEntry, SettingsCategory


class PlotBackendSettings(ConfigEntry):
    category: ClassVar[str] = SettingsCategory.APPLICATION
    subcategory: ClassVar[str] = "Plotting"

    default_speasy_backend: Literal["matplotlib", "sciqlop"] = "matplotlib"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_speasy_plot_backend.py::test_plot_backend_settings_defaults -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/settings/backend/plot_backend_settings.py tests/test_speasy_plot_backend.py
git commit -m "feat(settings): add PlotBackendSettings for speasy plot backend selection"
```

---

### Task 2: SciQLopBackend — line() and colormap() with all ax modes

**Files:**
- Create: `SciQLop/user_api/plot/_speasy_backend.py`
- Modify: `tests/test_speasy_plot_backend.py`

- [ ] **Step 1: Write failing tests for all ax modes**

```python
# append to tests/test_speasy_plot_backend.py
import numpy as np


def test_sciqlop_backend_line_creates_panel(qtbot, qapp, main_window):
    """ax=None should create a new panel and plot into it"""
    from SciQLop.user_api.plot._speasy_backend import SciQLopBackend

    backend = SciQLopBackend()
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([4.0, 5.0, 6.0])
    result = backend.line(x=x, y=y)
    assert result is not None
    plot, graph = result
    assert plot is not None
    assert graph is not None


def test_sciqlop_backend_line_with_panel(qtbot, qapp, main_window):
    """ax=PlotPanel should create a new plot in the given panel"""
    from SciQLop.user_api.plot._speasy_backend import SciQLopBackend
    from SciQLop.user_api.plot import create_plot_panel

    backend = SciQLopBackend()
    panel = create_plot_panel()
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([4.0, 5.0, 6.0])

    plot1, graph1 = backend.line(x=x, y=y, ax=panel)
    plot2, graph2 = backend.line(x=x, y=y, ax=panel)
    assert plot1 is not None
    assert plot2 is not None
    assert graph1 is not None
    assert graph2 is not None


def test_sciqlop_backend_line_with_plot(qtbot, qapp, main_window):
    """ax=TimeSeriesPlot should add a graph to the existing plot"""
    from SciQLop.user_api.plot._speasy_backend import SciQLopBackend
    from SciQLop.user_api.plot import create_plot_panel

    backend = SciQLopBackend()
    panel = create_plot_panel()
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([4.0, 5.0, 6.0])

    plot, graph1 = backend.line(x=x, y=y, ax=panel)
    # Add second line to the same plot — returned plot should be the same object
    returned_plot, graph2 = backend.line(x=x, y=y * 2, ax=plot)
    assert returned_plot is plot


def test_sciqlop_backend_colormap(qtbot, qapp, main_window):
    from SciQLop.user_api.plot._speasy_backend import SciQLopBackend

    backend = SciQLopBackend()
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([10.0, 20.0, 30.0])
    z = np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], [7.0, 8.0, 9.0]])
    result = backend.colormap(x=x, y=y, z=z)
    assert result is not None
    plot, colormap = result
    assert plot is not None
    assert colormap is not None


def test_sciqlop_backend_invalid_ax_raises(qtbot, qapp, main_window):
    from SciQLop.user_api.plot._speasy_backend import SciQLopBackend

    backend = SciQLopBackend()
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([4.0, 5.0, 6.0])
    with pytest.raises(TypeError):
        backend.line(x=x, y=y, ax="not_a_plot")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_speasy_plot_backend.py -v -k "backend"`
Expected: FAIL with `ModuleNotFoundError` (backend module doesn't exist yet)

- [ ] **Step 3: Write the backend**

The three `ax` modes are handled inline in `line()` and `colormap()` to keep the logic clear and avoid a mixed-return-type helper.

```python
# SciQLop/user_api/plot/_speasy_backend.py
from __future__ import annotations
from SciQLop.user_api.plot._panel import PlotPanel, create_plot_panel
from SciQLop.user_api.plot._plots import TimeSeriesPlot
from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)

_current_panel: PlotPanel | None = None


def _get_or_create_panel() -> PlotPanel:
    global _current_panel
    if _current_panel is None or _current_panel._impl is None:
        _current_panel = create_plot_panel()
    return _current_panel


def _plot_into(ax, x, y, z=None):
    """Dispatch plot call based on ax type.

    Returns (TimeSeriesPlot | ProjectionPlot, Graph | ColorMap).
    """
    global _current_panel
    if ax is None:
        panel = _get_or_create_panel()
        return panel.plot_data(x, y, z) if z is not None else panel.plot_data(x, y)
    if isinstance(ax, PlotPanel):
        _current_panel = ax
        return ax.plot_data(x, y, z) if z is not None else ax.plot_data(x, y)
    if isinstance(ax, TimeSeriesPlot):
        args = (x, y, z) if z is not None else (x, y)
        graph = ax.plot(*args)
        return ax, graph
    raise TypeError(f"ax must be None, PlotPanel, or TimeSeriesPlot, got {type(ax).__name__}")


class SciQLopBackend:
    def line(self, x, y, ax=None, labels=None, units=None,
             xaxis_label=None, yaxis_label=None, *args, **kwargs):
        return _plot_into(ax, x, y)

    def colormap(self, x, y, z, ax=None, logy=True, logz=True,
                 xaxis_label=None, yaxis_label=None, yaxis_units=None,
                 zaxis_label=None, zaxis_units=None, cmap=None,
                 vmin=None, vmax=None, *args, **kwargs):
        return _plot_into(ax, x, y, z)

    def __call__(self, *args, **kwargs):
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_speasy_plot_backend.py -v -k "backend"`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/plot/_speasy_backend.py tests/test_speasy_plot_backend.py
git commit -m "feat(plot): add SciQLopBackend with line() and colormap()"
```

---

### Task 3: End-to-end test via speasy Plot API

**Files:**
- Modify: `tests/test_speasy_plot_backend.py`

- [ ] **Step 1: Write the integration test**

`SpeasyVariable` requires `VariableTimeAxis` and `DataContainer` — raw numpy arrays won't work.

```python
# append to tests/test_speasy_plot_backend.py

def test_speasy_variable_plot_with_sciqlop_backend(qtbot, qapp, main_window):
    """End-to-end: register backend, create a SpeasyVariable, call .plot['sciqlop'].line()"""
    import speasy.plotting as splt
    from SciQLop.user_api.plot._speasy_backend import SciQLopBackend
    from speasy.products.variable import SpeasyVariable
    from speasy.core.data_containers import DataContainer, VariableTimeAxis

    splt.__backends__["sciqlop"] = SciQLopBackend

    x = np.arange('2020-01-01', '2020-01-02', dtype='datetime64[h]').astype('datetime64[ns]')
    y = np.sin(np.arange(len(x), dtype=float))

    time_axis = VariableTimeAxis(values=x, meta={})
    values = DataContainer(values=y.reshape(-1, 1), meta={}, name='sin', is_time_dependent=True)
    var = SpeasyVariable(values=values, columns=['sin'], axes=[time_axis])

    result = var.plot["sciqlop"].line()
    assert result is not None
    plot, graph = result
    assert plot is not None
    assert graph is not None
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest tests/test_speasy_plot_backend.py::test_speasy_variable_plot_with_sciqlop_backend -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_speasy_plot_backend.py
git commit -m "test(plot): add end-to-end speasy plot backend integration test"
```

---

### Task 4: Registration in speasy plugin

**Files:**
- Modify: `SciQLop/plugins/speasy_provider/speasy_provider.py:203-209`
- Modify: `tests/test_speasy_plot_backend.py`

The `main_window` fixture calls `start_sciqlop()` which calls `load_all()` to load all built-in plugins including speasy.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_speasy_plot_backend.py

def test_sciqlop_backend_registered_after_plugin_load(qtbot, qapp, main_window):
    """After the speasy plugin loads (via start_sciqlop), 'sciqlop' should be in __backends__"""
    import speasy.plotting as splt
    assert "sciqlop" in splt.__backends__
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_speasy_plot_backend.py::test_sciqlop_backend_registered_after_plugin_load -v`
Expected: FAIL with `AssertionError` (backend not registered yet)

- [ ] **Step 3: Add registration to speasy plugin load()**

In `SciQLop/plugins/speasy_provider/speasy_provider.py`, modify the `load()` function (around line 203):

```python
def load(*args):
    from speasy.core.cache import _cache
    from .speasy_catalog_provider import SpeasyCatalogProvider
    _cache._data._local = ThreadStorage()
    plugin = SpeasyPlugin()
    plugin._catalog_provider = SpeasyCatalogProvider()
    _register_plot_backend()
    return plugin


def _register_plot_backend():
    try:
        import speasy.plotting as splt
        from SciQLop.user_api.plot._speasy_backend import SciQLopBackend
        from SciQLop.components.settings.backend.plot_backend_settings import PlotBackendSettings

        splt.__backends__["sciqlop"] = SciQLopBackend
        if PlotBackendSettings().default_speasy_backend == "sciqlop":
            splt.__backends__[None] = SciQLopBackend
    except Exception as e:
        from SciQLop.components.sciqlop_logging import getLogger
        getLogger(__name__).debug(f"Could not register SciQLop plot backend: {e}")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_speasy_plot_backend.py::test_sciqlop_backend_registered_after_plugin_load -v`
Expected: PASS

- [ ] **Step 5: Run all tests**

Run: `uv run pytest tests/test_speasy_plot_backend.py -v`
Expected: All tests PASS

- [ ] **Step 6: Commit**

```bash
git add SciQLop/plugins/speasy_provider/speasy_provider.py tests/test_speasy_plot_backend.py
git commit -m "feat(speasy): register SciQLop plot backend on plugin load"
```

---

### Task 5: RuntimeError when called outside SciQLop

**Files:**
- Modify: `tests/test_speasy_plot_backend.py`

- [ ] **Step 1: Write the test**

```python
# append to tests/test_speasy_plot_backend.py

def test_sciqlop_backend_raises_without_main_window(qtbot, qapp):
    """Backend should raise a clear error if no SciQLopMainWindow exists"""
    from SciQLop.user_api.plot._speasy_backend import SciQLopBackend
    import SciQLop.user_api.plot._speasy_backend as backend_module
    backend_module._current_panel = None  # reset module state

    backend = SciQLopBackend()
    x = np.array([1.0, 2.0, 3.0])
    y = np.array([4.0, 5.0, 6.0])
    with pytest.raises((RuntimeError, AttributeError)):
        backend.line(x=x, y=y)
```

- [ ] **Step 2: Run test**

Run: `uv run pytest tests/test_speasy_plot_backend.py::test_sciqlop_backend_raises_without_main_window -v`

If the error from `create_plot_panel()` is cryptic, wrap the call in `_get_or_create_panel` with:
```python
try:
    _current_panel = create_plot_panel()
except Exception:
    raise RuntimeError("SciQLopBackend requires a running SciQLop application")
```

- [ ] **Step 3: Commit**

```bash
git add SciQLop/user_api/plot/_speasy_backend.py tests/test_speasy_plot_backend.py
git commit -m "test(plot): verify clear error when backend used outside SciQLop"
```

---

### Task 6: Run full test suite

- [ ] **Step 1: Run entire test suite to check for regressions**

Run: `uv run pytest -v`
Expected: All existing tests still pass, all new tests pass

- [ ] **Step 2: Final commit if any fixups needed**
