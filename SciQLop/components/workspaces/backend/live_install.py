"""Install packages into the workspace venv SciQLop is running from.

Shared by the app store, the ``%install`` magic and live plugin loading, so all
of them keep the running stack in place.
"""
import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from .uv import uv_command
from .workspace_project import _base_constraints, host_provided_overrides


def install_cmd(specs: List[str], override_file: Optional[str] = None,
                constraint_file: Optional[str] = None) -> List[str]:
    """uv command to install *specs*, trusting the platform certificate store.

    ``--native-tls`` lets uv use the OS certificate store, which is where a
    corporate proxy's MITM root CA lives — without it uv rejects the proxy's
    intercepted certificate and the install fails.

    ``--override``/``--constraint`` keep the install from pulling host-provided
    packages (SciQLop and the pinned base stack) from PyPI — without them uv
    resolves a wheel's transitive ``Requires-Dist: SciQLop`` against PyPI,
    dragging a mismatched SciQLop + pyside6/speasy/shiboken6 into the workspace
    venv, and can upgrade the Qt stack under the running process.
    """
    args = ["pip", "install", "--native-tls"]
    if override_file:
        args += ["--override", override_file]
    if constraint_file:
        args += ["--constraint", constraint_file]
    return uv_command(*args, *specs)


def write_requirements_file(directory: str, filename: str, lines: List[str]) -> Optional[str]:
    """Write *lines* to ``directory/filename``; return its path, or None if empty."""
    if not lines:
        return None
    path = os.path.join(directory, filename)
    Path(path).write_text("\n".join(lines) + "\n")
    return path


def guarded_install(specs: List[str]) -> subprocess.CompletedProcess:
    """Install *specs* with the running base stack pinned and SciQLop host-provided."""
    with tempfile.TemporaryDirectory() as isolation_dir:
        override_file = write_requirements_file(isolation_dir, "overrides.txt", host_provided_overrides())
        constraint_file = write_requirements_file(isolation_dir, "constraints.txt", _base_constraints())
        return subprocess.run(install_cmd(specs, override_file, constraint_file),
                              capture_output=True, text=True)
