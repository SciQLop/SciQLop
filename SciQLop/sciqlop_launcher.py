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


def _run_with_startup_window(workspace_dir: Path, default_python: Path, prepare_fn) -> int:
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtWidgets import QApplication
    from SciQLop.resources import qInitResources
    from SciQLop.components.startup.startup_window import StartupWindow

    existing = QApplication.instance()
    app = existing or QApplication(sys.argv[:1])
    qInitResources()

    window = StartupWindow()
    window.center_on_screen()
    window.show()
    window.set_phase("Preparing workspace...")
    app.processEvents()

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

    proc = subprocess.Popen(
        [str(python_path), "-m", "SciQLop.sciqlop_app"],
        env=env,
        stderr=subprocess.PIPE,
        text=True,
    )
    # Drain stderr in a background thread to prevent pipe buffer deadlock
    import threading
    stderr_lines: list[str] = []

    def _drain_stderr():
        for line in proc.stderr:
            stderr_lines.append(line)

    threading.Thread(target=_drain_stderr, daemon=True).start()

    def check_ready():
        if ready_file.exists():
            window.close()
            app.quit()
        elif proc.poll() is not None:
            timer.stop()
            window.show_error(
                f"SciQLop process exited with code {proc.returncode}.\n\n"
                f"{''.join(stderr_lines)}"
            )

    timer = QTimer()
    timer.timeout.connect(check_ready)
    timer.start(100)

    app.exec()
    timer.stop()

    shutil.rmtree(ready_dir, ignore_errors=True)

    if proc.poll() is None:
        return proc.wait()
    return proc.returncode


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
    workspace_dir = resolve_workspace_dir(args.workspace, args.sciqlop_file)
    dev_mode = _is_editable_install()

    while True:
        if dev_mode:
            def prepare_fn(on_output):
                _prepare_workspace_dev(workspace_dir, on_output=on_output)
                return None
            exit_code = _run_with_startup_window(workspace_dir, Path(sys.executable), prepare_fn)
        else:
            def prepare_fn(on_output):
                from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace
                return prepare_workspace(workspace_dir, on_output=on_output)
            exit_code = _run_with_startup_window(workspace_dir, Path(sys.executable), prepare_fn)

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
