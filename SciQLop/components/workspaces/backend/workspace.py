import datetime

from SciQLop.components.jupyter.IPythonKernel import InternalIPKernel
from SciQLop.components.jupyter.jupyter_clients.clients_manager import ClientsManager as IPythonKernelClientsManager
# from .workspace_spec import WorkspaceSpecFile
from .settings import SciQLopWorkspacesSettings
from SciQLop.core.data_models.models import WorkspaceSpecFile
from SciQLop.core.common import ensure_dir_exists
from SciQLop.components.sciqlop_logging import getLogger
from PySide6.QtCore import QObject, Signal
from typing import List, Optional
import shutil
import os
import sys


log = getLogger(__name__)


def create_workspace_dir(workspace_dir: str):
    ensure_dir_exists(workspace_dir)
    ensure_dir_exists(os.path.join(workspace_dir, "scripts"))


class Workspace(QObject):
    """Workspace class. Used to manage workspace. A workspace is a directory containing a workspace_spec.json file and specific dependencies for a given project.
    """
    _ipykernel_clients_manager: IPythonKernelClientsManager = None

    name_changed = Signal(str)
    kernel_started = Signal()
    dependencies_installed = Signal()

    def __init__(self, workspace_dir=None, parent=None, workspace_spec: Optional[WorkspaceSpecFile] = None):
        QObject.__init__(self, parent)
        self._mpl_backend = None
        if workspace_spec is None:
            self._workspace_dir = str(os.path.join(SciQLopWorkspacesSettings().workspaces_dir, workspace_dir or "default"))
        else:
            self._workspace_dir = workspace_spec.directory
        self._ipykernel: Optional[InternalIPKernel] = None

        create_workspace_dir(self._workspace_dir)

        self._workspace_spec = workspace_spec or WorkspaceSpecFile(
            os.path.join(self._workspace_dir, "workspace_spec.json"))
        self._workspace_spec.last_used = datetime.datetime.now().isoformat()
        os.chdir(self._workspace_dir)
        self.dependencies_installed.emit()

    @property
    def workspace_dir(self):
        return self._workspace_dir

    def add_to_python_path(self, path, prepend=True, permanent=False):
        if prepend:
            sys.path.insert(0, path)
        else:
            sys.path.append(path)
        if permanent:
            if prepend:
                self._workspace_spec.python_path.insert(0, path)
            else:
                self._workspace_spec.python_path.append(path)
            self._workspace_spec.save()

    @property
    def python_path(self):
        return self._workspace_spec.python_path

    @property
    def dependencies(self):
        return self._workspace_spec.dependencies

    def install_dependency(self, dependency):
        self._workspace_spec.dependencies.append(dependency)
        self._workspace_spec.save()

    def install_dependencies(self, dependencies: List[str]):
        self._workspace_spec.dependencies.extend(dependencies)
        self._workspace_spec.save()

    def add_files(self, files: List[str], destination: str = ""):
        for file in files:
            log.info(f"Copying {file} to {os.path.join(self._workspace_dir, destination)}")
            shutil.copy(file, os.path.join(self._workspace_dir, destination))

    def add_directory(self, directory: str, destination: str = ""):
        log.info(f"Coping {directory} to {os.path.join(self._workspace_dir, destination)}")
        shutil.copytree(directory, os.path.join(self._workspace_dir, destination))

    @property
    def name(self):
        return self._workspace_spec.name

    @name.setter
    def name(self, value):
        self._workspace_spec.name = value

