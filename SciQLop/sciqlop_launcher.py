"""SciQLop launcher — workspace-aware supervisor process.

In production (PyPI, AppImage, DMG, MSIX), the launcher creates a workspace
venv with --system-site-packages and spawns the Qt app as a subprocess.

In development mode (editable install), the launcher skips venv creation
and runs the Qt app directly using the current Python, since the dev venv
already has all dependencies.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

EXIT_RESTART = 64
EXIT_SWITCH_WORKSPACE = 65
SWITCH_WORKSPACE_FILE = ".sciqlop_switch_target"


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
            from SciQLop.core.workspace_archive import import_workspace
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


def run_sciqlop_app_inprocess(workspace_dir: Path) -> int:
    """Run the SciQLop Qt app in the current process (development mode).

    Used when SciQLop is installed as editable — no subprocess needed since
    the current Python already has all dependencies.
    """
    os.environ["SCIQLOP_WORKSPACE_DIR"] = str(workspace_dir)
    os.environ["SPEASY_SKIP_INIT_PROVIDERS"] = "1"
    from SciQLop.sciqlop_app import main as app_main
    app_main()
    # Check for restart/switch signals
    if os.environ.get("RESTART_SCIQLOP") is not None:
        return EXIT_RESTART
    return 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace_dir = resolve_workspace_dir(args.workspace, args.sciqlop_file)
    dev_mode = _is_editable_install()

    while True:
        if dev_mode:
            # Development mode: skip venv, run in-process
            workspace_dir.mkdir(parents=True, exist_ok=True)
            exit_code = run_sciqlop_app_inprocess(workspace_dir)
        else:
            # Production mode: prepare workspace venv and spawn subprocess
            from SciQLop.core.workspace_setup import prepare_workspace
            python_path = prepare_workspace(workspace_dir)
            exit_code = run_sciqlop_app(python_path, workspace_dir)

        if exit_code == EXIT_RESTART:
            continue
        elif exit_code == EXIT_SWITCH_WORKSPACE:
            target = _read_switch_target(workspace_dir)
            if target:
                workspace_dir = resolve_workspace_dir(
                    workspace_name=target, sciqlop_file=None
                )
            continue
        else:
            return exit_code


if __name__ == "__main__":
    sys.exit(main())
