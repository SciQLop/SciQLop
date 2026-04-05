# Replace SciQLop Jupyter Stack with jupyqt

## Problem

SciQLop's embedded Jupyter integration uses an in-process ipykernel running on the Qt main thread via qasync. This architecture causes:
- **Reentrancy crashes** — the `_KernelPoller` (QTimer + `asyncSlot`) re-enters the qasync event loop during completions and long-running cells
- **UI freezes** — kernel execution blocks the Qt event loop
- **Accumulated workarounds** — `pause_kernel_poller()`, `_patch_qasync_infinite_timer()`, ipykernel version pins, `processEvents()` hacks

jupyqt is a standalone package that embeds JupyterLab in PySide6 apps using a background-thread kernel with its own asyncio loop, a jupyverse server (no ZMQ), and a QWebEngineView widget. It eliminates all of the above issues by design.

## Decisions

| Topic | Decision | Rationale |
|---|---|---|
| qasync | Keep for app event loop, `background_run()`, `asyncSlot` | Still useful for non-kernel async Qt integration |
| LogsWidget / qtconsole | Keep qtconsole as dependency | LogsWidget uses `RichJupyterWidget` for ANSI rendering only |
| External QtConsole | Drop | Embedded JupyterLab + `open_in_browser()` is sufficient |
| `pause_kernel_poller()` | Delete entirely | No kernel poller on main thread = no reentrancy risk |
| Startup flow | Decouple kernel start from event loop blocking | jupyqt's `start()` is non-blocking |

## Scope

### Deleted modules

| Path | Contents | Reason |
|---|---|---|
| `SciQLop/components/jupyter/kernel/__init__.py` | `InternalIPKernel`, `SciQLopKernel`, `SciQLopKernelApp`, `_KernelPoller` | Replaced by `EmbeddedJupyter` |
| `SciQLop/components/jupyter/jupyter_clients/` | `ClientsManager`, `QtConsoleClient`, `JupyterLabClient`, `jupyterlab_auto_build.py`, `jupyter_client_process.py` | No external process spawning needed |
| `SciQLop/Jupyter/__init__.py` | `SciQLopProvisioner` | jupyqt has its own server |
| `SciQLop/Jupyter/lab_kernel_manager.py` | `ExternalMappingKernelManager`, `ExternalMultiKernelManager` | Same |
| `SciQLop/components/jupyter/ui/JupyterLabView.py` | QWebEngineView wrapper for JupyterLab | Replaced by `jupyter.widget()` |

### Deleted entry points and files

```toml
# Remove from pyproject.toml
[project.entry-points."jupyter_client.kernel_provisioners"]
sciqlop-kernel-provisioner = "SciQLop.Jupyter:SciQLopProvisioner"
```

Also delete `SciQLop/Jupyter/entry_points.txt`.

### Dependency changes

```diff
# pyproject.toml
- ipykernel==6.29.5
- jupyter_server==2.16.0
- jupyter_server_terminals==0.5.3
- jupyterlab==4.4.4
- jupyterlab_pygments==0.3.0
- jupyterlab_server==2.27.3
- jupyterlab_widgets==3.0.15
+ jupyqt
```

Keep: `ipython`, `jupyter_client` (qtconsole transitive), `pyzmq` (qtconsole transitive), `qasync`, `qtconsole`.

Future simplification: replace `LogsWidget`'s `RichJupyterWidget` with a lighter ANSI renderer to drop qtconsole (and its transitive deps) entirely.

## New KernelManager

`SciQLop/components/jupyter/kernel/manager.py` becomes a thin wrapper around `EmbeddedJupyter`:

```python
from jupyqt import EmbeddedJupyter
from PySide6.QtCore import QObject
from SciQLop.user_api.magics import register_all_magics


class KernelManager(QObject):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._jupyter = EmbeddedJupyter()
        # Shell is available immediately after EmbeddedJupyter() —
        # create_shell() is synchronous. push() before start() also
        # works: it writes directly to shell.user_ns on the calling
        # thread (kernel thread hasn't started yet). No deferred-
        # variables buffer needed.
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

## WorkspaceManager changes

`SciQLop/components/workspaces/backend/workspaces_manager.py`:

- Remove `ClientsManager` usage
- Remove `new_qt_console()`, `start_jupyterlab()` (external process variants)
- `start()` calls `kernel_manager.start()` (non-blocking) — no longer blocks in event loop
- Expose `kernel_manager.widget()` for the UI layer to dock
- Expose `kernel_manager.open_in_browser()` for the menu action
- Qt objects pushed via `kernel_manager.wrap_qt()` instead of direct push — specifically: `main_window` (QWidget) and `app` (QApplication) must be wrapped; `background_run` (plain function), `workspace` (not a QObject), and `plugins` (dict) do not need wrapping

## Startup flow restructuring

### Before

```
sciqlop_app.py:
  main_windows.show()
  load_all(main_windows)
  main_windows.push_variables_to_console(...)
  main_windows.start()
    → WorkspaceManager.start()
      → KernelManager.start()
        → _KernelPoller.start()
        → sciqlop_event_loop().exec()  # BLOCKS HERE
```

### After

```
sciqlop_app.py:start_sciqlop():
  main_windows = SciQLopMainWindow()
  main_windows.show()
  load_all(main_windows)
  main_windows.push_variables_to_console(...)  # works: shell exists at construction
  return main_windows

sciqlop_app.py:main():
  main_windows = start_sciqlop()
  main_windows.start()
    → WorkspaceManager.start()
      → KernelManager.start()          # non-blocking
      → dock jupyter widget
  sciqlop_event_loop().exec()           # BLOCKS HERE (new line in main())
```

The blocking call moves from deep inside `KernelManager` up to `sciqlop_app.py:main()`. This is the most important structural change: without adding `sciqlop_event_loop().exec()` after `main_windows.start()`, the program would exit immediately.

Note: some variables (e.g. `plugins`) are pushed in `start_sciqlop()` before `start()` is called. This works because jupyqt's shell is created synchronously at construction — `push()` before `start()` writes directly to `shell.user_ns`.

## MainWindow changes

`SciQLop/core/ui/mainwindow.py`:

- Remove `_on_jupyterlab_started(url)` signal handler
- Remove `jupyterlab_started` signal plumbing
- The JupyterLab widget is docked during `start()` via `kernel_manager.widget()`, not on an async signal
- `push_variables_to_console` uses `kernel_manager.wrap_qt()` for Qt objects
- Replace the "Start jupyter console" menu action (`toolsMenu.addAction("Start jupyter console", ...)`) with "Open JupyterLab in browser" calling `workspace_manager.open_in_browser()`

## Call site cleanup

### `SciQLop/user_api/magics/completions.py`

Remove `pause_kernel_poller()` import and `with pause_kernel_poller():` wrapper in `_complete_products()`. The `processEvents()` loop stays — it's still needed for the filter model to settle.

### `SciQLop/components/command_palette/arg_types.py`

Same — remove `pause_kernel_poller()` wrapper, keep surrounding logic.

### `SciQLop/user_api/virtual_products/magic.py`

Remove `pause_kernel_poller()` wrapper in `_run_in_thread_blocking()`. The `ThreadPoolExecutor` approach stays.

### `SciQLop/core/sciqlop_application.py`

Keep `_patch_qasync_infinite_timer()` — while the kernel poller no longer triggers it, any code using `asyncio.sleep(float('inf'))` or `anyio.sleep_forever()` on the qasync event loop would still hit the bug. Since qasync is kept and `cocat_provider.py` uses `asyncSlot`, the patch remains a safety net.

## WorkspaceManagerUI changes

`SciQLop/components/workspaces/ui/workspace_manager_ui.py`:

- Remove `new_qt_console()` delegation
- Remove `jupyterlab_started` signal forwarding
- Add `widget()` and `open_in_browser()` delegation

## What stays unchanged

- `user_api/magics/__init__.py` — `register_all_magics(shell)` works identically (jupyqt's shell is a standard `InteractiveShell`)
- All magic implementations (plot, timerange, vp) — logic unchanged, just lose pause wrappers
- `LogsWidget` — unchanged (still uses qtconsole's `RichJupyterWidget`)
- Completers (Matcher API v2) — unchanged
- Plugin system, settings, catalogs, plotting — no changes
- `SciQLopApp` base class (`qasync.QApplication`) — unchanged
- `background_run()` using `qasync.QThreadExecutor` — unchanged
- `cocat_provider.py` using `qasync.asyncSlot` — unchanged

## Testing

### Tests to delete or rewrite

- `tests/test_kernel_manager.py` — tests `KernelManager` internals (`_kernel_app`, `_kernel`, poller). Rewrite to test the new thin wrapper.
- `tests/test_kernel_poller.py` — tests `_KernelPoller`. Delete (class no longer exists).
- `tests/test_jupyter_clients_cleanup.py` — tests `ClientsManager`. Delete (class no longer exists).
- `tests/test_command_palette_harvester.py` — references "Start jupyter console" action in fixtures. Update to match renamed menu action.

### Tests that should pass unchanged

- Existing tests that exercise magics, completions, and virtual products (they test logic, not the kernel transport)
- `conftest.py` fixtures may need adjustment if they set up a kernel — verify and update

### Manual smoke test

Launch app, open JupyterLab widget, run a cell, use `%plot`, use `%%vp`, verify `open_in_browser()`
