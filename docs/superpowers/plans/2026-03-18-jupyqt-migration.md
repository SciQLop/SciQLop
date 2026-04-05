# jupyqt Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace SciQLop's ipykernel/qasync/ZMQ kernel stack with jupyqt, eliminating reentrancy crashes, UI freezes, and accumulated workarounds.

**Architecture:** A new thin `KernelManager` wraps `jupyqt.EmbeddedJupyter`. The blocking event loop call moves from deep inside `KernelManager.start()` up to `sciqlop_app.py:main()`. All `pause_kernel_poller()` call sites are cleaned up. External QtConsole/JupyterLab process spawning is removed. The `SciQLop/Jupyter/` provisioner package is deleted entirely.

**Tech Stack:** jupyqt, PySide6, qasync (kept for app event loop), IPython

**Spec:** `docs/superpowers/specs/2026-03-18-jupyqt-migration-design.md`

---

## File Map

### Files to create/rewrite
- `SciQLop/components/jupyter/kernel/manager.py` — rewrite: thin wrapper around `EmbeddedJupyter`
- `SciQLop/components/jupyter/kernel/__init__.py` — rewrite: re-export `KernelManager` only

### Files to modify
- `pyproject.toml` — dependency changes + remove entry point
- `SciQLop/sciqlop_dependencies.py` — mirror dependency changes (auto-generated, but we update it)
- `SciQLop/sciqlop_app.py:90-95` — add `sciqlop_event_loop().exec()` after `main_windows.start()`
- `SciQLop/core/ui/mainwindow.py:14,108-111,186-195,392` — remove JupyterLabView, jupyterlab_started, new_qt_console menu
- `SciQLop/components/workspaces/backend/workspaces_manager.py:15,76,83-88,92-93,118-128,201-206,209` — remove ClientsManager, simplify start/shutdown, add widget/open_in_browser, wrap_qt for Qt objects
- `SciQLop/components/workspaces/ui/workspace_manager_ui.py:9,15,32-33` — remove jupyterlab_started, new_qt_console
- `SciQLop/user_api/magics/completions.py:35,45` — remove pause_kernel_poller
- `SciQLop/components/command_palette/arg_types.py:52,59` — remove pause_kernel_poller
- `SciQLop/user_api/virtual_products/magic.py:277,281` — remove pause_kernel_poller
- `tests/test_command_palette_harvester.py:45,50,54` — update "Start jupyter console" references

### Files to delete
- `SciQLop/components/jupyter/jupyter_clients/` — entire directory
- `SciQLop/components/jupyter/ui/JupyterLabView.py` — replaced by jupyqt widget
- `SciQLop/Jupyter/` — entire directory (provisioner, lab_kernel_manager, entry_points.txt)
- `tests/test_kernel_poller.py` — tests deleted class
- `tests/test_jupyter_clients_cleanup.py` — tests deleted class
- `tests/test_kernel_manager.py` — tests old KernelManager internals (rewrite in Task 2)

---

### Task 1: Update dependencies and delete dead modules

**Files:**
- Modify: `pyproject.toml`
- Modify: `SciQLop/sciqlop_dependencies.py`
- Delete: `SciQLop/Jupyter/` (entire directory)
- Delete: `SciQLop/components/jupyter/jupyter_clients/` (entire directory)
- Delete: `SciQLop/components/jupyter/ui/JupyterLabView.py`
- Delete: `tests/test_kernel_poller.py`
- Delete: `tests/test_jupyter_clients_cleanup.py`
- Delete: `tests/test_kernel_manager.py`

- [ ] **Step 1: Update pyproject.toml dependencies**

Remove these lines from the `dependencies` array:
```
    "ipykernel==6.29.5",
    "jupyter_client==8.6.3",
    "jupyter_core==5.8.1",
    "jupyter_server==2.16.0",
    "jupyter_server_terminals==0.5.3",
    "jupyterlab==4.4.4",
    "jupyterlab_pygments==0.3.0",
    "jupyterlab_server==2.27.3",
    "jupyterlab_widgets==3.0.15",
    "notebook==7.4.4",
    "notebook_shim==0.2.4",
    "pyzmq==27.0.0",
    "jupyter-events==0.12.0",
    "jupyter-lsp==2.2.5",
    "tornado==6.5.1",
    "ipympl==0.9.7",
    "ipywidgets==8.1.7",
    "matplotlib-inline==0.1.7",
```

Add:
```
    "jupyqt",
```

Keep: `ipython==8.37.0`, `qtconsole`, `qasync`.

Note: `jupyter_client`, `pyzmq`, `jupyter_core` are kept as transitive deps of `qtconsole` — we just remove the explicit pins. `ipympl`, `ipywidgets`, `matplotlib-inline`, `notebook`, `notebook_shim`, `jupyter-events`, `jupyter-lsp`, `tornado` were only needed for the old jupyterlab server stack.

- [ ] **Step 2: Remove entry point from pyproject.toml**

Delete these lines (95-96):
```toml
[project.entry-points."jupyter_client.kernel_provisioners"]
sciqlop-kernel-provisioner = "SciQLop.Jupyter:SciQLopProvisioner"
```

- [ ] **Step 3: Update sciqlop_dependencies.py**

Mirror the dependency changes. Remove the same packages from the `RUNTIME_DEPENDENCIES` list and add `"jupyqt"`.

- [ ] **Step 4: Delete the Jupyter provisioner directory**

```bash
rm -rf SciQLop/Jupyter/
```

- [ ] **Step 5: Delete the jupyter_clients directory**

```bash
rm -rf SciQLop/components/jupyter/jupyter_clients/
```

- [ ] **Step 6: Delete JupyterLabView.py**

```bash
rm SciQLop/components/jupyter/ui/JupyterLabView.py
```

- [ ] **Step 7: Delete obsolete test files**

```bash
rm tests/test_kernel_poller.py tests/test_jupyter_clients_cleanup.py tests/test_kernel_manager.py
```

- [ ] **Step 8: Commit**

> **Warning:** After this commit, the codebase is in an unrunnable state — `kernel/__init__.py` and `kernel/manager.py` still import deleted modules (ipykernel, jupyter_clients). Do NOT run tests until Task 2 is complete.

```bash
git add -A
git commit -m "chore: remove ipykernel/ZMQ stack, add jupyqt dependency

Delete SciQLop/Jupyter/ provisioner, jupyter_clients/, JupyterLabView,
and their tests. Update pyproject.toml dependencies.

NOTE: kernel/__init__.py and manager.py still reference deleted modules.
Task 2 rewrites them immediately."
```

---

### Task 2: Rewrite KernelManager as jupyqt wrapper

**Files:**
- Rewrite: `SciQLop/components/jupyter/kernel/__init__.py`
- Rewrite: `SciQLop/components/jupyter/kernel/manager.py`
- Create: `tests/test_kernel_manager.py` (new tests)

- [ ] **Step 1: Write failing test for new KernelManager**

Create `tests/test_kernel_manager.py`.

Note: Use `qapp` from pytest-qt (provided via `qapp_cls` fixture in `conftest.py`). The `KernelManager` constructor creates `EmbeddedJupyter()` which needs a QApplication.

```python
"""Tests for the new jupyqt-based KernelManager."""


def test_kernel_manager_has_shell(qapp):
    from SciQLop.components.jupyter.kernel.manager import KernelManager
    km = KernelManager()
    assert km.shell is not None


def test_kernel_manager_push_before_start(qapp):
    from SciQLop.components.jupyter.kernel.manager import KernelManager
    km = KernelManager()
    km.push_variables({"test_var": 42})
    assert km.shell.user_ns["test_var"] == 42


def test_kernel_manager_wrap_qt(qapp):
    from SciQLop.components.jupyter.kernel.manager import KernelManager
    from PySide6.QtWidgets import QLabel
    km = KernelManager()
    label = QLabel("test")
    proxy = km.wrap_qt(label)
    assert proxy is not None


def test_kernel_manager_shutdown(qapp):
    from SciQLop.components.jupyter.kernel.manager import KernelManager
    km = KernelManager()
    km.start()
    km.shutdown()
    # Should not raise — clean shutdown
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_kernel_manager.py -v`
Expected: FAIL (old KernelManager doesn't have these methods/behavior)

- [ ] **Step 3: Rewrite kernel/__init__.py**

Replace `SciQLop/components/jupyter/kernel/__init__.py` with:
```python
from .manager import KernelManager
```

- [ ] **Step 4: Rewrite kernel/manager.py**

Replace `SciQLop/components/jupyter/kernel/manager.py` with:
```python
from jupyqt import EmbeddedJupyter
from PySide6.QtCore import QObject
from SciQLop.user_api.magics import register_all_magics


class KernelManager(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._jupyter = EmbeddedJupyter()
        register_all_magics(self._jupyter.shell)

    @property
    def shell(self):
        return self._jupyter.shell

    def start(self, port=0):
        self._jupyter.start(port=port)

    def push_variables(self, variables: dict):
        self._jupyter.push(variables)

    def wrap_qt(self, obj):
        return self._jupyter.wrap_qt(obj)

    def widget(self):
        return self._jupyter.widget()

    def open_in_browser(self):
        self._jupyter.open_in_browser()

    def shutdown(self):
        self._jupyter.shutdown()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_kernel_manager.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/jupyter/kernel/__init__.py SciQLop/components/jupyter/kernel/manager.py tests/test_kernel_manager.py
git commit -m "feat: rewrite KernelManager as thin jupyqt wrapper"
```

---

### Task 3: Update WorkspaceManager and WorkspaceManagerUI

**Files:**
- Modify: `SciQLop/components/workspaces/backend/workspaces_manager.py`
- Modify: `SciQLop/components/workspaces/ui/workspace_manager_ui.py`

- [ ] **Step 1: Update WorkspaceManager**

In `SciQLop/components/workspaces/backend/workspaces_manager.py`:

Remove line 15 import of `KernelManager` and replace with:
```python
from SciQLop.components.jupyter.kernel import KernelManager
```
(Same import path, just confirming it still works with new module.)

Remove lines 76, 88 (the `jupyterlab_started` signal and its connection):
```python
# Delete this signal declaration:
    jupyterlab_started = Signal(str)
# Delete this connection:
        self._kernel_manager.jupyterlab_started.connect(self.jupyterlab_started)
```

Remove the quickstart shortcut registration (lines 83-85) and replace with:
```python
        sciqlop_app().add_quickstart_shortcut("JupyterLab", "Open JupyterLab in browser",
                                              Icons.get_icon("Jupyter"),
                                              self.open_in_browser)
```

Remove `_init_kernel` method (lines 92-93).

Remove dead icon registration (line 22):
```python
# Delete:
register_icon("JupyterConsole", lambda: QIcon("://icons/JupyterConsole.png"))
```

Replace `start_jupyterlab` method (lines 118-123) with:
```python
    def open_in_browser(self):
        self._kernel_manager.open_in_browser()

    def widget(self):
        return self._kernel_manager.widget()
```

Remove `new_qt_console` method (lines 125-128).

Update `start` method (lines 204-206) — remove `sciqlop_event_loop` blocking:
```python
    def start(self):
        self.push_variables({
            "app": self._kernel_manager.wrap_qt(sciqlop_app()),
            "background_run": background_run,
        })
        self._kernel_manager.start()
```

In `load_workspace` (line 169), remove `self.start_jupyterlab()` entirely. The browser opening only works after `start()` has been called (jupyqt's server must be running). For non-default workspaces that auto-started JupyterLab, the embedded widget in the dock is sufficient — no separate browser launch needed on load.

```python
        # Delete these lines from load_workspace():
        if not manifest.default:
            self.start_jupyterlab()
```

- [ ] **Step 2: Update WorkspaceManagerUI**

In `SciQLop/components/workspaces/ui/workspace_manager_ui.py`:

Remove the `jupyterlab_started` signal (line 9) and its connection (line 15).

Remove `new_qt_console` method (lines 32-33).

Add delegation methods:
```python
    def widget(self):
        return workspaces_manager_instance().widget()

    def open_in_browser(self):
        workspaces_manager_instance().open_in_browser()

    def wrap_qt(self, obj):
        return workspaces_manager_instance()._kernel_manager.wrap_qt(obj)
```

- [ ] **Step 3: Run existing tests**

Run: `uv run pytest tests/ -v -x`
Expected: Some tests may fail due to mainwindow changes not yet done — that's OK, we fix those in Task 4.

- [ ] **Step 4: Commit**

```bash
git add SciQLop/components/workspaces/backend/workspaces_manager.py SciQLop/components/workspaces/ui/workspace_manager_ui.py
git commit -m "refactor: simplify WorkspaceManager for jupyqt

Remove ClientsManager, QtConsole, JupyterLab process spawning.
KernelManager.start() is now non-blocking. Qt objects wrapped with
wrap_qt() for thread safety."
```

---

### Task 4: Update MainWindow and startup flow

**Files:**
- Modify: `SciQLop/core/ui/mainwindow.py`
- Modify: `SciQLop/sciqlop_app.py`

- [ ] **Step 1: Update mainwindow.py**

Remove the `JupyterLabView` import (line 14):
```python
# Delete:
from SciQLop.components.jupyter.ui.JupyterLabView import JupyterLabView
```

In `_setup_ui()`, remove/replace these lines:

Line 106 — wrap `main_window` with `wrap_qt` (uses the delegation method added in Task 3):
```python
        # Old:
        self.workspace_manager.pushVariables({"main_window": self})
        # New:
        self.workspace_manager.pushVariables({"main_window": self.workspace_manager.wrap_qt(self)})
```

Lines 108-109 — remove JupyterLabView reference and jupyterlab_started connection:
```python
# Delete:
        self._jupyterlab_view: Optional[JupyterLabView] = None
        self.workspace_manager.jupyterlab_started.connect(self._on_jupyterlab_started)
```

Line 111 — replace "Start jupyter console" with "Open JupyterLab in browser":
```python
        # Old:
        self.toolsMenu.addAction("Start jupyter console", self.workspace_manager.new_qt_console)
        # New:
        self.toolsMenu.addAction("Open JupyterLab in browser", self.workspace_manager.open_in_browser)
```

Delete the `_on_jupyterlab_started` method entirely (lines 186-195).

In `start()` method (lines 395-396), add widget docking after workspace start:
```python
    def start(self):
        self.workspace_manager.start()
        jupyter_widget = self.workspace_manager.widget()
        if jupyter_widget is not None:
            jupyter_widget.setWindowTitle("SciQLop JupyterLab")
            self.addWidgetIntoDock(QtAds.DockWidgetArea.TopDockWidgetArea, jupyter_widget,
                                   size_hint_from_content=False)
```

- [ ] **Step 2: Update sciqlop_app.py startup flow**

In `sciqlop_app.py`, modify `main()` (lines 90-95):
```python
def main():
    main_windows = start_sciqlop()
    try:
        main_windows.start()
    except Exception as e:
        print(e)
    from SciQLop.core.sciqlop_application import sciqlop_event_loop
    sciqlop_event_loop().exec()
```

The `__main__` block (lines 98-105) remains unchanged — it runs after `main()` returns (when the event loop exits) and handles exit codes. This is correct because `main()` now blocks on `sciqlop_event_loop().exec()` just as before, except the blocking point moved from inside `KernelManager.start()` to here.

- [ ] **Step 3: Run tests**

Run: `uv run pytest tests/ -v -x`
Expected: Most tests pass. Test failures from harvester test addressed in Task 6.

- [ ] **Step 4: Commit**

```bash
git add SciQLop/core/ui/mainwindow.py SciQLop/sciqlop_app.py
git commit -m "refactor: restructure startup flow for jupyqt

Event loop blocking moves from KernelManager to sciqlop_app.main().
JupyterLab widget docked directly, QtConsole menu replaced with
Open in Browser action."
```

---

### Task 5: Remove pause_kernel_poller from all call sites

**Files:**
- Modify: `SciQLop/user_api/magics/completions.py`
- Modify: `SciQLop/components/command_palette/arg_types.py`
- Modify: `SciQLop/user_api/virtual_products/magic.py`

- [ ] **Step 1: Clean up completions.py**

In `SciQLop/user_api/magics/completions.py`, remove the import (line 35), the unused `QEventLoop` import (line 34), and unwrap the context manager (lines 45):

Before:
```python
    from SciQLop.components.jupyter.kernel.manager import pause_kernel_poller
    ...
        with pause_kernel_poller():
            prev_count = -1
            ...
```

After:
```python
    # Remove the import entirely
    # Remove `with pause_kernel_poller():` — keep the body at original indent
        prev_count = -1
        stable_rounds = 0
        for _ in range(500):
            app.processEvents()
            ...
```

The full `_complete_products` function becomes:
```python
def _complete_products(prefix: str, max_results: int = 20) -> list[str]:
    """Fuzzy-match product paths using ProductsFlatFilterModel."""
    from SciQLopPlots import ProductsModel, ProductsFlatFilterModel, QueryParser
    from PySide6.QtWidgets import QApplication

    flat = ProductsFlatFilterModel(ProductsModel.instance())
    flat.set_query(QueryParser.parse(prefix))

    app = QApplication.instance()
    if app:
        prev_count = -1
        stable_rounds = 0
        for _ in range(500):
            app.processEvents()
            cur = flat.rowCount()
            if cur == prev_count:
                stable_rounds += 1
                if stable_rounds >= 3:
                    break
            else:
                stable_rounds = 0
                prev_count = cur

    count = min(flat.rowCount(), max_results)
    if count == 0:
        return []
    indexes = [flat.index(i, 0) for i in range(count)]
    mime = flat.mimeData(indexes)
    if mime and mime.text():
        return [_normalize_product_path(path.strip()) for path in mime.text().strip().split("\n") if path.strip()]
    return []
```

- [ ] **Step 2: Clean up arg_types.py**

In `SciQLop/components/command_palette/arg_types.py`, remove the import (line 52) and unwrap the context manager (line 59):

The `filtered_completions` method becomes:
```python
    def filtered_completions(self, query: str, context: dict, max_results: int) -> list[Completion]:
        from SciQLopPlots import QueryParser, ProductsModel
        from PySide6.QtWidgets import QApplication

        flat = self._ensure_flat_model()
        flat.set_query(QueryParser.parse(query))

        app = QApplication.instance()
        if app:
            prev_count = -1
            stable_rounds = 0
            for _ in range(500):
                app.processEvents()
                cur = flat.rowCount()
                if cur == prev_count:
                    stable_rounds += 1
                    if stable_rounds >= 3:
                        break
                else:
                    stable_rounds = 0
                    prev_count = cur

        items = []
        count = min(flat.rowCount(), max_results)
        if count > 0:
            indexes = [flat.index(i, 0) for i in range(count)]
            mime = flat.mimeData(indexes)
            if mime and mime.text():
                for path_text in mime.text().strip().split("\n"):
                    product_path = _normalize_product_path(path_text)
                    description = _node_stable_id(ProductsModel, product_path)
                    items.append(Completion(value=product_path, display=product_path, description=description))
        return items
```

- [ ] **Step 3: Clean up virtual_products/magic.py**

In `SciQLop/user_api/virtual_products/magic.py`, update `_run_in_thread_blocking` (lines 269-286):

Remove the `pause_kernel_poller` import and context manager:
```python
def _run_in_thread_blocking(func, *args):
    """Run func(*args) in a thread, pumping Qt events until done."""
    from concurrent.futures import ThreadPoolExecutor
    from SciQLop.core.sciqlop_application import sciqlop_app

    app = sciqlop_app()
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(func, *args)
        while not future.done():
            app.processEvents()
        return future.result()
```

- [ ] **Step 4: Run magic/completion tests**

Run: `uv run pytest tests/test_magics/ tests/test_plot_pure_logic.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/magics/completions.py SciQLop/components/command_palette/arg_types.py SciQLop/user_api/virtual_products/magic.py
git commit -m "cleanup: remove pause_kernel_poller from all call sites

No longer needed — jupyqt runs the kernel on its own thread,
so there is no poller on the Qt main thread to cause reentrancy."
```

---

### Task 6: Update test fixtures and harvester test

**Files:**
- Modify: `tests/test_command_palette_harvester.py:45,50,54`

- [ ] **Step 1: Update harvester test**

In `tests/test_command_palette_harvester.py`, update the "Start jupyter console" references to "Open JupyterLab in browser":

Line 45:
```python
    action = QAction("Open JupyterLab in browser", win)
```

Line 50:
```python
        callback=lambda: None, replaces_qaction="Open JupyterLab in browser",
```

Line 54:
```python
    assert "Open JupyterLab in browser" not in names
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/test_command_palette_harvester.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_command_palette_harvester.py
git commit -m "test: update harvester test for renamed menu action"
```

---

### Task 7: Full test suite and smoke test

- [ ] **Step 1: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: All tests PASS

- [ ] **Step 2: Fix any remaining failures**

Address any import errors or broken references found by the test suite.

- [ ] **Step 3: Manual smoke test checklist**

If possible (requires display), launch the app and verify:
- [ ] App starts without errors
- [ ] JupyterLab widget appears in the dock
- [ ] Can run a cell in JupyterLab
- [ ] `%plot` magic works with tab completion
- [ ] `%%vp` magic works
- [ ] "Open JupyterLab in browser" menu action works
- [ ] App closes cleanly

- [ ] **Step 4: Final commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: address remaining test failures from jupyqt migration"
```
