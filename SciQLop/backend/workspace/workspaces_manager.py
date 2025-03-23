import os
import shutil
from datetime import datetime
from typing import List, Optional, Union
from PySide6.QtCore import QObject, Signal, Slot, QFile, QTimer, QDir
from PySide6.QtGui import QIcon

from .workspace import WORKSPACES_DIR_CONFIG_ENTRY
from ..data_models import WorkspaceSpecFile
from .workspace import Workspace
from ..icons import register_icon
from ..examples import Example
from ..sciqlop_application import sciqlop_app, QEventLoop
from ..IPythonKernel import InternalIPKernel
from ..common import background_run
from ..sciqlop_logging import getLogger
from ..jupyter_clients.clients_manager import ClientsManager as IPythonKernelClientsManager
import uuid
from SciQLopPlots import  Icons


register_icon("Jupyter", QIcon("://icons/Jupyter_logo.png"))
register_icon("JupyterConsole", QIcon("://icons/JupyterConsole.png"))

log = getLogger(__name__)


def _try_load_workspace(workspace_dir):
    try:
        return WorkspaceSpecFile(workspace_dir)
    except Exception as e:
        log.error(f"Error loading workspace {workspace_dir}: {e}")
        return None


def list_existing_workspaces() -> List[WorkspaceSpecFile]:
    workspaces_dir = WORKSPACES_DIR_CONFIG_ENTRY.get()
    if not os.path.exists(workspaces_dir):
        return []
    return list(
        filter(
            lambda w: w is not None,
            map(
                _try_load_workspace,
                filter(
                    lambda workspace_dir: os.path.exists(os.path.join(workspace_dir, "workspace.json")),
                    filter(
                        lambda d: os.path.isdir(d) and d != 'default',
                        map(lambda workspace_dir: os.path.join(WORKSPACES_DIR_CONFIG_ENTRY.get(), workspace_dir),
                            os.listdir(WORKSPACES_DIR_CONFIG_ENTRY.get()))
                    )
                )
            )
        )
    )


class WorkspaceManager(QObject):
    workspace_loaded = Signal(Workspace)
    jupyterlab_started = Signal(str)

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self._quit = False
        self._deferred_variables = {}
        self._workspace: Optional[Workspace] = None

        sciqlop_app().add_quickstart_shortcut("JupyterLab", "Start JupyterLab in current workspace or a new one",
                                              Icons.get_icon("Jupyter"),
                                              self.start_jupyterlab)

        self._ipykernel: Optional[InternalIPKernel] = None
        self._ipykernel_clients_manager: Optional[IPythonKernelClientsManager] = None
        self._default_workspace: WorkspaceSpecFile = self._ensure_default_workspace_exists()

    def _init_kernel(self):
        if self._ipykernel is not None:
            return
        self._ipykernel = InternalIPKernel()
        self._ipykernel.init_ipkernel()
        self.push_variables({"app": sciqlop_app(), "background_run": background_run})
        self.push_variables(self._deferred_variables)
        self._ipykernel_clients_manager = IPythonKernelClientsManager(self._ipykernel.connection_file, parent=self)
        self._ipykernel_clients_manager.jupyterlab_started.connect(self.jupyterlab_started)

    def _ensure_default_workspace_exists(self) -> WorkspaceSpecFile:
        default_workspace = os.path.join(WORKSPACES_DIR_CONFIG_ENTRY.get(), "default")
        if not os.path.exists(default_workspace):
            return self._create_workspace("default", default_workspace, description="Default workspace",
                                          default_workspace=True)
        return WorkspaceSpecFile(default_workspace)

    def start_jupyterlab(self):
        self._init_kernel()
        w = self.workspace
        self._ipykernel_clients_manager.start_jupyterlab(cwd=w.workspace_dir)

    def new_qt_console(self):
        self._init_kernel()
        w = self.workspace
        self._ipykernel_clients_manager.new_qt_console(cwd=w.workspace_dir)

    @staticmethod
    def _create_workspace(name: str, path: str, **kwargs) -> WorkspaceSpecFile:
        spec = WorkspaceSpecFile(path, name=name, **kwargs)
        if spec.image == "":
            QFile.copy(":/splash.png", os.path.join(path, "image.png"))
            spec.image = "image.png"
        return spec

    def create_workspace(self, name: Optional[str] = None, **kwargs) -> Workspace:
        self._init_kernel()
        if self._workspace is not None:
            raise Exception("Workspace already created")
        name = name or f"New workspace from {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        log.info(f"Creating workspace {name}")
        # using uuid4 to avoid name collision and simplify workspace renaming without having to move the directory and
        # update python path at runtime
        directory = os.path.join(WORKSPACES_DIR_CONFIG_ENTRY.get(), uuid.uuid4().hex)
        spec = self._create_workspace(name, directory, **kwargs)
        return self.load_workspace(spec)

    def load_example(self, example_path: str) -> Workspace:
        log.info(f"Loading example from {example_path}")
        example = Example(example_path)
        if self._workspace is None:
            self.create_workspace(example.name, description=example.description, image=os.path.basename(example.image),
                                  notebooks=[os.path.basename(example.notebook)], dependencies=example.dependencies)
        assert self._workspace is not None
        self._workspace.add_files([example.notebook, example.image])
        for directory in filter(lambda d: os.path.isdir(os.path.join(example_path, d)), os.listdir(example_path)):
            self._workspace.add_directory(os.path.join(example_path, directory), directory)
        assert self._ipykernel_clients_manager is not None
        if not self._ipykernel_clients_manager.has_running_jupyterlab:
            self.start_jupyterlab()
        return self._workspace

    def load_workspace(self, workspace_spec: Union[WorkspaceSpecFile, str, None]) -> Workspace:
        if self._workspace is not None:
            raise Exception("Workspace already created")
        if isinstance(workspace_spec, str):
            workspace_spec = WorkspaceSpecFile(workspace_spec)
        if workspace_spec is None:
            workspace_spec = self._default_workspace
        self._workspace = Workspace(workspace_spec=workspace_spec)
        self.workspace_loaded.emit(self._workspace)
        self.push_variables({"workspace": self._workspace})
        if len(workspace_spec.notebooks) and os.path.exists(workspace_spec.notebooks[0]):
            self.start_jupyterlab()
        return self._workspace

    @Slot(str)
    def delete_workspace(self, workspace: str):
        shutil.rmtree(workspace, ignore_errors=True)

    @Slot(str)
    def duplicate_workspace(self, workspace: str, background: bool = False):
        def duplicate(directory: str):
            shutil.copytree(directory, directory + "_copy")
            spec = WorkspaceSpecFile(directory + "_copy")
            spec.name = f"Copy of {spec.name}"

        if background:
            log.info("Backgrounding duplicate")
            duplicate(workspace)
        else:
            duplicate(workspace)

    @property
    def workspace(self) -> Workspace:
        if not self.has_workspace:
            self.load_workspace(None)
        return self._workspace

    @property
    def has_workspace(self) -> bool:
        return self._workspace is not None

    @staticmethod
    def workspace_spec(name) -> WorkspaceSpecFile:
        return WorkspaceSpecFile(str(os.path.join(WORKSPACES_DIR_CONFIG_ENTRY.get(), name)))

    @staticmethod
    def list_workspaces() -> List[WorkspaceSpecFile]:
        return list_existing_workspaces()

    def push_variables(self, variable_dict):
        if self._ipykernel is None:
            self._deferred_variables.update(variable_dict)
        else:
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
        app.workspaces_manager = WorkspaceManager(parent=app)
    return app.workspaces_manager
