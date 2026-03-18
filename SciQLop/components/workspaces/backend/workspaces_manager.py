import os
import shutil
from datetime import datetime
from re import sub as re_sub
from typing import Optional
from PySide6.QtCore import QObject, Signal, Slot, QFile
from PySide6.QtGui import QIcon

from SciQLop.components.workspaces.backend.settings import SciQLopWorkspacesSettings
from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
from SciQLop.components.workspaces.backend.workspace import Workspace
from SciQLop.components.theming.icons import register_icon
from SciQLop.components.workspaces.backend.example import Example
from SciQLop.core.sciqlop_application import sciqlop_app
from SciQLop.components.jupyter.kernel import KernelManager
from SciQLop.core.common import background_run
from SciQLop.components.sciqlop_logging import getLogger
import uuid
from SciQLopPlots import Icons

register_icon("Jupyter", lambda: QIcon("://icons/Jupyter_logo.png"))

log = getLogger(__name__)


def _ensure_migrated(ws_dir: str) -> bool:
    """Migrate workspace.json → workspace.sciqlop if needed. Returns True if manifest exists."""
    from SciQLop.components.workspaces.backend.workspace_migration import migrate_workspace, restore_legacy_json
    manifest_path = os.path.join(ws_dir, "workspace.sciqlop")
    if os.path.exists(manifest_path):
        restore_legacy_json(ws_dir)
        return True
    if os.path.exists(os.path.join(ws_dir, "workspace.json")):
        migrate_workspace(ws_dir)
        return os.path.exists(manifest_path)
    return False


def list_existing_workspaces() -> list[WorkspaceManifest]:
    workspaces_dir = SciQLopWorkspacesSettings().workspaces_dir
    if not os.path.exists(workspaces_dir):
        return []
    results = []
    for entry in os.listdir(workspaces_dir):
        ws_dir = os.path.join(workspaces_dir, entry)
        if not os.path.isdir(ws_dir):
            continue
        if not _ensure_migrated(ws_dir):
            continue
        try:
            results.append(WorkspaceManifest.load(os.path.join(ws_dir, "workspace.sciqlop")))
        except Exception as e:
            log.error(f"Error loading workspace {ws_dir}: {e}")
    return results


_EXAMPLE_METADATA_FILES = {"example.json", "image.png"}


def _copy_example_tree(src: str, dest: str):
    for entry in os.listdir(src):
        if entry in _EXAMPLE_METADATA_FILES:
            continue
        src_path = os.path.join(src, entry)
        dest_path = os.path.join(dest, entry)
        if os.path.isdir(src_path):
            shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
        else:
            os.makedirs(dest, exist_ok=True)
            shutil.copy2(src_path, dest_path)


class WorkspaceManager(QObject):
    workspace_loaded = Signal(Workspace)

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self._quit = False
        self._workspace: Optional[Workspace] = None

        sciqlop_app().add_quickstart_shortcut("JupyterLab", "Open JupyterLab in browser",
                                              Icons.get_icon("Jupyter"),
                                              self.open_in_browser)

        self._kernel_manager = KernelManager(parent=self)
        self._default_workspace: WorkspaceManifest = self._ensure_default_workspace_exists()
        self._auto_load_workspace()

    def _auto_load_workspace(self):
        target = os.environ.get("SCIQLOP_WORKSPACE_DIR")
        if not target:
            return
        default_dir = os.path.join(SciQLopWorkspacesSettings().workspaces_dir, "default")
        if os.path.realpath(target) == os.path.realpath(default_dir):
            return
        manifest_path = os.path.join(target, "workspace.sciqlop")
        if os.path.exists(manifest_path):
            log.info(f"Auto-loading workspace: {target}")
            self.load_workspace(WorkspaceManifest.load(manifest_path))

    def _ensure_default_workspace_exists(self) -> WorkspaceManifest:
        default_dir = os.path.join(SciQLopWorkspacesSettings().workspaces_dir, "default")
        manifest_path = os.path.join(default_dir, "workspace.sciqlop")
        if not os.path.exists(manifest_path):
            return self._create_workspace("default", default_dir, description="Default workspace", default=True)
        manifest = WorkspaceManifest.load(manifest_path)
        if not manifest.default:
            manifest.default = True
            manifest.save(manifest_path)
        return manifest

    def open_in_browser(self):
        self._kernel_manager.open_in_browser()

    def widget(self):
        return self._kernel_manager.widget()

    def wrap_qt(self, obj):
        return self._kernel_manager.wrap_qt(obj)

    @staticmethod
    def _create_workspace(name: str, path: str, **kwargs) -> WorkspaceManifest:
        os.makedirs(path, exist_ok=True)
        manifest = WorkspaceManifest(name=name, **kwargs)
        manifest_path = os.path.join(path, "workspace.sciqlop")
        dest = os.path.join(path, "image.png")
        if not os.path.exists(dest):
            QFile.copy(":/splash.png", dest)
            os.chmod(dest, 0o644)
        manifest.image = "image.png"
        manifest.save(manifest_path)
        return WorkspaceManifest.load(manifest_path)

    def create_workspace(self, name: Optional[str] = None, **kwargs):
        name = name or f"New workspace from {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        log.info(f"Creating workspace {name}")
        directory = os.path.join(SciQLopWorkspacesSettings().workspaces_dir, uuid.uuid4().hex)
        self._create_workspace(name, directory, **kwargs)
        from SciQLop.sciqlop_app import switch_workspace
        switch_workspace(directory)

    @staticmethod
    def add_example_to_workspace(example_path: str, workspace_dir: str) -> list[str]:
        example = Example(example_path)
        slug = re_sub(r'[^\w\-]', '_', example.name).strip('_')
        dest = os.path.join(workspace_dir, slug)
        _copy_example_tree(example_path, dest)
        manifest = WorkspaceManifest.load(os.path.join(workspace_dir, "workspace.sciqlop"))
        return [d for d in example.dependencies if d not in manifest.requires]

    def load_workspace(self, manifest: WorkspaceManifest | None = None) -> Workspace:
        if self._workspace is not None:
            raise Exception("Workspace already created")
        if manifest is None:
            manifest = self._default_workspace
        self._workspace = Workspace(manifest=manifest)
        self.workspace_loaded.emit(self._workspace)
        self.push_variables({"workspace": self._workspace})
        return self._workspace

    @Slot(str)
    def delete_workspace(self, workspace: str):
        shutil.rmtree(workspace, ignore_errors=True)

    @Slot(str)
    def duplicate_workspace(self, workspace: str, background: bool = False):
        def duplicate(directory: str):
            copy_dir = directory + "_copy"
            shutil.copytree(directory, copy_dir)
            manifest_path = os.path.join(copy_dir, "workspace.sciqlop")
            manifest = WorkspaceManifest.load(manifest_path)
            manifest.name = f"Copy of {manifest.name}"
            manifest.save(manifest_path)
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
    def list_workspaces() -> list[WorkspaceManifest]:
        return list_existing_workspaces()

    def push_variables(self, variable_dict):
        self._kernel_manager.push_variables(variable_dict)

    def start(self):
        self.push_variables({
            "app": self.wrap_qt(sciqlop_app()),
            "background_run": background_run,
        })
        self._kernel_manager.start()

    def quit(self):
        self._kernel_manager.shutdown()
        self._quit = True


def workspaces_manager_instance():
    app = sciqlop_app()
    if not hasattr(app, "workspaces_manager"):
        app.workspaces_manager = WorkspaceManager(parent=app)
    return app.workspaces_manager
