"""Implementation of %install line magic — install packages and record them in the workspace."""
import subprocess
import shlex

from IPython.core.error import UsageError


def _run_uv_install(packages: list[str]) -> subprocess.CompletedProcess:
    from SciQLop.components.workspaces.backend.uv import uv_command
    return subprocess.run(uv_command("pip", "install", *packages), capture_output=True, text=True)


def _record_in_manifest(packages: list[str]):
    from SciQLop.components.workspaces import workspaces_manager_instance
    wm = workspaces_manager_instance()
    if wm is None:
        return
    ws = wm.workspace
    if ws is None:
        return
    ws.record_dependencies(packages)


def install_magic(line: str):
    """%install <package> [package2 ...]

    Install Python packages into the current workspace using uv and
    record them in the .sciqlop manifest so they persist across restarts.
    """
    packages = shlex.split(line)
    if not packages:
        raise UsageError("Usage: %install <package> [package2 ...]")

    print(f"Installing: {' '.join(packages)}")
    result = _run_uv_install(packages)

    if result.returncode != 0:
        print(result.stderr)
        raise UsageError(f"Installation failed (exit code {result.returncode})")

    print(result.stdout)

    from SciQLop.user_api.threading import invoke_on_main_thread
    invoke_on_main_thread(_record_in_manifest, packages)
    print(f"Recorded in workspace manifest: {', '.join(packages)}")
