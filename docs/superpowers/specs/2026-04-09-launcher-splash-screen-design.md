# Launcher Startup Window

**Date**: 2026-04-09
**Status**: Approved

## Problem

When SciQLop launches, workspace preparation (venv creation, `uv sync`, plugin dep install) runs silently in the launcher process. The user sees nothing — no feedback that the app has started, no progress, no error details if something fails. Additionally, on Linux with forced XCB backend, missing `libxcb-cursor0` is a common issue with no warning.

## Design

### Approach: Single custom startup widget in the launcher

A `QWidget` (not `QSplashScreen`) in the launcher process that covers the full startup lifecycle — from workspace preparation through to the main app window being ready in the subprocess.

### Startup window states

**Progress** (default): Splash image background, phase label ("Preparing workspace...", "Installing dependencies...", "Starting SciQLop..."), detail label showing the last line of uv stderr output. Both labels overlaid at the bottom of the splash image.

**Warning**: Same layout plus a yellow warning banner and a "Continue" button. Used for non-fatal issues like missing xcb-cursor. Window stays until the user clicks Continue.

**Error**: Splash image replaced/shrunk, scrollable `QPlainTextEdit` (read-only) with the full stack trace, "Copy to clipboard" and "Quit" buttons. Window stays until the user quits.

State transitions:
```
Progress → Done (happy path, window closes)
Progress → Warning → user clicks Continue → Progress → Done
Progress → Error (window stays until user quits)
```

Widget is frameless (`Qt.SplashScreen | Qt.FramelessWindowHint`), centered on primary screen. No click-to-dismiss.

### Launcher flow

```
1. Parse args, resolve workspace
2. Create QApplication + StartupWindow (show immediately)
3. Run workspace prep with progress callback:
   - uv venv create → "Preparing workspace..."
   - uv sync → "Installing dependencies..." + streamed uv stderr lines
4. Check xcb cursors (Linux + xcb only) → warning state if missing
5. Spawn subprocess via Popen (non-blocking)
6. Show "Starting SciQLop..."
7. QTimer polls for ready-file at ~100ms
8. Ready-file detected → close StartupWindow, destroy QApplication
9. Popen.wait() for subprocess exit code
10. Return exit code (restart/switch-workspace loop unchanged)
```

Both dev mode and production mode use the same flow. In dev mode the splash just lives shorter since workspace prep is lighter.

### IPC: ready-file

The launcher creates a temp directory (`tempfile.mkdtemp()`), passes the ready-file path to the subprocess via `SCIQLOP_STARTUP_READY_FILE` env var. The subprocess writes to this file after main window + plugins are fully loaded. The launcher polls with `QTimer` and closes the startup window on detection. Temp directory is cleaned up on launcher exit.

### uv output streaming

`WorkspaceVenv.create()` and `.sync()` gain an optional `on_output: Callable[[str], None] | None = None` parameter. When provided, they use `Popen` with `stderr=PIPE` and read line-by-line, calling the callback for each line. When `None`, behavior is unchanged (`subprocess.run`).

The launcher wraps this callback to update the startup window and call `app.processEvents()`.

`prepare_workspace()` in `workspace_setup.py` forwards the callback to `WorkspaceVenv` methods.

`_prepare_workspace_dev()` in `sciqlop_launcher.py` does the same for its `uv pip install` call.

### xcb-cursor check

On Linux, after `QApplication` is created, if `QT_QPA_PLATFORM == xcb`:
- Attempt `ctypes.cdll.LoadLibrary("libxcb-cursor.so.0")`
- On failure: transition startup window to warning state with "Missing libxcb-cursor0 — install it for proper cursor support"
- User clicks Continue to proceed

### Existing splash removal

The `QSplashScreen` in `sciqlop_app.py` is removed. The launcher's startup window covers the entire startup. Direct `python -m SciQLop.sciqlop_app` invocation (dev scenario) has no splash — terminal output is sufficient.

## Files

**New:**
- `SciQLop/components/startup/startup_window.py` — `StartupWindow` widget

**Modified:**
- `SciQLop/sciqlop_launcher.py` — QApplication lifecycle, StartupWindow integration, Popen + ready-file polling
- `SciQLop/components/workspaces/backend/workspace_venv.py` — optional `on_output` callback on `create()` and `sync()`
- `SciQLop/components/workspaces/backend/workspace_setup.py` — forward callback to WorkspaceVenv
- `SciQLop/sciqlop_app.py` — remove QSplashScreen, write ready-file after startup
