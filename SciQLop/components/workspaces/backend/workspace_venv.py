"""Workspace virtual environment manager using uv."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from SciQLop.core.common.files import write_text_atomic
from SciQLop.core.common.python import get_python
from SciQLop.components.workspaces.backend.uv import uv_command

_WINDOWS = os.name == "nt"


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
    def venv_dir(self) -> Path:
        """Path to the venv directory."""
        return self._venv_dir

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

    @property
    def has_sciqlop_installed(self) -> bool:
        """Whether a ``sync`` has ever actually installed SciQLop here.

        ``create()`` produces a working interpreter with no packages at all,
        so ``exists``/``python_path`` can't distinguish that from a venv whose
        last sync succeeded. The offline-sync fallback in ``prepare_workspace``
        needs this distinction: falling back to "keep running the existing
        venv" only makes sense when there is an existing app to keep running.

        Both the dist-info *and* the package directory are required: an
        interrupted install can leave dist-info behind with no ``SciQLop``
        package, which must not be reported as "installed".
        """
        for site in (
            *self._venv_dir.glob("lib/python*/site-packages"),
            self._venv_dir / "Lib" / "site-packages",
        ):
            if not site.is_dir():
                continue
            has_dist_info = any(site.glob("sciqlop-*.dist-info"))
            has_package = (site / "SciQLop" / "__init__.py").exists()
            if has_dist_info and has_package:
                return True
        return False

    def create(self, on_output: Callable[[str], None] | None = None) -> None:
        """Create a self-contained workspace venv.

        Deliberately *not* --system-site-packages: the workspace installs its
        own SciQLop, so inheriting the launcher's environment would shadow it
        with a second copy and reintroduce the C-extension mismatches that the
        base-package pinning used to guard against.
        """
        cmd = uv_command(
            "venv",
            str(self._venv_dir),
            "--clear",
            "--native-tls",
            "--python",
            get_python(),
        )
        _run_uv(cmd, on_output)

    def sync(self, locked: bool = False, on_output: Callable[[str], None] | None = None) -> None:
        """Run uv sync in the workspace directory."""
        args = ("sync", "--locked", "--native-tls") if locked else ("sync", "--native-tls")
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

    def _inherits_system_site_packages(self) -> bool:
        """Whether this venv predates self-contained workspaces.

        Such a venv has no SciQLop of its own — it read one out of the host —
        so it has to be rebuilt rather than synced into the new layout.
        """
        return self._read_pyvenv_cfg().get("include-system-site-packages", "").lower() == "true"

    def _venv_dir_present(self) -> bool:
        """Whether the venv has a python entry at all, symlink or not.

        Unlike ``exists``, this doesn't require the entry to *resolve* — a
        dangling symlink still counts as "present" here, because that's the
        repointable case C1 exists to handle, not a missing venv.
        """
        python = self.python_path
        return self._venv_dir.exists() and (python.is_symlink() or python.exists())

    def _version_mismatch(self, cfg: dict[str, str]) -> bool:
        parts = cfg.get("version_info", "").split(".")
        if len(parts) < 2:
            return True
        try:
            major, minor = int(parts[0]), int(parts[1])
        except ValueError:
            return True
        return (major, minor) != (sys.version_info.major, sys.version_info.minor)

    def _interpreter_name(self) -> str:
        return "python.exe" if _WINDOWS else "python3"

    def _missing_interpreter_link(self, cfg: dict[str, str]) -> bool:
        """H3: a copied (non-symlink) python whose ``home`` no longer holds
        an interpreter — Windows has no symlinks, so this is its equivalent
        of a dangling link, and unlike one it can't be repaired in place."""
        if self.python_path.is_symlink():
            return False
        home = cfg.get("home", "")
        if not home:
            return False
        return not (Path(home) / self._interpreter_name()).exists()

    def _needs_recreate(self) -> bool:
        if not self._venv_dir_present():
            return True
        cfg = self._read_pyvenv_cfg()
        if self._version_mismatch(cfg):
            return True
        if self._inherits_system_site_packages():
            return True
        if self._missing_interpreter_link(cfg):
            return True
        return False

    def _needs_repoint(self) -> bool:
        """The venv is otherwise fine, but its interpreter link (symlink
        target and/or ``pyvenv.cfg``'s ``home``) no longer points at
        ``get_python()`` — repair it in place instead of rebuilding."""
        if not self._venv_dir_present():
            return False
        cfg = self._read_pyvenv_cfg()
        if self._version_mismatch(cfg):
            return False
        python = self.python_path
        if not python.is_symlink():
            return False
        target = Path(get_python())
        if not python.resolve().exists() or python.resolve() != target.resolve():
            return True
        home = cfg.get("home", "")
        return bool(home) and Path(home).resolve() != target.parent.resolve()

    def _repoint_interpreter(self) -> None:
        target = Path(get_python())
        bin_dir = self.python_path.parent
        for entry in bin_dir.glob("python*"):
            if entry.is_symlink():
                entry.unlink()
                try:
                    entry.symlink_to(target)
                except FileExistsError:
                    pass  # another instance repointed it first; already correct
        self._rewrite_pyvenv_home(target.parent)

    def _rewrite_pyvenv_home(self, home: Path) -> None:
        cfg = self._venv_dir / "pyvenv.cfg"
        lines = [
            f"home = {home}" if line.partition("=")[0].strip() == "home" else line
            for line in cfg.read_text().splitlines()
        ]
        write_text_atomic(cfg, "\n".join(lines) + "\n")

    def ensure(self, on_output: Callable[[str], None] | None = None) -> None:
        """Create the venv if missing, wrong version, stale paths, or legacy;
        just repoint its interpreter link if that's the only thing stale."""
        if self._needs_recreate():
            if self._venv_dir.exists():
                if self._inherits_system_site_packages() and on_output is not None:
                    on_output(
                        "Rebuilding this workspace so it holds its own SciQLop "
                        "(one-time; it previously shared the application's)."
                    )
                shutil.rmtree(self._venv_dir)
            self.create(on_output=on_output)
        elif self._needs_repoint():
            self._repoint_interpreter()
            if on_output is not None:
                on_output(f"Re-linking workspace interpreter to {get_python()}")
