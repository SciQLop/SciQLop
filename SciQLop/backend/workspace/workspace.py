import datetime

from ..settings import ConfigEntry
from ..IPythonKernel import InternalIPKernel
from ..jupyter_clients.clients_manager import ClientsManager as IPythonKernelClientsManager
# from .workspace_spec import WorkspaceSpecFile
from ..data_models.models import WorkspaceSpec, WorkspaceSpecFile
from ..common.process import Process
from ..common.pip_process import pip_install_requirements
from ..common import ensure_dir_exists
from ..sciqlop_logging import getLogger
from PySide6.QtCore import QObject, Signal, Slot
from platformdirs import *
from typing import List, Optional, AnyStr
import shutil
import os
import sys

WORKSPACES_DIR_CONFIG_ENTRY = ConfigEntry(section="CORE", key2="WORKSPACE_DIR", default=str(
    os.path.join(user_data_dir(appname="sciqlop", appauthor="LPP", ensure_exists=True), "workspaces")),
                                          description="Directory where SciQLop will store its data")

log = getLogger(__name__)


def create_workspace_dir(workspace_dir: str):
    ensure_dir_exists(workspace_dir)
    ensure_dir_exists(os.path.join(workspace_dir, "dependencies"))
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
            self._workspace_dir = str(os.path.join(WORKSPACES_DIR_CONFIG_ENTRY.get(), workspace_dir or "default"))
        else:
            self._workspace_dir = workspace_spec.directory
        self._dependencies_dir = str(os.path.join(self._workspace_dir, "dependencies"))
        self._ipykernel: Optional[InternalIPKernel] = None

        create_workspace_dir(self._workspace_dir)

        self._workspace_spec = workspace_spec or WorkspaceSpecFile(
            os.path.join(self._workspace_dir, "workspace_spec.json"))
        self._workspace_spec.last_used = datetime.datetime.now().isoformat()
        self.add_to_python_path(self._dependencies_dir, prepend=True, permanent=False)
        os.chdir(self._workspace_dir)
        self._ensure_all_dependencies_installed()

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
        self._ensure_all_dependencies_installed()

    def install_dependencies(self, dependencies: List[str]):
        self._workspace_spec.dependencies.extend(dependencies)
        self._ensure_all_dependencies_installed()

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

    @Slot()
    def _dependencies_installed(self):
        log.info("Dependencies installed")
        log.info(self._install_proc.stdout)
        log.info(self._install_proc.stderr)

    def _ensure_all_dependencies_installed(self):
        if len(self.dependencies):
            if 'SCIQLOP_BUNDLED' in os.environ:
                git_dependencies = list(filter(lambda x: x.startswith("git+"), self.dependencies))
                if len(git_dependencies):
                    from PySide6.QtWidgets import QMessageBox
                    QMessageBox.warning(None, "SciQLop", "The following dependencies are git repositories:\n\n"
                                                         f"{', '.join(git_dependencies)}\n\n"
                                                         "These dependencies are not supported in the bundled version of SciQLop because git is not provided.")
                    return

            log.info(f"Installing dependencies: {self.dependencies}")
            with open(os.path.join(self._workspace_dir, "requirements.txt"), 'w') as f:
                f.write('\n'.join(self.dependencies))
            self._install_proc = pip_install_requirements(
                requirements_file=os.path.join(self._workspace_dir, "requirements.txt"),
                install_dir=self._dependencies_dir, cwd=self._workspace_dir)
            self._install_proc.finished.connect(self.dependencies_installed)
            self._install_proc.finished.connect(self._dependencies_installed)
            self._install_proc.start()
        else:
            log.info("No dependencies to install")
            self.dependencies_installed.emit()
