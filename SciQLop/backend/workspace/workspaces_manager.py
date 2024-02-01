import os
from typing import List, Optional
from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QIcon
from mypy.plugins import functools

from .workspace import WORKSPACES_DIR_CONFIG_ENTRY
from ..data_models import WorkspaceSpecFile
from .workspace import Workspace
from ..icons import register_icon, icons
from ..examples import Example
from ..sciqlop_application import sciqlop_app, QEventLoop
from ..IPythonKernel import InternalIPKernel
from ..common import background_run
from ..jupyter_clients.clients_manager import ClientsManager as IPythonKernelClientsManager
import uuid

register_icon("Jupyter", QIcon("://icons/Jupyter_logo.svg"))
register_icon("JupyterConsole", QIcon("://icons/JupyterConsole.svg"))


def list_existing_workspaces() -> List[WorkspaceSpecFile]:
    return list(
        map(
            lambda workspace_dir: WorkspaceSpecFile(workspace_dir),
            filter(
                os.path.isdir,
                map(lambda workspace_dir: os.path.join(WORKSPACES_DIR_CONFIG_ENTRY.get(), workspace_dir),
                    os.listdir(WORKSPACES_DIR_CONFIG_ENTRY.get()))
            )
        )
    )


class WorkspaceManager(QObject):
    workspace_loaded = Signal(Workspace)
    workspace_deleted = Signal(Workspace)
    jupyterlab_started = Signal(str)

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self._quit = False
        self._workspace: Optional[Workspace] = None

        sciqlop_app().add_quickstart_shortcut("IPython", "Start an IPython console in current workspace or a new one",
                                              icons.get("JupyterConsole"),
                                              self.new_qt_console)
        sciqlop_app().add_quickstart_shortcut("JupyterLab", "Start JupyterLab in current workspace or a new one",
                                              icons.get("Jupyter"),
                                              self.start_jupyterlab)

        self._ipykernel: Optional[InternalIPKernel] = None
        self._ipykernel_clients_manager: Optional[IPythonKernelClientsManager] = None

    def _init_kernel(self):
        if self._ipykernel is not None:
            return
        self._ipykernel = InternalIPKernel()
        self._ipykernel.init_ipkernel()
        self.push_variables({"app": sciqlop_app(), "background_run": background_run})
        self._ipykernel_clients_manager = IPythonKernelClientsManager(self._ipykernel.connection_file)
        self._ipykernel_clients_manager.jupyterlab_started.connect(self.jupyterlab_started)

    def start_jupyterlab(self):
        self._init_kernel()
        if self._workspace is None:
            self.create_workspace()
        self._ipykernel_clients_manager.start_jupyterlab(cwd=self._workspace.workspace_dir)

    def new_qt_console(self):
        self._init_kernel()
        if self._workspace is None:
            self.create_workspace()
        self._ipykernel_clients_manager.new_qt_console(cwd=self._workspace.workspace_dir)

    def create_workspace(self, name: Optional[str] = None, **kwargs) -> Workspace:
        self._init_kernel()
        if self._workspace is not None:
            raise Exception("Workspace already created")
        name = name or "default"
        print(f"Creating workspace {name}")
        # using uuid4 to avoid name collision and simplify workspace renaming without having to move the directory and
        # update python path at runtime
        directory = os.path.join(WORKSPACES_DIR_CONFIG_ENTRY.get(), uuid.uuid4().hex)
        spec = WorkspaceSpecFile(directory, name=name, **kwargs)
        return self.load_workspace(spec)

    def load_example(self, example_path: str) -> Workspace:
        print(f"Loading example from {example_path}")
        example = Example(example_path)
        if self._workspace is None:
            self.create_workspace(example.name, description=example.description, image=os.path.basename(example.image),
                                  notebooks=[os.path.basename(example.notebook)])
        assert self._workspace is not None
        self._workspace.add_files([example.notebook, example.image])
        self._workspace.install_dependencies(example.dependencies)
        assert self._ipykernel_clients_manager is not None
        if not self._ipykernel_clients_manager.has_running_jupyterlab:
            self.start_jupyterlab()
        return self._workspace

    def load_workspace(self, workspace_spec: WorkspaceSpecFile) -> Workspace:
        if self._workspace is not None:
            raise Exception("Workspace already created")
        self._workspace = Workspace(workspace_spec=workspace_spec)
        self.workspace_loaded.emit(self._workspace)
        self.push_variables({"workspace": self._workspace})
        if len(workspace_spec.notebooks) and os.path.exists(workspace_spec.notebooks[0]):
            self.start_jupyterlab()
        return self._workspace

    @Slot(str)
    def delete_workspace(self, workspace: str):
        os.rmdir(workspace)
        self.workspace_deleted.emit(workspace)

    @property
    def workspace(self) -> Workspace:
        if self._workspace is None:
            return self.create_workspace()
        return self._workspace

    @staticmethod
    def workspace_spec(name) -> WorkspaceSpecFile:
        return WorkspaceSpecFile(str(os.path.join(WORKSPACES_DIR_CONFIG_ENTRY.get(), name)))

    @staticmethod
    def list_workspaces() -> List[WorkspaceSpecFile]:
        return list_existing_workspaces()

    def push_variables(self, variable_dict):
        if self._ipykernel is None:
            self._init_kernel()
        self._ipykernel.push_variables(variable_dict)

    def start(self):
        if self._ipykernel is None:
            self._init_kernel()
        self._ipykernel.start()

    def quit(self):
        if self._ipykernel is None:
            return
        self._ipykernel_clients_manager.cleanup()
        self._ipykernel.ipykernel.shell.run_cell("quit()")
        self._quit = True


def workspaces_manager_instance():
    app = sciqlop_app()
    if not hasattr(app, "workspaces_manager"):
        app.workspaces_manager = WorkspaceManager(app)
    return app.workspaces_manager
