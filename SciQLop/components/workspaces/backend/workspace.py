import os
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
from SciQLop.components.workspaces.backend.workspace_project import _deduplicate_requirements
from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)


class Workspace(QObject):
    name_changed = Signal(str)

    def __init__(self, manifest: WorkspaceManifest, parent=None):
        super().__init__(parent)
        self._manifest = manifest
        self._manifest_path = Path(manifest.directory) / "workspace.sciqlop"

    def activate(self):
        """Make this workspace the active one: chdir, add to sys.path, touch timestamp."""
        os.chdir(self._manifest.directory)
        if self._manifest.directory not in sys.path:
            sys.path.insert(0, self._manifest.directory)
        WorkspaceManifest.touch_last_used(self._manifest.directory)

    @property
    def workspace_dir(self) -> str:
        return self._manifest.directory

    @property
    def name(self) -> str:
        return self._manifest.name

    @name.setter
    def name(self, value: str):
        self._manifest.name = value
        self._manifest.save(self._manifest_path)
        self.name_changed.emit(value)

    @property
    def dependencies(self) -> list[str]:
        return self._manifest.requires

    def _uv_install(self, packages: list[str]) -> subprocess.CompletedProcess:
        from .live_install import guarded_install
        return guarded_install(packages)

    def add_packages(self, specs: list[str]) -> dict:
        """Install packages into the workspace venv (uv) and record the newly
        added ones in the manifest so they persist across restarts and venv
        rebuilds. Synchronous/blocking — call off the GUI thread.

        Returns {"ok", "installed", "already_present", "error"}."""
        already_present = [s for s in specs if s in self._manifest.requires]
        to_install = [s for s in specs if s not in self._manifest.requires]
        if not to_install:
            return {"ok": True, "installed": [],
                    "already_present": already_present, "error": ""}
        result = self._uv_install(to_install)
        if result.returncode != 0:
            log.error("Failed to install %s: %s", to_install, result.stderr)
            return {"ok": False, "installed": [],
                    "already_present": already_present, "error": result.stderr}
        self._manifest.requires.extend(to_install)
        # Collapse any same-package duplicates (e.g. "scipy" + "scipy>=1.11"),
        # last spec wins — same canonical-name rule the launcher applies when it
        # regenerates pyproject.toml, so the manifest matches the resolved venv.
        self._manifest.requires[:] = _deduplicate_requirements(self._manifest.requires)
        self._manifest.save(self._manifest_path)
        return {"ok": True, "installed": to_install,
                "already_present": already_present, "error": ""}

    def add_files(self, files: list[str], destination: str = ""):
        for f in files:
            dest = os.path.join(self.workspace_dir, destination, os.path.basename(f))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(f, dest)

    def add_directory(self, directory: str, destination: str = ""):
        dest = os.path.join(self.workspace_dir, destination)
        shutil.copytree(directory, dest, dirs_exist_ok=True)

    def __str__(self):
        return self.name
