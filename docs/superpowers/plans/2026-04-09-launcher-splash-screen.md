# Launcher Startup Window Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a startup window from the launcher process that displays progress during workspace preparation, warns about missing xcb-cursor, handles errors with full stack traces, and stays visible until the main app is ready.

**Architecture:** The launcher creates a minimal QApplication + StartupWindow before workspace prep. uv subprocess output is streamed line-by-line via an `on_output` callback. After prep, the app subprocess is spawned with `Popen` (non-blocking). A ready-file IPC mechanism signals when the main window is up. The launcher's QApplication is torn down only after the ready signal.

**Tech Stack:** PySide6 (QWidget, QLabel, QPlainTextEdit, QPushButton, QTimer, QPixmap), subprocess.Popen, tempfile, ctypes (xcb-cursor check)

---

### Task 1: Add `on_output` callback to WorkspaceVenv

**Files:**
- Modify: `SciQLop/components/workspaces/backend/workspace_venv.py:34-50`
- Test: `tests/test_workspace_venv.py`

- [ ] **Step 1: Write failing tests for on_output callback**

Add to `tests/test_workspace_venv.py`:

```python
class TestCreateWithCallback:
    @patch("SciQLop.components.workspaces.backend.workspace_venv.subprocess.Popen")
    @patch("SciQLop.components.workspaces.backend.workspace_venv.uv_command")
    def test_streams_stderr_to_callback(self, mock_uv_cmd, mock_popen, venv, workspace_dir):
        mock_uv_cmd.return_value = ["uv", "venv", str(workspace_dir / ".venv")]
        proc = MagicMock()
        proc.stderr.__iter__ = MagicMock(return_value=iter(["Creating venv...\n", "Done\n"]))
        proc.wait.return_value = 0
        mock_popen.return_value = proc

        lines = []
        venv.create(on_output=lines.append)

        assert lines == ["Creating venv...", "Done"]
        mock_popen.assert_called_once_with(
            mock_uv_cmd.return_value, stderr=subprocess.PIPE, text=True,
        )

    @patch("SciQLop.components.workspaces.backend.workspace_venv.subprocess.Popen")
    @patch("SciQLop.components.workspaces.backend.workspace_venv.uv_command")
    def test_raises_on_nonzero_exit(self, mock_uv_cmd, mock_popen, venv, workspace_dir):
        mock_uv_cmd.return_value = ["uv", "venv"]
        proc = MagicMock()
        proc.stderr.__iter__ = MagicMock(return_value=iter([]))
        proc.wait.return_value = 1
        mock_popen.return_value = proc

        with pytest.raises(subprocess.CalledProcessError):
            venv.create(on_output=lambda _: None)


class TestSyncWithCallback:
    @patch("SciQLop.components.workspaces.backend.workspace_venv.subprocess.Popen")
    @patch("SciQLop.components.workspaces.backend.workspace_venv.uv_command")
    def test_streams_stderr_to_callback(self, mock_uv_cmd, mock_popen, venv, workspace_dir):
        mock_uv_cmd.return_value = ["uv", "sync"]
        proc = MagicMock()
        proc.stderr.__iter__ = MagicMock(return_value=iter(["Resolved 10 packages\n"]))
        proc.wait.return_value = 0
        mock_popen.return_value = proc

        lines = []
        venv.sync(on_output=lines.append)

        assert lines == ["Resolved 10 packages"]
        mock_popen.assert_called_once_with(
            mock_uv_cmd.return_value, stderr=subprocess.PIPE, text=True,
            cwd=str(workspace_dir),
        )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_workspace_venv.py::TestCreateWithCallback tests/test_workspace_venv.py::TestSyncWithCallback -v`
Expected: FAIL — `create()` and `sync()` don't accept `on_output`

- [ ] **Step 3: Implement on_output in WorkspaceVenv**

Replace the `create` and `sync` methods in `SciQLop/components/workspaces/backend/workspace_venv.py`:

```python
from __future__ import annotations
from collections.abc import Callable

# ... existing imports, add Popen usage ...

def _run_uv(cmd: list[str], on_output: Callable[[str], None] | None = None, **kwargs) -> None:
    """Run a uv command, optionally streaming stderr line-by-line."""
    if on_output is None:
        subprocess.run(cmd, check=True, **kwargs)
        return
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, **kwargs)
    for line in proc.stderr:
        on_output(line.rstrip("\n"))
    rc = proc.wait()
    if rc != 0:
        raise subprocess.CalledProcessError(rc, cmd)
```

Then update the methods:

```python
def create(self, on_output: Callable[[str], None] | None = None) -> None:
    """Create the workspace venv with --system-site-packages."""
    cmd = uv_command(
        "venv",
        str(self._venv_dir),
        "--system-site-packages",
        "--clear",
        "--python",
        get_python(),
    )
    _run_uv(cmd, on_output)

def sync(self, locked: bool = False, on_output: Callable[[str], None] | None = None) -> None:
    """Run uv sync in the workspace directory."""
    args = ("sync", "--locked") if locked else ("sync",)
    cmd = uv_command(*args)
    _run_uv(cmd, on_output, cwd=str(self._workspace_dir))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_workspace_venv.py -v`
Expected: ALL PASS (existing tests unchanged — `on_output=None` uses old `subprocess.run` path)

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/workspaces/backend/workspace_venv.py tests/test_workspace_venv.py
git commit -m "feat: add on_output callback to WorkspaceVenv for streaming uv output"
```

---

### Task 2: Forward callback in `prepare_workspace`

**Files:**
- Modify: `SciQLop/components/workspaces/backend/workspace_setup.py:37-103`
- Test: `tests/test_workspace_setup.py`

- [ ] **Step 1: Write failing test for callback forwarding**

Add to `tests/test_workspace_setup.py`:

```python
class TestPrepareWorkspaceCallback:
    def test_forwards_on_output_to_venv_methods(self, workspace_dir, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        cb = MagicMock()
        prepare_workspace(workspace_dir, workspace_name="Test", on_output=cb)

        patches["venv"].ensure.assert_called_once_with(on_output=cb)
        patches["venv"].sync.assert_called_once_with(locked=False, on_output=cb)

    def test_no_callback_by_default(self, workspace_dir, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        prepare_workspace(workspace_dir, workspace_name="Test")

        patches["venv"].ensure.assert_called_once_with(on_output=None)
        patches["venv"].sync.assert_called_once_with(locked=False, on_output=None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_workspace_setup.py::TestPrepareWorkspaceCallback -v`
Expected: FAIL — `prepare_workspace` doesn't accept `on_output`

- [ ] **Step 3: Update prepare_workspace signature and calls**

In `SciQLop/components/workspaces/backend/workspace_setup.py`, add `on_output` parameter and forward it:

```python
from __future__ import annotations
from collections.abc import Callable

def prepare_workspace(
    workspace_dir: Path | str,
    workspace_name: str | None = None,
    locked: bool = False,
    on_output: Callable[[str], None] | None = None,
) -> Path:
    # ... existing code unchanged until venv section ...

    # Ensure venv exists and sync
    venv = WorkspaceVenv(workspace_dir)
    venv.ensure(on_output=on_output)
    venv.sync(locked=locked, on_output=on_output)

    return venv.python_path
```

Also update `WorkspaceVenv.ensure()` in `workspace_venv.py` to forward the callback:

```python
def ensure(self, on_output: Callable[[str], None] | None = None) -> None:
    """Create the venv if missing, wrong version, or stale paths."""
    if self._needs_recreate():
        if self._venv_dir.exists():
            shutil.rmtree(self._venv_dir)
        self.create(on_output=on_output)
```

- [ ] **Step 4: Update existing tests that assert ensure/sync call signatures**

The existing `TestPrepareWorkspaceVenv` tests assert `sync.assert_called_once_with(locked=False)` — update them to `sync.assert_called_once_with(locked=False, on_output=None)` and similarly for `ensure`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_workspace_setup.py tests/test_workspace_venv.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/workspaces/backend/workspace_setup.py SciQLop/components/workspaces/backend/workspace_venv.py tests/test_workspace_setup.py tests/test_workspace_venv.py
git commit -m "feat: forward on_output callback through prepare_workspace"
```

---

### Task 3: Create StartupWindow widget

**Files:**
- Create: `SciQLop/components/startup/__init__.py`
- Create: `SciQLop/components/startup/startup_window.py`
- Test: `tests/test_startup_window.py`

- [ ] **Step 1: Write failing tests for StartupWindow**

Create `tests/test_startup_window.py`:

```python
"""Tests for StartupWindow widget."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from SciQLop.components.startup.startup_window import StartupWindow


@pytest.fixture
def window(qtbot):
    w = StartupWindow()
    qtbot.addWidget(w)
    return w


class TestProgressState:
    def test_initial_state_shows_progress(self, window):
        assert window._phase_label.isVisible()
        assert window._detail_label.isVisible()
        assert not window._warning_banner.isVisible()
        assert not window._error_text.isVisible()

    def test_set_phase_updates_label(self, window):
        window.set_phase("Installing dependencies...")
        assert window._phase_label.text() == "Installing dependencies..."

    def test_set_detail_updates_label(self, window):
        window.set_detail("Resolved 42 packages")
        assert window._detail_label.text() == "Resolved 42 packages"


class TestWarningState:
    def test_show_warning_displays_banner(self, window, qtbot):
        window.show_warning("Missing libxcb-cursor0")
        assert window._warning_banner.isVisible()
        assert "libxcb-cursor0" in window._warning_banner.text()
        assert window._continue_btn.isVisible()

    def test_continue_button_resumes_progress(self, window, qtbot):
        window.show_warning("test warning")
        qtbot.mouseClick(window._continue_btn, Qt.LeftButton)
        assert not window._warning_banner.isVisible()
        assert not window._continue_btn.isVisible()
        assert window._phase_label.isVisible()

    def test_continue_emits_signal(self, window, qtbot):
        window.show_warning("test warning")
        with qtbot.waitSignal(window.warning_acknowledged):
            qtbot.mouseClick(window._continue_btn, Qt.LeftButton)


class TestErrorState:
    def test_show_error_displays_traceback(self, window):
        window.show_error("Traceback (most recent call last):\n  File ...")
        assert window._error_text.isVisible()
        assert "Traceback" in window._error_text.toPlainText()
        assert window._quit_btn.isVisible()
        assert window._copy_btn.isVisible()
        assert not window._phase_label.isVisible()

    def test_copy_button_copies_to_clipboard(self, window, qtbot):
        window.show_error("some error text")
        qtbot.mouseClick(window._copy_btn, Qt.LeftButton)
        clipboard = QApplication.clipboard()
        assert clipboard.text() == "some error text"


class TestWindowFlags:
    def test_frameless_splash_flags(self, window):
        flags = window.windowFlags()
        assert flags & Qt.SplashScreen
        assert flags & Qt.FramelessWindowHint
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_startup_window.py -v`
Expected: FAIL — module not found

- [ ] **Step 3: Create the StartupWindow widget**

Create `SciQLop/components/startup/__init__.py`:

```python
```

Create `SciQLop/components/startup/startup_window.py`:

```python
"""Startup window shown by the launcher during workspace preparation."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_SPLASH_PATH = ":/splash.png"


class StartupWindow(QWidget):
    """Frameless startup window with progress, warning, and error states."""

    warning_acknowledged = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowFlags(Qt.SplashScreen | Qt.FramelessWindowHint)
        self._build_ui()
        self._enter_progress_state()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._splash_label = QLabel()
        pixmap = QPixmap(_SPLASH_PATH)
        if not pixmap.isNull():
            self._splash_label.setPixmap(pixmap)
            self.setFixedSize(pixmap.size())
        self._splash_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._splash_label)

        overlay = QVBoxLayout()
        overlay.setContentsMargins(12, 8, 12, 8)

        self._warning_banner = QLabel()
        self._warning_banner.setWordWrap(True)
        self._warning_banner.setStyleSheet(
            "background: #e6a817; color: #222; padding: 6px; font-weight: bold;"
        )
        overlay.addWidget(self._warning_banner)

        self._phase_label = QLabel()
        self._phase_label.setStyleSheet(
            "color: white; font-size: 14px; font-weight: bold;"
            "background: rgba(0, 0, 0, 120); padding: 4px;"
        )
        overlay.addWidget(self._phase_label)

        self._detail_label = QLabel()
        self._detail_label.setStyleSheet(
            "color: #ccc; font-size: 11px;"
            "background: rgba(0, 0, 0, 80); padding: 2px;"
        )
        overlay.addWidget(self._detail_label)

        btn_row = QHBoxLayout()
        self._continue_btn = QPushButton("Continue")
        self._continue_btn.clicked.connect(self._on_continue)
        btn_row.addWidget(self._continue_btn)
        btn_row.addStretch()
        overlay.addLayout(btn_row)

        self._error_text = QPlainTextEdit()
        self._error_text.setReadOnly(True)
        self._error_text.setStyleSheet("background: #1e1e1e; color: #f44; font-family: monospace;")
        overlay.addWidget(self._error_text)

        error_btn_row = QHBoxLayout()
        self._copy_btn = QPushButton("Copy to clipboard")
        self._copy_btn.clicked.connect(self._copy_error)
        self._quit_btn = QPushButton("Quit")
        self._quit_btn.clicked.connect(QApplication.quit)
        error_btn_row.addWidget(self._copy_btn)
        error_btn_row.addWidget(self._quit_btn)
        error_btn_row.addStretch()
        overlay.addLayout(error_btn_row)

        layout.addLayout(overlay)

    def _enter_progress_state(self) -> None:
        self._phase_label.setVisible(True)
        self._detail_label.setVisible(True)
        self._warning_banner.setVisible(False)
        self._continue_btn.setVisible(False)
        self._error_text.setVisible(False)
        self._copy_btn.setVisible(False)
        self._quit_btn.setVisible(False)

    def set_phase(self, text: str) -> None:
        self._phase_label.setText(text)

    def set_detail(self, text: str) -> None:
        self._detail_label.setText(text)

    def show_warning(self, message: str) -> None:
        self._warning_banner.setText(message)
        self._warning_banner.setVisible(True)
        self._continue_btn.setVisible(True)

    def _on_continue(self) -> None:
        self._warning_banner.setVisible(False)
        self._continue_btn.setVisible(False)
        self.warning_acknowledged.emit()

    def show_error(self, traceback_text: str) -> None:
        self._phase_label.setVisible(False)
        self._detail_label.setVisible(False)
        self._warning_banner.setVisible(False)
        self._continue_btn.setVisible(False)
        self._error_text.setPlainText(traceback_text)
        self._error_text.setVisible(True)
        self._copy_btn.setVisible(True)
        self._quit_btn.setVisible(True)
        self.setFixedSize(600, 400)

    def _copy_error(self) -> None:
        QApplication.clipboard().setText(self._error_text.toPlainText())

    def center_on_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move(
                geo.x() + (geo.width() - self.width()) // 2,
                geo.y() + (geo.height() - self.height()) // 2,
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_startup_window.py -v`
Expected: ALL PASS

Note: The splash pixmap (`:/splash.png`) will be null in tests since qInitResources isn't called. The widget still works — it just has no background image. Tests validate behavior, not visuals.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/startup/__init__.py SciQLop/components/startup/startup_window.py tests/test_startup_window.py
git commit -m "feat: add StartupWindow widget with progress/warning/error states"
```

---

### Task 4: Integrate StartupWindow into the launcher

**Files:**
- Modify: `SciQLop/sciqlop_launcher.py`
- Test: `tests/test_launcher.py`

- [ ] **Step 1: Write failing tests for launcher startup window integration**

Add to `tests/test_launcher.py`:

```python
import subprocess
import tempfile

from unittest.mock import patch, MagicMock, call
from pathlib import Path

from SciQLop.sciqlop_launcher import (
    _run_with_startup_window, check_xcb_cursor,
)


class TestCheckXcbCursor:
    @patch("SciQLop.sciqlop_launcher.platform.system", return_value="Linux")
    @patch.dict("os.environ", {"QT_QPA_PLATFORM": "xcb"})
    @patch("SciQLop.sciqlop_launcher.ctypes.cdll.LoadLibrary")
    def test_returns_none_when_cursor_available(self, mock_load, mock_sys):
        assert check_xcb_cursor() is None

    @patch("SciQLop.sciqlop_launcher.platform.system", return_value="Linux")
    @patch.dict("os.environ", {"QT_QPA_PLATFORM": "xcb"})
    @patch("SciQLop.sciqlop_launcher.ctypes.cdll.LoadLibrary", side_effect=OSError)
    def test_returns_warning_when_cursor_missing(self, mock_load, mock_sys):
        result = check_xcb_cursor()
        assert result is not None
        assert "xcb-cursor" in result.lower()

    @patch("SciQLop.sciqlop_launcher.platform.system", return_value="Windows")
    def test_returns_none_on_non_linux(self, mock_sys):
        assert check_xcb_cursor() is None

    @patch("SciQLop.sciqlop_launcher.platform.system", return_value="Linux")
    @patch.dict("os.environ", {}, clear=False)
    def test_returns_none_when_not_xcb(self, mock_sys):
        import os
        os.environ.pop("QT_QPA_PLATFORM", None)
        assert check_xcb_cursor() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_launcher.py::TestCheckXcbCursor -v`
Expected: FAIL — `check_xcb_cursor` doesn't exist

- [ ] **Step 3: Rewrite the launcher**

Replace `SciQLop/sciqlop_launcher.py` with the new implementation:

```python
"""SciQLop launcher — workspace-aware supervisor process.

In production (PyPI, AppImage, DMG, MSIX), the launcher creates a workspace
venv with --system-site-packages and spawns the Qt app as a subprocess.

In development mode (editable install), the launcher still sets up the
workspace directory and metadata but uses the current Python (sys.executable)
instead of a workspace venv, since the dev venv already has all dependencies.

A startup window is shown during the entire process, from workspace preparation
through to the main app window being ready.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import platform
import subprocess
import sys
import tempfile
from pathlib import Path

EXIT_RESTART = 64
EXIT_SWITCH_WORKSPACE = 65
SWITCH_WORKSPACE_FILE = ".sciqlop_switch_target"
READY_FILE_ENV = "SCIQLOP_STARTUP_READY_FILE"


def _is_editable_install() -> bool:
    """Detect if SciQLop is installed as an editable package (development mode)."""
    try:
        from importlib.metadata import distribution
        dist = distribution("SciQLop")
        direct_url = dist.read_text("direct_url.json")
        if direct_url:
            import json
            info = json.loads(direct_url)
            return info.get("dir_info", {}).get("editable", False)
    except Exception:
        pass
    return False


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SciQLop launcher")
    parser.add_argument("--workspace", "-w", type=str, default=None,
                        help="Workspace name or path")
    parser.add_argument("sciqlop_file", nargs="?", default=None,
                        help="Path to a .sciqlop or .sciqlop-archive file")
    return parser.parse_args(argv if argv is not None else sys.argv[1:])


def resolve_workspace_dir(
    workspace_name: str | None,
    sciqlop_file: str | None,
) -> Path:
    from SciQLop.components.workspaces.backend.settings import SciQLopWorkspacesSettings

    settings = SciQLopWorkspacesSettings()
    workspaces_root = Path(settings.workspaces_dir)

    if sciqlop_file:
        sciqlop_path = Path(sciqlop_file)
        if sciqlop_path.suffix == ".sciqlop":
            return sciqlop_path.parent
        elif sciqlop_path.suffix == ".sciqlop-archive":
            from SciQLop.components.workspaces.backend.workspace_archive import import_workspace
            target_dir = workspaces_root / sciqlop_path.stem
            if not (target_dir / "workspace.sciqlop").exists():
                import_workspace(sciqlop_path, target_dir)
            return target_dir

    if workspace_name:
        candidate = Path(workspace_name)
        if candidate.is_absolute():
            return candidate
        return workspaces_root / workspace_name

    return workspaces_root / "default"


def _read_switch_target(workspace_dir: Path) -> str | None:
    switch_file = workspace_dir / SWITCH_WORKSPACE_FILE
    if switch_file.exists():
        target = switch_file.read_text().strip()
        switch_file.unlink()
        return target
    return None


def check_xcb_cursor() -> str | None:
    """Return a warning string if xcb-cursor is missing on Linux+xcb, else None."""
    if platform.system() != "Linux":
        return None
    if os.environ.get("QT_QPA_PLATFORM") != "xcb":
        return None
    try:
        ctypes.cdll.LoadLibrary("libxcb-cursor.so.0")
        return None
    except OSError:
        return (
            "Warning: libxcb-cursor0 is not installed.\n"
            "Cursor rendering may be broken. Install it with:\n"
            "  sudo apt install libxcb-cursor0   (Debian/Ubuntu)\n"
            "  sudo dnf install xcb-util-cursor   (Fedora)"
        )


def _prepare_workspace_dev(workspace_dir: Path, on_output=None) -> None:
    """Set up workspace directory, metadata, and install plugin deps in dev mode."""
    from SciQLop.components.workspaces.backend.workspace_migration import migrate_workspace
    from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
    from SciQLop.components.plugins.plugin_deps import collect_plugin_dependencies
    from SciQLop.components.workspaces.backend.workspace_setup import get_globally_enabled_plugins, get_plugin_folders
    from SciQLop.components.workspaces.backend.uv import uv_command
    from SciQLop.components.workspaces.backend.workspace_venv import _run_uv

    workspace_dir.mkdir(parents=True, exist_ok=True)
    migrate_workspace(workspace_dir)

    manifest_path = workspace_dir / "workspace.sciqlop"
    if manifest_path.exists():
        manifest = WorkspaceManifest.load(manifest_path)
    else:
        manifest = WorkspaceManifest.default_manifest(workspace_dir.name)
        manifest.save(manifest_path)

    plugin_deps = collect_plugin_dependencies(
        plugin_folders=get_plugin_folders(),
        enabled_plugins=get_globally_enabled_plugins(),
        workspace_plugins_add=manifest.plugins_add,
        workspace_plugins_remove=manifest.plugins_remove,
    )
    all_deps = plugin_deps + manifest.requires
    if all_deps:
        try:
            cmd = uv_command("pip", "install", *all_deps)
            _run_uv(cmd, on_output)
        except Exception as e:
            print(f"Warning: failed to install plugin/workspace deps: {e}")


def _run_with_startup_window(workspace_dir: Path, python_path: Path, prepare_fn) -> int:
    """Show startup window, run workspace prep, spawn app, wait for ready signal."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from SciQLop.resources import qInitResources
    from SciQLop.components.startup.startup_window import StartupWindow

    app = QApplication(sys.argv[:1])
    qInitResources()

    window = StartupWindow()
    window.center_on_screen()
    window.show()
    window.set_phase("Preparing workspace...")
    app.processEvents()

    # Workspace preparation with streaming output
    try:
        def on_output(line: str) -> None:
            window.set_detail(line)
            app.processEvents()

        prepare_fn(on_output)
    except Exception:
        import traceback
        window.show_error(traceback.format_exc())
        app.exec()
        return 1

    # Check xcb cursor availability
    xcb_warning = check_xcb_cursor()
    if xcb_warning:
        window.show_warning(xcb_warning)
        # Block until user clicks Continue
        waiting = True

        def on_ack():
            nonlocal waiting
            waiting = False

        window.warning_acknowledged.connect(on_ack)
        while waiting:
            app.processEvents()

    # Spawn the app subprocess
    window.set_phase("Starting SciQLop...")
    window.set_detail("")
    app.processEvents()

    ready_dir = tempfile.mkdtemp(prefix="sciqlop_startup_")
    ready_file = Path(ready_dir) / "ready"

    env = os.environ.copy()
    env["SCIQLOP_WORKSPACE_DIR"] = str(workspace_dir)
    env["SPEASY_SKIP_INIT_PROVIDERS"] = "1"
    env[READY_FILE_ENV] = str(ready_file)

    proc = subprocess.Popen(
        [str(python_path), "-m", "SciQLop.sciqlop_app"],
        env=env,
    )

    # Poll for ready signal or process exit
    def check_ready():
        if ready_file.exists():
            window.close()
            app.quit()
        elif proc.poll() is not None:
            # Process exited before signaling ready — likely a crash
            window.show_error(
                f"SciQLop process exited with code {proc.returncode} before becoming ready."
            )

    timer = QTimer()
    timer.timeout.connect(check_ready)
    timer.start(100)

    app.exec()
    timer.stop()

    # Clean up temp dir
    import shutil
    shutil.rmtree(ready_dir, ignore_errors=True)

    # If process is still running, wait for it
    if proc.poll() is None:
        return proc.wait()
    return proc.returncode


def run_sciqlop_app(python_path: Path, workspace_dir: Path) -> int:
    """Launch the SciQLop Qt app as a subprocess using the workspace venv Python."""
    env = os.environ.copy()
    env["SCIQLOP_WORKSPACE_DIR"] = str(workspace_dir)
    env["SPEASY_SKIP_INIT_PROVIDERS"] = "1"
    result = subprocess.run(
        [str(python_path), "-m", "SciQLop.sciqlop_app"],
        env=env,
    )
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace_dir = resolve_workspace_dir(args.workspace, args.sciqlop_file)
    dev_mode = _is_editable_install()

    while True:
        if dev_mode:
            def prepare_fn(on_output):
                _prepare_workspace_dev(workspace_dir, on_output=on_output)

            exit_code = _run_with_startup_window(
                workspace_dir, Path(sys.executable), prepare_fn,
            )
        else:
            def prepare_fn(on_output):
                from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace
                result = prepare_workspace(workspace_dir, on_output=on_output)
                prepare_fn.python_path = result

            prepare_fn.python_path = None
            exit_code = _run_with_startup_window(
                workspace_dir,
                # python_path is resolved during prepare_fn; use a lazy lookup
                # We need to restructure slightly — see step 4
                Path(sys.executable),  # placeholder, overridden below
                prepare_fn,
            )

        if exit_code == EXIT_RESTART:
            continue
        elif exit_code == EXIT_SWITCH_WORKSPACE:
            target = _read_switch_target(workspace_dir)
            if target:
                workspace_dir = resolve_workspace_dir(
                    workspace_name=target, sciqlop_file=None
                )
                continue
            print("Switch-workspace requested but no target found — exiting", file=sys.stderr)
            return exit_code
        else:
            return exit_code


if __name__ == "__main__":
    sys.exit(main())
```

Wait — there's a subtlety in production mode: `prepare_workspace` returns the venv python path, which is needed for `Popen`. But `_run_with_startup_window` receives `python_path` before `prepare_fn` runs. We need to restructure so `prepare_fn` can return the python path.

Revised `_run_with_startup_window` signature — `prepare_fn` returns the python path to use:

```python
def _run_with_startup_window(workspace_dir: Path, default_python: Path, prepare_fn) -> int:
    """Show startup window, run workspace prep, spawn app, wait for ready signal.

    prepare_fn(on_output) should return a Path to the python executable to use,
    or None to use default_python.
    """
    # ... same setup ...

    python_path = default_python
    try:
        def on_output(line: str) -> None:
            window.set_detail(line)
            app.processEvents()

        result = prepare_fn(on_output)
        if result is not None:
            python_path = result
    except Exception:
        import traceback
        window.show_error(traceback.format_exc())
        app.exec()
        return 1

    # ... rest uses python_path for Popen ...
```

And in `main()`:

```python
if dev_mode:
    def prepare_fn(on_output):
        _prepare_workspace_dev(workspace_dir, on_output=on_output)
        return None  # use sys.executable

    exit_code = _run_with_startup_window(
        workspace_dir, Path(sys.executable), prepare_fn,
    )
else:
    def prepare_fn(on_output):
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace
        return prepare_workspace(workspace_dir, on_output=on_output)

    exit_code = _run_with_startup_window(
        workspace_dir, Path(sys.executable), prepare_fn,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_launcher.py -v`
Expected: ALL PASS (existing parse/resolve tests unchanged, new xcb tests pass)

- [ ] **Step 5: Commit**

```bash
git add SciQLop/sciqlop_launcher.py tests/test_launcher.py
git commit -m "feat: integrate StartupWindow into launcher with progress streaming and xcb check"
```

---

### Task 5: Remove splash from sciqlop_app.py, add ready-file signal

**Files:**
- Modify: `SciQLop/sciqlop_app.py:47-89`

- [ ] **Step 1: Update start_sciqlop to write ready-file and remove splash**

Replace `start_sciqlop()` in `SciQLop/sciqlop_app.py`:

```python
def _signal_ready() -> None:
    """Write the ready-file so the launcher knows the main window is up."""
    ready_path = os.environ.get("SCIQLOP_STARTUP_READY_FILE")
    if ready_path:
        Path(ready_path).touch()


def start_sciqlop():
    os.environ['INSIDE_SCIQLOP'] = '1'
    from PySide6 import QtPrintSupport, QtQml

    from SciQLop.core.sciqlop_application import sciqlop_event_loop, sciqlop_app
    from SciQLop.resources import qInitResources

    print(str(QtPrintSupport) + str(QtQml))

    app = sciqlop_app()
    qInitResources()
    from SciQLop.components.theming.icons import flush_deferred_icons
    flush_deferred_icons()
    sciqlop_event_loop()

    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    from SciQLop.components.plugins import load_all, loaded_plugins
    app.processEvents()
    main_windows = SciQLopMainWindow()

    main_windows.show()
    app.processEvents()
    load_all(main_windows)

    from SciQLop.components.command_palette.commands import register_builtin_commands
    register_builtin_commands(app.command_registry)

    from SciQLop.components.command_palette.backend.harvester import harvest_qactions
    harvest_qactions(app.command_registry, main_windows)

    main_windows.push_variables_to_console({"plugins": loaded_plugins})

    app.processEvents()
    _signal_ready()
    return main_windows
```

Also remove the `QPixmap` and `QSplashScreen` imports at the top of `start_sciqlop()` (lines 50-51 in the original).

- [ ] **Step 2: Verify the app still starts correctly**

Run: `uv run pytest tests/ -v --timeout=60`
Expected: ALL PASS

- [ ] **Step 3: Commit**

```bash
git add SciQLop/sciqlop_app.py
git commit -m "feat: remove splash screen from app subprocess, signal launcher via ready-file"
```

---

### Task 6: Manual integration test

**Files:** None (manual verification)

- [ ] **Step 1: Test happy path in dev mode**

Run: `uv run sciqlop`

Expected:
- Startup window appears immediately with splash image
- Phase label shows "Preparing workspace..."
- Detail label shows uv output lines (if any deps to install)
- Phase changes to "Starting SciQLop..."
- Startup window disappears when main window appears

- [ ] **Step 2: Test xcb-cursor warning (Linux only)**

Temporarily rename/hide `libxcb-cursor.so.0` or set an env override, then run `uv run sciqlop`.

Expected:
- Warning banner appears with install instructions
- "Continue" button visible
- Clicking Continue proceeds to "Starting SciQLop..."

- [ ] **Step 3: Test error handling**

Temporarily break `prepare_workspace` (e.g. invalid uv path), then run `uv run sciqlop`.

Expected:
- Error view appears with full stack trace
- "Copy to clipboard" and "Quit" buttons visible
- "Copy" copies the trace, "Quit" exits

- [ ] **Step 4: Commit any fixes from manual testing**

```bash
git add -u
git commit -m "fix: address issues found during manual startup window testing"
```
