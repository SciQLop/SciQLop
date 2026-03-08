"""Workspace virtual environment manager using uv."""

import subprocess
import sys
from pathlib import Path

from SciQLop.components.workspaces.backend.uv import uv_command


class WorkspaceVenv:
    """Manages a virtual environment inside a workspace directory."""

    def __init__(self, workspace_dir: Path | str):
        self._workspace_dir = Path(workspace_dir)
        self._venv_dir = self._workspace_dir / ".venv"

    @property
    def python_path(self) -> Path:
        """Path to the venv's Python executable."""
        return self._venv_dir / "bin" / "python"

    @property
    def exists(self) -> bool:
        """Whether the venv directory and its Python executable exist."""
        return self._venv_dir.exists() and self.python_path.exists()

    def create(self) -> None:
        """Create the workspace venv with --system-site-packages."""
        cmd = uv_command(
            "venv",
            str(self._venv_dir),
            "--system-site-packages",
            "--python",
            sys.executable,
        )
        subprocess.run(cmd, check=True)

    def sync(self, locked: bool = False) -> None:
        """Run uv sync in the workspace directory."""
        args = ("sync", "--locked") if locked else ("sync",)
        cmd = uv_command(*args)
        subprocess.run(cmd, check=True, cwd=str(self._workspace_dir))

    def ensure(self) -> None:
        """Create the venv if it doesn't exist."""
        if not self.exists:
            self.create()
