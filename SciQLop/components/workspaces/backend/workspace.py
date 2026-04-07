import os
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
from SciQLop.components.workspaces.backend.uv import uv_command
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
        return subprocess.run(uv_command("pip", "install", *packages), capture_output=True, text=True)

    def install_dependency(self, dep: str) -> bool:
        if dep in self._manifest.requires:
            return True
        result = self._uv_install([dep])
        if result.returncode != 0:
            log.error("Failed to install %s: %s", dep, result.stderr)
            return False
        self._manifest.requires.append(dep)
        self._manifest.save(self._manifest_path)
        return True

    def install_dependencies(self, deps: list[str]) -> bool:
        added = [d for d in deps if d not in self._manifest.requires]
        if not added:
            return True
        result = self._uv_install(added)
        if result.returncode != 0:
            log.error("Failed to install %s: %s", added, result.stderr)
            return False
        self._manifest.requires.extend(added)
        self._manifest.save(self._manifest_path)
        return True

    def record_dependencies(self, deps: list[str]):
        """Save deps to manifest without installing (caller already installed)."""
        added = [d for d in deps if d not in self._manifest.requires]
        if added:
            self._manifest.requires.extend(added)
            self._manifest.save(self._manifest_path)

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
