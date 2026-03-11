import os
import shutil
import sys
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)


class Workspace(QObject):
    name_changed = Signal(str)

    def __init__(self, manifest: WorkspaceManifest, parent=None):
        super().__init__(parent)
        self._manifest = manifest
        self._manifest_path = Path(manifest.directory) / "workspace.sciqlop"
        os.chdir(manifest.directory)
        sys.path.insert(0, manifest.directory)
        WorkspaceManifest.touch_last_used(manifest.directory)

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

    def install_dependency(self, dep: str):
        if dep not in self._manifest.requires:
            self._manifest.requires.append(dep)
            self._manifest.save(self._manifest_path)

    def install_dependencies(self, deps: list[str]):
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
