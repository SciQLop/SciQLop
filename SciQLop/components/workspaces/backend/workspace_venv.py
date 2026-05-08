"""Workspace virtual environment manager using uv."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
import sysconfig
from collections.abc import Callable
from pathlib import Path

from SciQLop.core.common.python import get_python
from SciQLop.components.workspaces.backend.uv import uv_command

_WINDOWS = os.name == "nt"
_SYSTEM_FINGERPRINT_FILENAME = ".sciqlop_system_fingerprint"


def _system_packages_fingerprint() -> str:
    """Hash the dist-info directory names in the bundled Python's site-packages.

    A workspace venv created with --system-site-packages inherits whatever is
    installed in the system layer.  When a SciQLop upgrade replaces the
    bundled PySide6 / SciQLopPlots binaries underneath an existing venv, the
    venv's own pinned copies and the system's new copies collide at import
    time (different ABIs).  This fingerprint changes whenever any package is
    added, removed, or re-versioned in the system layer, so the venv can be
    rebuilt against the new stack.
    """
    purelib = Path(sysconfig.get_paths()["purelib"])
    if not purelib.is_dir():
        return ""
    names = sorted(
        p.name for p in purelib.iterdir()
        if p.is_dir() and p.suffix == ".dist-info"
    )
    h = hashlib.sha256()
    for name in names:
        h.update(name.encode("utf-8"))
        h.update(b"\n")
    return h.hexdigest()


def _run_uv(cmd: list[str], on_output: Callable[[str], None] | None = None, **kwargs) -> None:
    if on_output is None:
        subprocess.run(cmd, check=True, **kwargs)
        return
    stderr_lines: list[str] = []
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE, text=True, **kwargs)
    for line in proc.stderr:
        stripped = line.rstrip("\n")
        stderr_lines.append(stripped)
        on_output(stripped)
    rc = proc.wait()
    if rc != 0:
        stderr = "\n".join(stderr_lines)
        raise RuntimeError(
            f"uv command failed (exit {rc}):\n"
            f"  {' '.join(cmd)}\n\n{stderr}"
        )


class WorkspaceVenv:
    """Manages a virtual environment inside a workspace directory."""

    def __init__(self, workspace_dir: Path | str):
        self._workspace_dir = Path(workspace_dir)
        self._venv_dir = self._workspace_dir / ".venv"

    @property
    def python_path(self) -> Path:
        """Path to the venv's Python executable."""
        if _WINDOWS:
            return self._venv_dir / "Scripts" / "python.exe"
        return self._venv_dir / "bin" / "python"

    @property
    def exists(self) -> bool:
        """Whether the venv directory and its Python executable exist."""
        return self._venv_dir.exists() and self.python_path.exists()

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

    def _read_pyvenv_cfg(self) -> dict[str, str]:
        cfg = self._venv_dir / "pyvenv.cfg"
        if not cfg.exists():
            return {}
        result = {}
        for line in cfg.read_text().splitlines():
            key, _, value = line.partition("=")
            if value:
                result[key.strip()] = value.strip()
        return result

    @property
    def _fingerprint_path(self) -> Path:
        return self._venv_dir / _SYSTEM_FINGERPRINT_FILENAME

    def _read_fingerprint(self) -> str:
        try:
            return self._fingerprint_path.read_text().strip()
        except OSError:
            return ""

    def _write_fingerprint(self) -> None:
        try:
            self._fingerprint_path.write_text(_system_packages_fingerprint())
        except OSError:
            pass

    def _needs_recreate(self) -> bool:
        if not self.exists:
            return True
        cfg = self._read_pyvenv_cfg()
        version = cfg.get("version_info", "")
        parts = version.split(".")
        if len(parts) < 2:
            return True
        if (int(parts[0]), int(parts[1])) != (sys.version_info.major, sys.version_info.minor):
            return True
        python = self.python_path
        if python.is_symlink() and not python.resolve().exists():
            return True
        if python.is_symlink() and str(python.resolve()) != str(Path(get_python()).resolve()):
            return True
        if self._read_fingerprint() != _system_packages_fingerprint():
            return True
        return False

    def ensure(self, on_output: Callable[[str], None] | None = None) -> None:
        """Create the venv if missing, wrong version, or stale paths."""
        if self._needs_recreate():
            if self._venv_dir.exists():
                shutil.rmtree(self._venv_dir)
            self.create(on_output=on_output)
            self._write_fingerprint()
