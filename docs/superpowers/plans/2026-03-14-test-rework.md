# Test Rework Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework SciQLop test infrastructure so tests are fast (no per-test app restart), filesystem-safe (temp dirs only), and organized as user-story workflows.

**Architecture:** Three test tiers — unit (no Qt), widget (Qt app only), workflow (full app, module-scoped). Workflow tests group related assertions into classes that share state like a real user session. A session-scoped autouse fixture redirects all persistent paths to temp dirs.

**Tech Stack:** pytest, pytest-qt, pytest-xvfb, PySide6

**Spec:** `docs/superpowers/specs/2026-03-14-test-rework-design.md`

---

## Chunk 1: Foundation (fixtures + filesystem isolation)

### Task 1: Add `sciqlop_test_env` fixture for filesystem isolation

**Files:**
- Modify: `tests/conftest.py`

This fixture redirects all persistent paths to temp dirs so tests never touch the real home directory. Env vars that must be set before any SciQLop/speasy import (`SPEASY_SKIP_INIT_PROVIDERS`, `INSIDE_SCIQLOP`, Qt attributes) go in `pytest_configure` which runs before any collection/import. The fixture handles the tmp directory creation.

- [ ] **Step 1: Rewrite `tests/conftest.py`**

Replace the entire content of `tests/conftest.py` with:

```python
import os
import platform
import tempfile
from pathlib import Path

import pytest

# Temp root created early (before fixtures) for env var paths.
# Using tempfile directly because tmp_path_factory isn't available in hooks.
_test_tmp = Path(tempfile.mkdtemp(prefix="sciqlop_test_"))
_config_dir = _test_tmp / "config"
_data_dir = _test_tmp / "data"
_workspace_dir = _test_tmp / "workspace"
_config_dir.mkdir()
_data_dir.mkdir()
_workspace_dir.mkdir()


def pytest_configure(config):
    # These env vars MUST be set before any SciQLop or speasy import.
    # pytest_configure runs before collection, so no test module is imported yet.
    os.environ["XDG_CONFIG_HOME"] = str(_config_dir)
    os.environ["XDG_DATA_HOME"] = str(_data_dir)
    os.environ["SCIQLOP_WORKSPACE_DIR"] = str(_workspace_dir)
    os.environ["SPEASY_SKIP_INIT_PROVIDERS"] = "1"
    os.environ["SCIQLOP_DEBUG"] = "1"
    os.environ["INSIDE_SCIQLOP"] = "1"
    if platform.system() == "Windows":
        os.environ["APPDATA"] = str(_config_dir)

    # Qt OpenGL attributes — must be set before QApplication creation.
    from PySide6 import QtCore
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseDesktopOpenGL, True)
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts, True)

    if platform.system() == "Linux":
        os.environ["QT_QPA_PLATFORM"] = "xcb"
        config.option.xvfb_xauth = True
        config.option.xvfb_width = 2560
        config.option.xvfb_height = 1440


@pytest.fixture(scope="session", autouse=True)
def sciqlop_test_env():
    """Expose the test temp root to fixtures that need it."""
    yield _test_tmp


def pytest_unconfigure(config):
    import shutil
    shutil.rmtree(_test_tmp, ignore_errors=True)
```

- [ ] **Step 2: Run existing tests to verify nothing breaks**

Run: `uv run pytest tests/test_workspace_manifest.py tests/test_command_palette_fuzzy.py tests/test_mime.py -v`
Expected: All pass. These are unit tests that should be unaffected.

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add sciqlop_test_env fixture for filesystem isolation"
```

### Task 2: Rewrite `main_window` fixture as module-scoped

**Files:**
- Modify: `tests/fixtures.py`

The current `main_window` fixture is function-scoped and calls `start_sciqlop()` (which creates splash screens, etc.). Replace it with a module-scoped fixture that runs only the essential subset.

- [ ] **Step 1: Rewrite `fixtures.py`**

Replace the entire content of `tests/fixtures.py` with:

```python
import os
import pytest
from typing import Tuple


@pytest.fixture(scope="session")
def qapp_cls():
    from SciQLop.core.sciqlop_application import SciQLopApp
    return SciQLopApp


@pytest.fixture(scope="session")
def sciqlop_resources(qapp):
    """One-time session setup: Qt resources, icons, event loop."""
    from SciQLop.resources import qInitResources
    from SciQLop.components.theming.icons import flush_deferred_icons
    from SciQLop.core.sciqlop_application import sciqlop_event_loop

    qInitResources()
    flush_deferred_icons()
    sciqlop_event_loop()


@pytest.fixture(scope="module")
def main_window(qapp, sciqlop_resources):
    """Module-scoped main window with plugins loaded.

    Shared across all tests in a workflow file. No splash screen.
    Teardown closes the window and clears the command registry.
    """
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    from SciQLop.components.plugins import load_all, loaded_plugins
    from SciQLop.components.command_palette.commands import register_builtin_commands
    from SciQLop.components.command_palette.backend.harvester import harvest_qactions

    mw = SciQLopMainWindow()
    mw.show()
    qapp.processEvents()
    load_all(mw)
    register_builtin_commands(qapp.command_registry)
    harvest_qactions(qapp.command_registry, mw)
    mw.push_variables_to_console({"plugins": loaded_plugins})
    qapp.processEvents()

    yield mw

    mw.close()
    for cmd in list(qapp.command_registry.commands()):
        qapp.command_registry.unregister(cmd.id)
    qapp.processEvents()


@pytest.fixture(scope="function")
def test_plugin(qtbot, qapp, main_window):
    from SciQLop.components.plugins.backend.loader import load_plugin, plugins_folders
    p = load_plugin(plugins_folders()[0], "test_plugin", main_window)
    qtbot.wait(1)
    return p


@pytest.fixture(scope="function")
def simple_vp_callback():
    import numpy as np

    def callback(start: float, end: float) -> Tuple[np.ndarray, np.ndarray]:
        x = np.linspace(start, end, int(end - start))
        y = np.sin(x)
        return x, y

    return callback


@pytest.fixture(scope="function")
def plot_panel(main_window):
    from SciQLop.user_api.plot import create_plot_panel
    return create_plot_panel()
```

Key changes:
- `main_window` is now `scope="module"` and uses `yield` for teardown
- No `qtbot` dependency (it's function-scoped, can't be used in module-scoped fixtures)
- No `start_sciqlop()` — runs the essential subset directly
- Teardown: closes window, unregisters all commands
- `sciqlop_resources` (session-scoped) handles one-time init (Qt resources, icons, event loop)
- Qt OpenGL attributes (`AA_UseDesktopOpenGL`, `AA_ShareOpenGLContexts`) set in `pytest_configure` (conftest.py), before QApplication creation
- `plot_panel` depends on `main_window` instead of `qtbot, main_window` (it doesn't use qtbot)
- `test_plugin` fixture kept for backward compat but workflow tests don't need it — `load_all()` already loads bundled plugins

- [ ] **Step 2: Run an existing test that uses `main_window` to verify it works**

Run: `uv run pytest tests/test_creating_plots.py::test_create_panel -v`
Expected: PASS

- [ ] **Step 3: Run all existing tests to check for regressions**

Run: `uv run pytest -v`
Expected: All previously passing tests still pass.

- [ ] **Step 4: Commit**

```bash
git add tests/fixtures.py
git commit -m "test: rewrite main_window as module-scoped fixture, skip splash"
```

### Task 3: Update `helpers.py` to remove stale import

**Files:**
- Modify: `tests/helpers.py`

`helpers.py` currently does `from .fixtures import *`. This is needed for tests that `from .helpers import drag_and_drop` to also get fixtures. Verify it still works with the new fixtures.

- [ ] **Step 1: Verify `helpers.py` imports work**

Run: `uv run python -c "from tests.helpers import drag_and_drop; print('OK')"`
Expected: `OK`

- [ ] **Step 2: If needed, fix any import issues and commit**

If the import works, no changes needed. Skip this commit.

---

## Chunk 2: Migrate existing integration tests to workflow format

### Task 4: Migrate `test_creating_plots.py` → `test_wf_plot_and_navigate.py`

**Files:**
- Create: `tests/test_wf_plot_and_navigate.py`
- Keep: `tests/test_creating_plots.py` (delete after migration verified)

Convert the existing plot creation tests into a workflow class. The parametrized `test_create_plot` becomes multiple ordered tests in a workflow.

- [ ] **Step 1: Create `test_wf_plot_and_navigate.py`**

```python
from tests.helpers import *
import numpy as np
import pytest


class TestPlotWorkflow:
    """Create panels, plot static data and products, verify data."""

    panel = None

    def test_create_panel(self, main_window):
        from SciQLop.user_api.plot import create_plot_panel

        TestPlotWorkflow.panel = create_plot_panel()
        assert TestPlotWorkflow.panel is not None
        assert TestPlotWorkflow.panel._impl is not None

    def test_plot_static_data(self, main_window, qtbot):
        panel = TestPlotWorkflow.panel
        plot, graph = panel.plot([1, 2, 3], [1, 2, 3])
        assert plot is not None
        assert graph is not None
        for _ in range(10000):
            if graph.data is not None and graph.data[0] is not None:
                break
            qtbot.wait(1)
        assert len(graph.data[0])
        assert np.allclose(graph.data[0], [1, 2, 3])
        assert np.allclose(graph.data[1], [1, 2, 3])

    def test_plot_static_spectro(self, main_window, qtbot):
        from SciQLop.user_api.plot import create_plot_panel

        panel = create_plot_panel()
        x = [1, 2, 3]
        y = [1, 2, 3]
        z = [[1, 2, 3], [1, 2, 3], [1, 2, 3]]
        plot, graph = panel.plot(x, y, z)
        assert plot is not None
        assert graph is not None
        for _ in range(10000):
            if graph.data is not None and graph.data[0] is not None:
                break
            qtbot.wait(1)
        assert len(graph.data[0])

    def test_plot_product(self, main_window, qtbot):
        # test_plugin is already loaded by load_all() in the main_window fixture
        from SciQLop.user_api.plot import create_plot_panel

        panel = create_plot_panel()
        plot, graph = panel.plot("TestPlugin//TestMultiComponent")
        assert plot is not None
        assert graph is not None
        for _ in range(10000):
            if graph.data is not None and graph.data[0] is not None:
                break
            qtbot.wait(1)
        assert len(graph.data[0])
```

- [ ] **Step 2: Run the workflow**

Run: `uv run pytest tests/test_wf_plot_and_navigate.py -v`
Expected: All tests pass in order.

- [ ] **Step 3: Commit**

```bash
git add tests/test_wf_plot_and_navigate.py
git commit -m "test: add plot workflow test (migrated from test_creating_plots)"
```

### Task 5: Migrate `test_virtual_products.py` → `test_wf_virtual_products.py`

**Files:**
- Create: `tests/test_wf_virtual_products.py`

Convert the parametrized VP test into a workflow that creates VPs with different callback types and plots them.

- [ ] **Step 1: Create `test_wf_virtual_products.py`**

```python
from tests.helpers import *
import numpy as np
import pytest
from typing import Tuple
from datetime import datetime
from functools import partial


def _callback(start: float, end: float) -> Tuple[np.ndarray, np.ndarray]:
    x = np.linspace(start, end, int(end - start))
    y = np.sin(x)
    return x, y


def _callback_dt(start: datetime, end: datetime) -> Tuple[np.ndarray, np.ndarray]:
    start = datetime.timestamp(start)
    end = datetime.timestamp(end)
    x = np.linspace(start, end, int(end - start))
    y = np.sin(x)
    return x, y


def _callback_dt64(start: np.datetime64, end: np.datetime64) -> Tuple[np.ndarray, np.ndarray]:
    start = start.astype("datetime64[s]").astype(int)
    end = end.astype("datetime64[s]").astype(int)
    x = np.linspace(start, end, int(end - start))
    y = np.sin(x)
    return x, y


def _callback_scaled(scale: float, start: float, end: float) -> Tuple[np.ndarray, np.ndarray]:
    x, y = _callback(start, end)
    return x, y * scale


def _callback_scaled_dt(scale: float, start: datetime, end: datetime) -> Tuple[np.ndarray, np.ndarray]:
    x, y = _callback_dt(start, end)
    return x, y * scale


def _callback_scaled_kw_dt(start: datetime, end: datetime, scale: float = 1.0) -> Tuple[np.ndarray, np.ndarray]:
    x, y = _callback_dt(start, end)
    return x, y * scale


class _Functor:
    def __call__(self, start: float, end: float) -> Tuple[np.ndarray, np.ndarray]:
        return _callback(start, end)


@pytest.mark.parametrize(
    "vp_callback,name",
    [
        pytest.param(_callback, "float_cb", id="Regular callback"),
        pytest.param(lambda start, end: _callback(start, end), "lambda_cb", id="lambda callback"),
        pytest.param(_Functor(), "functor_cb", id="Functor callback"),
        pytest.param(_callback_dt, "dt_cb", id="Datetime callback"),
        pytest.param(_callback_dt64, "dt64_cb", id="Datetime64 callback"),
        pytest.param(partial(_callback_scaled, 2.0), "partial_cb", id="Partial function callback"),
        pytest.param(partial(_callback_scaled_dt, 2.0), "partial_dt_cb", id="Partial datetime callback"),
        pytest.param(partial(_callback_scaled_kw_dt, scale=2.0), "partial_kw_cb", id="Partial keyword callback"),
    ],
)
def test_virtual_product(main_window, qtbot, vp_callback, name):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    from SciQLop.user_api.plot import TimeRange, create_plot_panel

    vp = create_virtual_product(
        path=f"test_vp_{name}",
        callback=vp_callback,
        product_type=VirtualProductType.Scalar,
        labels=["vp"],
    )
    panel = create_plot_panel()
    panel.time_range = TimeRange(0.0, 10.0)
    plt, graph = panel.plot(vp)
    for _ in range(10):
        qtbot.wait(10)
    x, y = graph.data
    assert len(x) > 0
    assert len(y) > 0
```

Note: this keeps the parametrized approach since each VP callback variant is independent. The `main_window` fixture (module-scoped) is shared across all parametrizations in this file.

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/test_wf_virtual_products.py -v`
Expected: All 8 parametrized tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/test_wf_virtual_products.py
git commit -m "test: add virtual products workflow test"
```

### Task 6: Migrate `test_interactions.py` → `test_wf_drag_and_drop.py`

**Files:**
- Create: `tests/test_wf_drag_and_drop.py`

- [ ] **Step 1: Create `test_wf_drag_and_drop.py`**

```python
from tests.helpers import *
import os
import pytest
from PySide6.QtWidgets import QTreeView
from PySide6.QtCore import Qt


class TestDragAndDropWorkflow:
    """Open product tree, drag a product onto a plot panel."""

    @pytest.mark.skipif(
        "GITHUB_ACTIONS" in os.environ,
        reason="Drag and drop does not work in GitHub Actions",
    )
    def test_drag_product_to_panel(self, qapp, main_window, qtbot, plot_panel):
        # test_plugin is already loaded by load_all() in the main_window fixture
        from PySide6QtAds import ads

        b = main_window.dock_manager.autoHideSideBar(ads.SideBarLocation.SideBarLeft).tab(0)
        qtbot.mouseClick(b, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, b.rect().center())
        qtbot.wait(100)

        tree: QTreeView = next(
            filter(lambda c: isinstance(c, QTreeView), main_window.productTree.children())
        )
        tree.expandAll()
        qtbot.wait(100)
        model = tree.model()
        model.setFilterFixedString("TestMultiComponent")
        qtbot.wait(100)
        index = model.index(0, 0, model.index(0, 0))
        drag_and_drop(qapp, qtbot, tree, index, plot_panel._impl)
        for _ in range(10):
            qtbot.wait(10)
        assert len(plot_panel.plots) > 0
```

- [ ] **Step 2: Run**

Run: `uv run pytest tests/test_wf_drag_and_drop.py -v`
Expected: Pass (or skip on GitHub Actions).

- [ ] **Step 3: Commit**

```bash
git add tests/test_wf_drag_and_drop.py
git commit -m "test: add drag-and-drop workflow test"
```

### Task 7: Remove old test files

**Files:**
- Delete: `tests/test_creating_plots.py`
- Delete: `tests/test_virtual_products.py`
- Delete: `tests/test_interactions.py`

- [ ] **Step 1: Verify all workflow tests pass**

Run: `uv run pytest tests/test_wf_*.py -v`
Expected: All pass.

- [ ] **Step 2: Delete old files**

```bash
git rm tests/test_creating_plots.py tests/test_virtual_products.py tests/test_interactions.py
```

- [ ] **Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: All tests pass. No test was lost.

- [ ] **Step 4: Commit**

```bash
git commit -m "test: remove old integration tests replaced by workflow tests"
```

---

## Chunk 3: Migrate remaining `main_window` tests

### Task 8: Assess and migrate remaining tests that use `main_window`

**Files that still use `main_window`** (not yet migrated):
- `tests/test_vp_debug_workbench.py`
- `tests/test_vp_magic_integration.py`
- `tests/test_command_palette_integration.py`
- `tests/test_command_palette_arg_types.py`
- `tests/test_speasy_plot_backend.py`

These tests already exist and work. They just need to be verified with the new module-scoped `main_window` fixture.

- [ ] **Step 1: Run each file to verify compatibility with module-scoped fixture**

Run: `uv run pytest tests/test_vp_debug_workbench.py tests/test_vp_magic_integration.py tests/test_command_palette_integration.py tests/test_command_palette_arg_types.py tests/test_speasy_plot_backend.py -v`

Expected: All pass. If any fail due to state leaking between tests in the same module, they need to be organized into workflow classes or adjusted.

- [ ] **Step 2: Fix any failures**

For each failing test file:
- If tests conflict due to shared state, wrap them in a workflow class and add cleanup between tests
- If a test mutates global state that other tests depend on, add the appropriate setup/teardown

- [ ] **Step 3: Commit any fixes**

```bash
git add tests/
git commit -m "test: fix remaining tests for module-scoped main_window"
```

---

## Chunk 4: Verification

### Task 9: Full test suite verification

- [ ] **Step 1: Run the complete test suite**

Run: `uv run pytest -v`
Expected: All tests pass.

- [ ] **Step 2: Verify filesystem isolation**

Run: `ls ~/.config/sciqlop/ 2>/dev/null && echo "FAIL: wrote to real config" || echo "OK: config clean"`
Expected: `OK: config clean` (or the directory doesn't exist / has no new files from this run).

- [ ] **Step 3: Measure timing improvement**

Run: `uv run pytest tests/test_wf_plot_and_navigate.py tests/test_wf_virtual_products.py tests/test_wf_drag_and_drop.py -v --durations=0`
Expected: Total time dominated by a single ~7s startup per file, not per test.

- [ ] **Step 4: Commit any final adjustments**

```bash
git add -A
git commit -m "test: complete test rework migration"
```
