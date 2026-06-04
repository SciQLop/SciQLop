"""SciQLop launcher — workspace-aware supervisor process.

In production (PyPI, AppImage, DMG, MSIX), the launcher creates a workspace
venv with --system-site-packages and spawns the Qt app as a subprocess.

In development mode (editable install), the launcher still sets up the
workspace directory and metadata but uses the current Python (sys.executable)
instead of a workspace venv, since the dev venv already has all dependencies.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import platform
import shutil
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
        # Check for direct_url.json which indicates a direct/editable install
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
    """Return a warning if libxcb-cursor is missing on Linux, else None."""
    if platform.system() != "Linux":
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


def _apply_proxy_settings() -> None:
    """Inject the configured HTTP proxy into the process environment before any
    uv / network call.  A GUI-launched SciQLop (desktop shortcut) inherits no
    shell environment, so without this the bundled uv connects directly and
    hangs at "Preparing workspace..." behind a corporate proxy.  Setting
    ``os.environ`` here covers both the in-process uv runs during workspace
    preparation and the app subprocess, which inherits ``os.environ``.
    """
    from SciQLop.components.settings.backend.network import apply_proxy_settings
    apply_proxy_settings(os.environ)


def _last_launch_log_path() -> Path:
    """Stable on-disk log location for the most recent SciQLop subprocess.

    The bundled Windows launcher (``launcher.c``) spawns the Python entry
    point with ``CREATE_NO_WINDOW``, so any output written to stdout/stderr
    is otherwise lost.  Tee the subprocess output here so users (and bug
    reports) have something to point to when SciQLop fails to start.
    """
    from platformdirs import user_data_dir
    log_dir = Path(user_data_dir(appname="sciqlop", appauthor="LPP", ensure_exists=True))
    return log_dir / "last-launch.log"


def _prepare_on_worker_thread(prepare_fn, default_python: Path, on_detail) -> tuple[Path, str | None]:
    """Run ``prepare_fn(on_output)`` on a worker thread while a local Qt event
    loop keeps spinning on the GUI thread, so the splash stays responsive during
    the long, often-silent workspace preparation (uv resolve/download/sync).

    Output lines are delivered to ``on_detail`` on the GUI thread via a queued
    signal (the worker must never touch widgets directly). Returns
    ``(python_path, error_traceback)`` — ``error_traceback`` is ``None`` on
    success, and ``python_path`` falls back to ``default_python`` on failure or
    when ``prepare_fn`` returns ``None``.
    """
    import threading
    from PySide6.QtCore import QEventLoop, QObject, Signal

    class _Signals(QObject):
        detail = Signal(str)
        done = Signal()

    signals = _Signals()
    state: dict = {"python_path": default_python, "error": None}

    def _work() -> None:
        try:
            result = prepare_fn(signals.detail.emit)
            if result is not None:
                state["python_path"] = result
        except Exception:
            import traceback
            state["error"] = traceback.format_exc()
        finally:
            signals.done.emit()

    loop = QEventLoop()
    signals.detail.connect(on_detail)  # queued (worker → GUI thread)
    signals.done.connect(loop.quit)    # queued; pending even if emitted before exec()
    thread = threading.Thread(target=_work, daemon=True)
    thread.start()
    loop.exec()                        # GUI thread spins → splash repaints
    thread.join(timeout=1.0)
    return state["python_path"], state["error"]


def _run_with_startup_window(workspace_name: str | None, sciqlop_file: str | None) -> tuple[int, Path | None]:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication
    from SciQLop.components.startup.startup_window import StartupWindow

    existing = QApplication.instance()
    app = existing or QApplication(sys.argv[:1])

    window = StartupWindow()
    window.center_on_screen()
    window.show()
    window.set_phase("Initializing...")
    app.processEvents()

    _apply_proxy_settings()

    workspace_dir = resolve_workspace_dir(workspace_name, sciqlop_file)
    dev_mode = _is_editable_install()
    default_python = Path(sys.executable)

    if dev_mode:
        def prepare_fn(on_output):
            _prepare_workspace_dev(workspace_dir, on_output=on_output)
            return None
    else:
        def prepare_fn(on_output):
            from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace
            return prepare_workspace(workspace_dir, on_output=on_output)

    window.set_phase("Preparing workspace...")
    app.processEvents()

    python_path, prep_error = _prepare_on_worker_thread(
        prepare_fn, default_python, window.set_detail
    )
    if prep_error is not None:
        window.show_error(prep_error)
        app.exec()
        return 1, workspace_dir

    xcb_warning = check_xcb_cursor()
    if xcb_warning:
        window.show_warning(xcb_warning)
        loop = QEventLoop()
        window.warning_acknowledged.connect(loop.quit)
        loop.exec()

    window.set_phase("Starting SciQLop...")
    window.set_detail("")
    app.processEvents()

    ready_dir = tempfile.mkdtemp(prefix="sciqlop_startup_")
    ready_file = Path(ready_dir) / "ready"

    env = os.environ.copy()
    env["SCIQLOP_WORKSPACE_DIR"] = str(workspace_dir)
    env["SPEASY_SKIP_INIT_PROVIDERS"] = "1"
    env[READY_FILE_ENV] = str(ready_file)
    env["PYTHONNOUSERSITE"] = "1"

    log_path = _last_launch_log_path()
    try:
        log_file = open(log_path, "w", encoding="utf-8", errors="replace")
    except OSError:
        # If we can't open the log file, fall back to a sink that drops writes
        # rather than crash the launcher.
        import io
        log_file = io.StringIO()
        log_path = None
    proc: subprocess.Popen | None = None
    try:
        log_file.write(f"$ {python_path} -m SciQLop.sciqlop_app\n")
        log_file.flush()

        proc = subprocess.Popen(
            [str(python_path), "-m", "SciQLop.sciqlop_app"],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        import threading
        stderr_lines: list[str] = []
        drain_threads: list[threading.Thread] = []

        def _drain(stream, label: str, capture: list[str] | None):
            for line in stream:
                if capture is not None:
                    capture.append(line)
                try:
                    log_file.write(f"[{label}] {line}")
                    log_file.flush()
                except Exception:
                    pass

        for stream, label, capture in (
            (proc.stdout, "out", None),
            (proc.stderr, "err", stderr_lines),
        ):
            t = threading.Thread(target=_drain, args=(stream, label, capture), daemon=True)
            t.start()
            drain_threads.append(t)

        def check_ready():
            if ready_file.exists():
                window.close()
                app.processEvents()
                try:
                    ready_file.unlink()
                except OSError:
                    pass
                app.quit()
            elif proc.poll() is not None:
                timer.stop()
                window.show_error(
                    f"SciQLop process exited with code {proc.returncode}.\n\n"
                    f"Full output: {log_path}\n\n"
                    f"{''.join(stderr_lines)}"
                )

        timer = QTimer()
        timer.timeout.connect(check_ready)
        timer.start(100)

        app.exec()
        timer.stop()

        # Wait for the subprocess to exit before closing the log so that any
        # output produced after the splash window closed (i.e. for the rest of
        # the SciQLop session) still lands in last-launch.log.
        exit_code = proc.wait() if proc.poll() is None else proc.returncode
        for t in drain_threads:
            t.join(timeout=2.0)
        return exit_code, workspace_dir
    except Exception:
        # If anything in the subprocess setup raised, surface it to the user
        # rather than letting the launcher crash silently.
        import traceback
        try:
            window.show_error(traceback.format_exc())
            app.exec()
        except Exception:
            pass
        if proc is not None and proc.poll() is None:
            proc.kill()
        return 1, workspace_dir
    finally:
        try:
            log_file.close()
        except Exception:
            pass
        shutil.rmtree(ready_dir, ignore_errors=True)


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


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace_name = args.workspace
    sciqlop_file = args.sciqlop_file

    while True:
        exit_code, workspace_dir = _run_with_startup_window(workspace_name, sciqlop_file)
        sciqlop_file = None  # only consumed once, on the first iteration

        if exit_code == EXIT_RESTART:
            continue
        elif exit_code == EXIT_SWITCH_WORKSPACE:
            target = _read_switch_target(workspace_dir) if workspace_dir else None
            if target:
                workspace_name = target
                continue
            print("Switch-workspace requested but no target found — exiting", file=sys.stderr)
            return exit_code
        else:
            return exit_code


if __name__ == "__main__":
    sys.exit(main())
