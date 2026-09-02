"""SciQLop launcher — workspace-aware supervisor process.

In production (PyPI, AppImage, DMG, MSIX), the launcher creates a
self-contained workspace venv (no --system-site-packages, since e564d6aaf)
and spawns the Qt app as a subprocess.

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
SWITCH_HANDOFF_FILE_ENV = "SCIQLOP_SWITCH_HANDOFF_FILE"


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


def _most_recently_used_workspace(workspaces_root: Path) -> Path | None:
    """Return the workspace dir with the newest .last_used marker, or None.

    Only directories containing a workspace.sciqlop manifest and a .last_used
    marker are candidates. last_used() returns an ISO timestamp string, which
    sorts chronologically as text.
    """
    from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest

    if not workspaces_root.is_dir():
        return None
    used = [
        (WorkspaceManifest.last_used(d), d)
        for d in workspaces_root.iterdir()
        if (d / "workspace.sciqlop").is_file()
    ]
    used = [(ts, d) for ts, d in used if ts]
    if not used:
        return None
    used.sort(key=lambda t: t[0], reverse=True)
    return used[0][1]


def resolve_workspace_dir(
    workspace_name: str | None,
    sciqlop_file: str | None,
) -> Path:
    from SciQLop.components.workspaces.backend.settings import SciQLopWorkspacesSettings

    settings = SciQLopWorkspacesSettings()
    workspaces_root = Path(settings.workspaces_dir).expanduser()

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
        candidate = Path(workspace_name).expanduser()
        if candidate.is_absolute():
            return candidate
        return workspaces_root / workspace_name

    if settings.reopen_last_workspace:
        last = _most_recently_used_workspace(workspaces_root)
        if last is not None:
            return last

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


def _switch_handoff_path() -> Path:
    """Where a native-mode session (see ``main()``) leaves the target of a
    workspace switch for the C++ launcher's next round to pick up.

    A per-launcher-process path the native launcher chose itself (sibling of
    its own ready-marker file — see ``launcher/src/launcher.cpp``'s
    ``RoundScratchFiles``) and told us about via ``SWITCH_HANDOFF_FILE_ENV``,
    not a fixed path this module would have to guess: a fixed path can go
    stale (a launcher killed after this was written but before the next
    round read it) or collide between two concurrent launcher instances.

    Native mode is only ever entered because the native launcher already set
    ``READY_FILE_ENV`` (see ``_choose_run_session()``), and it must always set
    this alongside it — a missing var here is a native-launcher bug, so this
    raises rather than silently falling back to some other path.
    """
    path = os.environ.get(SWITCH_HANDOFF_FILE_ENV)
    if not path:
        raise RuntimeError(
            f"{SWITCH_HANDOFF_FILE_ENV} is not set — the native launcher must set it "
            f"alongside {READY_FILE_ENV}"
        )
    return Path(path)


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


def _spawn_app_logged(
    python_path: Path, env: dict, echo: bool = False
) -> tuple[subprocess.Popen, list[str], Path | None]:
    """Start the SciQLop subprocess, tee-ing its stdout/stderr into
    last-launch.log on background threads.

    Returns the process, the stderr lines captured so far (mutated in place as
    more arrive — used to show an error if the process exits early), and the
    log path (``None`` if it could not be opened, in which case output is
    silently dropped rather than crashing the launcher).

    ``echo``, when true, also writes each line to the real console
    (stdout lines to ``sys.stdout``, stderr lines to ``sys.stderr``) as it
    arrives — used by the console entry point, which has no splash to show
    progress on.

    simplify: the caller isn't given the drain threads to join, so a return
    right after the subprocess exits can race a few lines of trailing output
    still being flushed to last-launch.log (each drain thread closes the log
    itself once its stream hits EOF). Upgrade to returning the threads too, if
    last-launch.log is ever seen truncated.
    """
    import threading

    log_path = _last_launch_log_path()
    try:
        log_file = open(log_path, "w", encoding="utf-8", errors="replace")
    except OSError:
        import io
        log_file = io.StringIO()
        log_path = None

    log_file.write(f"$ {python_path} -m SciQLop.sciqlop_app\n")
    log_file.flush()

    proc = subprocess.Popen(
        [str(python_path), "-m", "SciQLop.sciqlop_app"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    stderr_lines: list[str] = []
    streams = ((proc.stdout, "out", None), (proc.stderr, "err", stderr_lines))
    remaining = [len(streams)]
    close_lock = threading.Lock()

    def _drain(stream, label: str, capture: list[str] | None):
        console = sys.stdout if label == "out" else sys.stderr
        try:
            for line in stream:
                if capture is not None:
                    capture.append(line)
                if echo:
                    try:
                        console.write(line)
                        console.flush()
                    except Exception:
                        pass
                try:
                    log_file.write(f"[{label}] {line}")
                    log_file.flush()
                except Exception:
                    pass
        finally:
            with close_lock:
                remaining[0] -= 1
                if remaining[0] == 0:
                    try:
                        log_file.close()
                    except Exception:
                        pass

    for stream, label, capture in streams:
        threading.Thread(target=_drain, args=(stream, label, capture), daemon=True).start()

    return proc, stderr_lines, log_path


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

    workspace_dir = None
    try:
        workspace_dir = resolve_workspace_dir(workspace_name, sciqlop_file)
    except Exception:
        import traceback
        window.show_error(traceback.format_exc())
        app.exec()
        return 1, workspace_dir

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

    proc: subprocess.Popen | None = None
    try:
        proc, stderr_lines, log_path = _spawn_app_logged(python_path, env)

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

        exit_code = proc.wait() if proc.poll() is None else proc.returncode
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
        shutil.rmtree(ready_dir, ignore_errors=True)


def _qt_available() -> bool:
    """Whether the GUI stack is usable: importable, and — on Linux — able to
    reach a display server.

    ``pip install sciqlop`` provides only the launcher; the application (and
    PySide6 with it) is installed into the workspace venv. There is no splash
    to show in that case, so the launcher reports progress on the console it
    was started from. A headless Linux session (no DISPLAY, WAYLAND_DISPLAY,
    or QT_QPA_PLATFORM) hits the same fallback even when PySide6 IS
    importable, since constructing a QApplication would just abort.
    """
    try:
        import PySide6.QtCore  # noqa: F401
        import PySide6.QtWidgets  # noqa: F401
    except ImportError:
        return False
    if platform.system() == "Linux":
        return bool(
            os.environ.get("DISPLAY")
            or os.environ.get("WAYLAND_DISPLAY")
            or os.environ.get("QT_QPA_PLATFORM")
        )
    return True


def _choose_run_session():
    """Pick the launcher path: the startup-window splash, or the console.

    An already-set READY_FILE_ENV means the native C++ launcher spawned this
    process itself and owns the splash — the console path must be used
    regardless of Qt availability, or two splashes would race each other.
    """
    if READY_FILE_ENV in os.environ:
        return _run_on_console
    return _run_with_startup_window if _qt_available() else _run_on_console


def _run_on_console(workspace_name: str | None, sciqlop_file: str | None) -> tuple[int, Path | None]:
    """Prepare the workspace and run SciQLop with no splash.

    Output goes straight to the terminal (and last-launch.log) rather than
    only a log file: the user is already looking at one.
    """
    _apply_proxy_settings()

    workspace_dir = None
    try:
        workspace_dir = resolve_workspace_dir(workspace_name, sciqlop_file)
        print(f"Preparing workspace {workspace_dir} ...", flush=True)
        if _is_editable_install():
            _prepare_workspace_dev(workspace_dir, on_output=print)
            python_path = Path(sys.executable)
        else:
            from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace
            python_path = prepare_workspace(workspace_dir, on_output=print)
    except Exception:
        import traceback
        message = "Workspace preparation failed:\n" + traceback.format_exc()
        print(message, file=sys.stderr)
        try:
            _last_launch_log_path().write_text(message, encoding="utf-8")
        except OSError:
            pass
        return 1, workspace_dir

    if warning := check_xcb_cursor():
        print(warning, file=sys.stderr)

    env = os.environ.copy()
    env["SCIQLOP_WORKSPACE_DIR"] = str(workspace_dir)
    env["SPEASY_SKIP_INIT_PROVIDERS"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    # This path neither sets nor strips READY_FILE_ENV: when this launcher
    # picked the console path itself (no Qt / headless), there's no splash to
    # close so it's simply absent from os.environ. When a native C++ launcher
    # forced this path (M15), READY_FILE_ENV is already set in os.environ and
    # is inherited as-is — the child does wait on it, and the native launcher
    # (not this process) is the one that owns and closes the splash.

    print("Starting SciQLop ...", flush=True)
    proc, _stderr_lines, log_path = _spawn_app_logged(
        python_path, env, echo=sys.stdout is not None
    )
    exit_code = proc.wait()
    if exit_code != 0:
        print(f"SciQLop exited with code {exit_code}. Full output: {log_path}", file=sys.stderr)
    return exit_code, workspace_dir


def _prepare_workspace_dev(workspace_dir: Path, on_output=None) -> None:
    """Set up workspace directory, metadata, and install plugin deps in dev mode."""
    from SciQLop.components.workspaces.backend.workspace_migration import migrate_workspace
    from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
    from SciQLop.components.plugins.plugin_deps import collect_plugin_dependencies
    from SciQLop.components.workspaces.backend.workspace_setup import get_globally_enabled_plugins, get_plugin_folders
    from SciQLop.components.workspaces.backend.uv import uv_command
    from SciQLop.components.workspaces.backend.workspace_venv import _run_uv
    from SciQLop.components.workspaces.backend.workspace_project import strip_host_provided
    from SciQLop.components.workspaces.backend.lab_assets import repair_lab_assets

    workspace_dir.mkdir(parents=True, exist_ok=True)
    migrate_workspace(workspace_dir)

    manifest_path = workspace_dir / "workspace.sciqlop"
    if manifest_path.exists():
        manifest = WorkspaceManifest.load_or_repair(manifest_path)
    else:
        manifest = WorkspaceManifest.default_manifest(workspace_dir.name)
        manifest.save(manifest_path)

    plugin_deps = collect_plugin_dependencies(
        plugin_folders=get_plugin_folders(),
        enabled_plugins=get_globally_enabled_plugins(),
        workspace_plugins_add=manifest.plugins_add,
        workspace_plugins_remove=manifest.plugins_remove,
    )
    all_deps = strip_host_provided(plugin_deps + manifest.requires)
    if all_deps:
        try:
            cmd = uv_command("pip", "install", *all_deps)
            _run_uv(cmd, on_output)
        except Exception as e:
            print(f"Warning: failed to install plugin/workspace deps: {e}")

    # Dev mode never creates a workspace .venv (see module docstring) — it runs
    # JupyterLab straight out of the dev base venv, so that's the venv that
    # needs the same jupyterlab/jupyterlab-js self-heal the prod path gets via
    # prepare_workspace().
    dev_venv_dir = Path(sys.executable).parent.parent
    repair_lab_assets(dev_venv_dir, on_output=on_output)


def _run_single_session_for_native_launcher(workspace_name: str | None, sciqlop_file: str | None) -> int:
    """Run exactly one session under the native C++ launcher, which owns the
    restart (64) / workspace-switch (65) round loop itself (see
    ``launcher/src/main.cpp``) — this must never loop internally, or the two
    loops would race each other's splash and process supervision.

    A switch target still gets consumed from ``.sciqlop_switch_target`` here
    (Python already knows the workspace dir it just ran in), but handed to the
    native launcher's next round via the handoff file instead of being reused
    for another iteration.
    """
    run_session = _choose_run_session()
    exit_code, workspace_dir = run_session(workspace_name, sciqlop_file)

    if exit_code == EXIT_SWITCH_WORKSPACE:
        target = _read_switch_target(workspace_dir) if workspace_dir else None
        if target:
            _switch_handoff_path().write_text(target + "\n", encoding="utf-8")
        else:
            print("Switch-workspace requested but no target found — exiting", file=sys.stderr)

    return exit_code


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace_name = args.workspace
    sciqlop_file = args.sciqlop_file

    if READY_FILE_ENV in os.environ:
        return _run_single_session_for_native_launcher(workspace_name, sciqlop_file)

    run_session = _choose_run_session()

    while True:
        exit_code, workspace_dir = run_session(workspace_name, sciqlop_file)
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
