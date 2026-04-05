# Jupyter Integration Improvements — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve the Jupyter/IPython kernel integration by making the poller adaptive, hardening shutdown, extracting a proper KernelManager, and cleaning up file organization.

**Architecture:** The kernel stays in-process on the Qt main thread (via qasync). We replace the fixed-interval QTimer poller with an adaptive one, replace `run_cell("quit()")` with proper `do_shutdown()`, and extract kernel lifecycle management from `WorkspaceManager` into a dedicated `KernelManager` class.

**Tech Stack:** PySide6, qasync, ipykernel, jupyter_client, QProcess

---

### Task 1: Rename `IPythonKernel/` to `kernel/` and update imports

**Files:**
- Rename: `SciQLop/components/jupyter/IPythonKernel/` → `SciQLop/components/jupyter/kernel/`
- Modify: `SciQLop/components/workspaces/backend/workspaces_manager.py:14`

**Step 1: Rename the directory**

```bash
cd /var/home/jeandet/Documents/prog/SciQLop
git mv SciQLop/components/jupyter/IPythonKernel SciQLop/components/jupyter/kernel
```

**Step 2: Update the import in workspaces_manager.py**

Change line 14 from:
```python
from SciQLop.components.jupyter.IPythonKernel import InternalIPKernel
```
to:
```python
from SciQLop.components.jupyter.kernel import InternalIPKernel
```

**Step 3: Search for any other imports of the old path**

```bash
uv run python -c "from SciQLop.components.jupyter.kernel import InternalIPKernel; print('OK')"
```

Expected: `OK`

**Step 4: Commit**

```bash
git add -A && git commit -m "refactor(jupyter): rename IPythonKernel/ to kernel/"
```

---

### Task 2: Adaptive kernel poller

**Files:**
- Modify: `SciQLop/components/jupyter/kernel/__init__.py`
- Test: `tests/test_kernel_poller.py`

**Step 1: Write the test for adaptive polling behavior**

Create `tests/test_kernel_poller.py`:

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from PySide6.QtCore import QTimer


@pytest.fixture
def mock_kernel():
    kernel = MagicMock()
    kernel.do_one_iteration = AsyncMock(return_value=None)
    return kernel


def test_poller_starts_with_fast_interval(qtbot, mock_kernel):
    from SciQLop.components.jupyter.kernel import _KernelPoller
    poller = _KernelPoller(kernel=mock_kernel, fast_interval=0.005, slow_interval=0.05)
    assert poller._current_interval == poller._fast_interval


def test_poller_has_no_is_iterating_guard(qtbot, mock_kernel):
    """The _is_iterating flag was removed — @asyncSlot handles serialization."""
    from SciQLop.components.jupyter.kernel import _KernelPoller
    poller = _KernelPoller(kernel=mock_kernel)
    assert not hasattr(poller, '_is_iterating')
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_kernel_poller.py -v
```

Expected: FAIL (poller still has old interface)

**Step 3: Rewrite `_KernelPoller` with adaptive polling**

Replace the `_KernelPoller` class in `SciQLop/components/jupyter/kernel/__init__.py`:

```python
class _KernelPoller(QObject):
    def __init__(self, kernel: IPythonKernel, fast_interval: float = 0.005, slow_interval: float = 0.05):
        super().__init__()
        assert kernel is not None
        self.kernel = kernel
        self._fast_interval = fast_interval
        self._slow_interval = slow_interval
        self._current_interval = fast_interval
        self.timer = QTimer()
        if hasattr(self.kernel, "do_one_iteration"):
            self.timer.timeout.connect(self._poll_kernel_do_one_iteration)
        else:
            self.timer.timeout.connect(self._poll_kernel_flush)

    def start(self):
        self.timer.start(int(1000 * self._current_interval))

    def stop(self):
        self.timer.stop()

    def _set_interval(self, interval: float):
        if interval != self._current_interval:
            self._current_interval = interval
            self.timer.setInterval(int(1000 * interval))

    @asyncSlot()
    async def _poll_kernel_do_one_iteration(self):
        try:
            await self.kernel.do_one_iteration()
            self._set_interval(self._fast_interval)
        except Exception:
            log.exception("Error while polling IPython kernel")
            self._set_interval(self._slow_interval)

    @asyncSlot()
    async def _poll_kernel_flush(self):
        from ipykernel.eventloops import get_shell_stream
        get_shell_stream(self.kernel).flush(limit=1)
```

Note: `do_one_iteration()` doesn't tell us whether it processed messages. For now, we go fast after success and slow after errors. A more sophisticated approach would inspect ZMQ socket state, but that fights ipykernel internals.

**Step 4: Run tests**

```bash
uv run pytest tests/test_kernel_poller.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/components/jupyter/kernel/__init__.py tests/test_kernel_poller.py
git commit -m "feat(jupyter): adaptive kernel poller, remove _is_iterating guard"
```

---

### Task 3: Harden subprocess cleanup in ClientsManager

**Files:**
- Modify: `SciQLop/components/jupyter/jupyter_clients/clients_manager.py`
- Test: `tests/test_jupyter_clients_cleanup.py`

**Step 1: Write the test**

Create `tests/test_jupyter_clients_cleanup.py`:

```python
import pytest
from unittest.mock import MagicMock, call
from PySide6.QtCore import QProcess


def make_mock_client(still_running_after_terminate=False):
    client = MagicMock()
    client.state.return_value = QProcess.ProcessState.Running

    def fake_wait(timeout=-1):
        if still_running_after_terminate:
            return False  # didn't finish in time
        return True

    client.waitForFinished = MagicMock(side_effect=fake_wait)
    return client


def test_cleanup_terminates_before_kill(qtbot):
    from SciQLop.components.jupyter.jupyter_clients.clients_manager import ClientsManager
    mgr = ClientsManager(connection_file="/tmp/fake.json")
    client = make_mock_client(still_running_after_terminate=False)
    mgr._jupyter_processes.append(client)

    mgr.cleanup()

    client.terminate.assert_called_once()
    client.kill.assert_not_called()


def test_cleanup_escalates_to_kill_on_timeout(qtbot):
    from SciQLop.components.jupyter.jupyter_clients.clients_manager import ClientsManager
    mgr = ClientsManager(connection_file="/tmp/fake.json")
    client = make_mock_client(still_running_after_terminate=True)
    mgr._jupyter_processes.append(client)

    mgr.cleanup()

    client.terminate.assert_called_once()
    client.kill.assert_called_once()
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_jupyter_clients_cleanup.py -v
```

Expected: FAIL (cleanup still calls `kill()` directly)

**Step 3: Update `ClientsManager.cleanup()`**

In `SciQLop/components/jupyter/jupyter_clients/clients_manager.py`, replace the `cleanup` method:

```python
def cleanup(self):
    """Clean up the consoles. Terminate gracefully, escalate to kill."""
    for c in self._jupyter_processes:
        if c.state() is QProcess.ProcessState.Running:
            c.terminate()
            if not c.waitForFinished(3000):
                c.kill()
                c.waitForFinished(1000)
```

Also need to add `terminate` and `waitForFinished` delegation in `SciQLopJupyterClient` (`jupyter_client_process.py`):

```python
def terminate(self):
    self.process.terminate()

def waitForFinished(self, msecs=-1):
    return self.process.waitForFinished(msecs)
```

**Step 4: Run tests**

```bash
uv run pytest tests/test_jupyter_clients_cleanup.py -v
```

Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/components/jupyter/jupyter_clients/clients_manager.py \
        SciQLop/components/jupyter/jupyter_clients/jupyter_client_process.py \
        tests/test_jupyter_clients_cleanup.py
git commit -m "fix(jupyter): graceful subprocess shutdown with timeout escalation"
```

---

### Task 4: Extract KernelManager from WorkspaceManager

**Files:**
- Create: `SciQLop/components/jupyter/kernel/manager.py`
- Modify: `SciQLop/components/jupyter/kernel/__init__.py` (re-export)
- Modify: `SciQLop/components/workspaces/backend/workspaces_manager.py`
- Test: `tests/test_kernel_manager.py`

**Step 1: Write the test**

Create `tests/test_kernel_manager.py`:

```python
import pytest
from unittest.mock import MagicMock, patch


def test_kernel_manager_defers_variables_before_init():
    from SciQLop.components.jupyter.kernel.manager import KernelManager
    km = KernelManager()
    km.push_variables({"x": 42})
    assert km._deferred_variables == {"x": 42}


def test_kernel_manager_shutdown_stops_poller():
    from SciQLop.components.jupyter.kernel.manager import KernelManager
    km = KernelManager()
    km._poller = MagicMock()
    km._kernel_app = MagicMock()
    km._clients = MagicMock()

    km.shutdown()

    km._clients.cleanup.assert_called_once()
    km._poller.stop.assert_called_once()
    km._kernel_app.kernel.do_shutdown.assert_called_once()
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_kernel_manager.py -v
```

Expected: FAIL (module doesn't exist)

**Step 3: Create `KernelManager`**

Create `SciQLop/components/jupyter/kernel/manager.py`:

```python
from typing import Optional
from PySide6.QtCore import QObject, Signal

from SciQLop.components.jupyter.kernel import InternalIPKernel, _KernelPoller, SciQLopKernelApp
from SciQLop.components.jupyter.jupyter_clients.clients_manager import ClientsManager
from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.sciqlop_application import sciqlop_event_loop

log = getLogger(__name__)


class KernelManager(QObject):
    """Owns the full IPython kernel lifecycle: init, start, push_variables, shutdown."""
    jupyterlab_started = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._kernel: Optional[InternalIPKernel] = None
        self._kernel_app: Optional[SciQLopKernelApp] = None
        self._poller: Optional[_KernelPoller] = None
        self._clients: Optional[ClientsManager] = None
        self._deferred_variables: dict = {}
        self._initialized = False

    def init(self):
        if self._initialized:
            return
        self._kernel = InternalIPKernel()
        self._kernel.init_ipkernel()
        self._kernel_app = self._kernel.ipykernel
        self._clients = ClientsManager(self._kernel.connection_file, parent=self)
        self._clients.jupyterlab_started.connect(self.jupyterlab_started)
        self._flush_deferred_variables()
        self._initialized = True

    def _flush_deferred_variables(self):
        if self._deferred_variables:
            self._kernel.push_variables(self._deferred_variables)
            self._deferred_variables.clear()

    def start(self):
        if not self._initialized:
            self.init()
        self._kernel_app.kernel.start()
        self._poller = _KernelPoller(kernel=self._kernel_app.kernel)
        self._poller.start()
        sciqlop_event_loop().exec()

    def push_variables(self, variable_dict: dict):
        if not self._initialized:
            self._deferred_variables.update(variable_dict)
        else:
            self._kernel.push_variables(variable_dict)

    def shutdown(self):
        if not self._initialized:
            return
        if self._clients:
            self._clients.cleanup()
        if self._poller:
            self._poller.stop()
        if self._kernel_app and self._kernel_app.kernel:
            self._kernel_app.kernel.do_shutdown()

    @property
    def connection_file(self) -> Optional[str]:
        if self._kernel:
            return self._kernel.connection_file
        return None

    @property
    def clients(self) -> Optional[ClientsManager]:
        return self._clients

    @property
    def is_initialized(self) -> bool:
        return self._initialized
```

**Step 4: Update `kernel/__init__.py` to re-export**

Add at the end of `SciQLop/components/jupyter/kernel/__init__.py`:

```python
from .manager import KernelManager
```

**Step 5: Run tests**

```bash
uv run pytest tests/test_kernel_manager.py -v
```

Expected: PASS

**Step 6: Commit**

```bash
git add SciQLop/components/jupyter/kernel/manager.py \
        SciQLop/components/jupyter/kernel/__init__.py \
        tests/test_kernel_manager.py
git commit -m "refactor(jupyter): extract KernelManager from WorkspaceManager"
```

---

### Task 5: Wire KernelManager into WorkspaceManager

**Files:**
- Modify: `SciQLop/components/workspaces/backend/workspaces_manager.py`

**Step 1: Refactor WorkspaceManager to delegate to KernelManager**

Replace kernel-related code in `workspaces_manager.py`. The key changes:

- Remove `_ipykernel` and `_ipykernel_clients_manager` fields
- Add `_kernel_manager: KernelManager` field
- Replace `_init_kernel()` with `self._kernel_manager.init()`
- Replace `quit()` with `self._kernel_manager.shutdown()`
- Replace `push_variables()` delegation
- Replace `start()` delegation

Update imports — change:
```python
from SciQLop.components.jupyter.IPythonKernel import InternalIPKernel
from SciQLop.components.jupyter.jupyter_clients.clients_manager import ClientsManager as IPythonKernelClientsManager
```
to:
```python
from SciQLop.components.jupyter.kernel import KernelManager
```

Replace the `__init__`, `_init_kernel`, `start_jupyterlab`, `new_qt_console`, `push_variables`, `start`, and `quit` methods:

```python
class WorkspaceManager(QObject):
    workspace_loaded = Signal(Workspace)
    jupyterlab_started = Signal(str)

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self._quit = False
        self._workspace: Optional[Workspace] = None
        self._kernel_manager = KernelManager(parent=self)
        self._kernel_manager.jupyterlab_started.connect(self.jupyterlab_started)

        sciqlop_app().add_quickstart_shortcut("JupyterLab", "Start JupyterLab in current workspace or a new one",
                                              Icons.get_icon("Jupyter"),
                                              self.start_jupyterlab)

        self._default_workspace: WorkspaceSpecFile = self._ensure_default_workspace_exists()

    def start_jupyterlab(self):
        self._kernel_manager.init()
        w = self.workspace
        self._kernel_manager.clients.start_jupyterlab(cwd=w.workspace_dir)

    def new_qt_console(self):
        self._kernel_manager.init()
        w = self.workspace
        self._kernel_manager.clients.new_qt_console(cwd=w.workspace_dir)

    def push_variables(self, variable_dict):
        self._kernel_manager.push_variables(variable_dict)

    def start(self):
        self._kernel_manager.push_variables({"app": sciqlop_app(), "background_run": background_run})
        self._kernel_manager.start()

    def quit(self):
        self._kernel_manager.shutdown()
        self._quit = True
```

Note: `create_workspace`, `load_workspace`, `load_example` no longer call `_init_kernel()` directly — `start_jupyterlab` calls `self._kernel_manager.init()` which is idempotent.

**Step 2: Also update `SciQLopKernelApp.start()`**

In `SciQLop/components/jupyter/kernel/__init__.py`, simplify `SciQLopKernelApp.start()` — the poller creation and event loop exec are now in `KernelManager.start()`:

```python
class SciQLopKernelApp(IPKernelApp):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def start(self):
        if self.subapp is not None:
            return self.subapp.start()
        if self.poller is not None:
            self.poller.start()
```

**Step 3: Run existing tests to check nothing broke**

```bash
uv run pytest tests/ -v --timeout=30
```

Expected: All existing tests PASS

**Step 4: Commit**

```bash
git add SciQLop/components/workspaces/backend/workspaces_manager.py \
        SciQLop/components/jupyter/kernel/__init__.py
git commit -m "refactor(jupyter): wire KernelManager into WorkspaceManager"
```

---

### Task 6: Clean up `SciQLopKernelApp` and `InternalIPKernel`

**Files:**
- Modify: `SciQLop/components/jupyter/kernel/__init__.py`

**Step 1: Simplify InternalIPKernel**

`InternalIPKernel` is now just a thin wrapper. Simplify it — the `start()` method is no longer needed (KernelManager handles that). Remove the commented-out `do_one_iteration` method.

```python
class InternalIPKernel(QObject):
    """Internal ipykernel manager."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ipykernel: Optional[SciQLopKernelApp] = None

    def init_ipkernel(self):
        self.ipykernel = SciQLopKernelApp.instance(kernel_name="SciQLop",
                                                   kernel_class=SciQLopKernel)
        self.ipykernel.capture_fd_output = False
        self.ipykernel.initialize()

    def push_variables(self, variable_dict):
        self.ipykernel.shell.push(variable_dict)

    @property
    def connection_file(self) -> str:
        return jupyter_client.find_connection_file(self.ipykernel.abs_connection_file)
```

**Step 2: Run tests**

```bash
uv run pytest tests/ -v --timeout=30
```

Expected: PASS

**Step 3: Commit**

```bash
git add SciQLop/components/jupyter/kernel/__init__.py
git commit -m "refactor(jupyter): simplify InternalIPKernel after KernelManager extraction"
```

---

### Task 7: Verify full application startup and shutdown

**Step 1: Manual smoke test**

```bash
uv run sciqlop
```

Verify:
1. Application starts without errors
2. Open JupyterLab from the quickstart shortcut
3. Run a cell in JupyterLab (e.g. `print("hello")`)
4. Close the application — it should quit cleanly without hanging

**Step 2: Check logs for shutdown sequence**

Look for:
- "Process state changed" logs showing SIGTERM → exit
- No "Error while polling" spam during idle
- Clean exit without Python tracebacks

**Step 3: Final commit if any fixups needed**

```bash
git add -A && git commit -m "fix(jupyter): address issues found during smoke test"
```

---

## Summary of Changes

| File | Change |
|------|--------|
| `components/jupyter/IPythonKernel/` → `components/jupyter/kernel/` | Rename |
| `components/jupyter/kernel/__init__.py` | Adaptive poller, simplified `SciQLopKernelApp` and `InternalIPKernel` |
| `components/jupyter/kernel/manager.py` | New `KernelManager` class |
| `components/jupyter/jupyter_clients/clients_manager.py` | Graceful shutdown with timeout |
| `components/jupyter/jupyter_clients/jupyter_client_process.py` | Add `terminate()` method |
| `components/workspaces/backend/workspaces_manager.py` | Delegate to `KernelManager` |
| `tests/test_kernel_poller.py` | New tests |
| `tests/test_jupyter_clients_cleanup.py` | New tests |
| `tests/test_kernel_manager.py` | New tests |
