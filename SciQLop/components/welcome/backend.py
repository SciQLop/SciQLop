from __future__ import annotations

import base64
import glob
import json
import os
import subprocess
import threading
import urllib.request

from PySide6.QtCore import QBuffer, QFileSystemWatcher, QIODevice, QObject, Signal, Slot

from SciQLop.components.workspaces.backend.example import Example
from SciQLop.components.workspaces.backend.settings import SciQLopWorkspacesSettings
from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
from SciQLop.components.workspaces.backend.workspaces_manager import workspaces_manager_instance, WorkspaceManager
from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)

_EXAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "examples")


def _icon_to_data_uri(icon) -> str:
    if icon is None:
        return ""
    from PySide6.QtCore import QSize
    pixmap = icon.pixmap(QSize(80, 80))
    if pixmap.isNull():
        return ""
    buf = QBuffer()
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.data().data()).decode()


def _workspace_to_dict(ws: WorkspaceManifest) -> dict:
    ws_dir = ws.directory
    image_path = os.path.join(ws_dir, ws.image) if ws.image else ""
    return {
        "name": ws.name,
        "directory": ws_dir,
        "description": ws.description,
        "last_used": WorkspaceManifest.last_used(ws_dir),
        "last_modified": WorkspaceManifest.last_modified(ws_dir),
        "image": image_path if image_path and os.path.exists(image_path) else "",
        "is_default": ws.default,
        "requires": ws.requires,
    }


def _example_to_dict(ex: Example) -> dict:
    return {
        "name": ex.name,
        "description": ex.description,
        "image": ex.image if ex.image and os.path.exists(ex.image) else "",
        "tags": ex.tags,
        "directory": str(ex.directory),
    }


def _discover_examples() -> list[Example]:
    results = []
    for json_file in sorted(glob.glob(os.path.join(_EXAMPLES_DIR, "*", "*.json"))):
        try:
            results.append(Example(json_file))
        except Exception:
            pass
    return results


_MOCK_NEWS = [
    {"icon": "\U0001f389", "title": "SciQLop 0.8 released", "date": "2026-03-10"},
    {"icon": "\U0001f4e6", "title": "New MMS data products available", "date": "2026-03-08"},
    {"icon": "\U0001f4a1", "title": "Tip: Use virtual products for derived quantities", "date": "2026-03-05"},
]

_MOCK_FEATURED = [
    {"name": "AMDA Provider", "type": "plugin", "description": "Access AMDA data directly in SciQLop", "author": "IRAP", "tags": ["data-provider", "amda"], "stars": 42},
    {"name": "Wavelet Analysis", "type": "plugin", "description": "Continuous wavelet transform for time series", "author": "LPP", "tags": ["analysis", "wavelets"], "stars": 28},
    {"name": "MMS Mission Study", "type": "workspace", "description": "Pre-configured workspace for MMS data analysis", "author": "IRAP", "tags": ["mms", "magnetosphere"], "stars": 15},
    {"name": "Solar Wind Tutorial", "type": "example", "description": "Introduction to solar wind data analysis with SciQLop", "author": "Community", "tags": ["tutorial", "solar-wind"], "stars": 33},
]


class WelcomeBackend(QObject):
    """Python backend exposed to the welcome page via QWebChannel."""

    workspace_list_changed = Signal()
    quickstart_changed = Signal()
    appstore_requested = Signal()
    latest_release_ready = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        workspaces_dir = SciQLopWorkspacesSettings().workspaces_dir
        self._watcher = QFileSystemWatcher([workspaces_dir], self)
        self._watch_workspace_subdirs(workspaces_dir)
        self._watcher.directoryChanged.connect(self._on_directory_changed)
        from SciQLop.core.sciqlop_application import sciqlop_app
        sciqlop_app().quickstart_shortcuts_added.connect(lambda _: self.quickstart_changed.emit())

    def _watch_workspace_subdirs(self, workspaces_dir: str):
        if not os.path.exists(workspaces_dir):
            return
        subdirs = [
            os.path.join(workspaces_dir, d)
            for d in os.listdir(workspaces_dir)
            if os.path.isdir(os.path.join(workspaces_dir, d))
        ]
        if subdirs:
            self._watcher.addPaths(subdirs)

    def _on_directory_changed(self, path: str):
        workspaces_dir = SciQLopWorkspacesSettings().workspaces_dir
        if path == workspaces_dir:
            self._watch_workspace_subdirs(workspaces_dir)
        self.workspace_list_changed.emit()

    # --- Data slots ---

    @Slot(result=str)
    def list_workspaces(self) -> str:
        workspaces = workspaces_manager_instance().list_workspaces()
        workspaces.sort(key=lambda ws: WorkspaceManifest.last_used(ws.directory), reverse=True)
        return json.dumps([_workspace_to_dict(ws) for ws in workspaces])

    @Slot(result=str)
    def list_examples(self) -> str:
        return json.dumps([_example_to_dict(ex) for ex in _discover_examples()])

    @Slot(result=str)
    def get_palette(self) -> str:
        from SciQLop.components.theming.palette import SCIQLOP_PALETTE
        return json.dumps(SCIQLOP_PALETTE)

    @Slot(result=str)
    def list_quickstart_shortcuts(self) -> str:
        from SciQLop.core.sciqlop_application import sciqlop_app
        app = sciqlop_app()
        result = []
        for name in app.quickstart_shortcuts:
            info = app.quickstart_shortcut(name) or {}
            result.append({
                "name": name,
                "description": info.get("description", ""),
                "icon": _icon_to_data_uri(info.get("icon")),
            })
        return json.dumps(result)

    @Slot(result=str)
    def get_hero_workspace(self) -> str:
        workspaces = workspaces_manager_instance().list_workspaces()
        non_default = [ws for ws in workspaces if not ws.default]
        if not non_default:
            return "null"
        non_default.sort(key=lambda ws: WorkspaceManifest.last_used(ws.directory), reverse=True)
        return json.dumps(_workspace_to_dict(non_default[0]))

    @Slot(result=str)
    def list_news(self) -> str:
        return json.dumps(_MOCK_NEWS)

    @Slot(result=str)
    def list_featured_packages(self) -> str:
        return json.dumps(_MOCK_FEATURED)

    @Slot(result=str)
    def get_current_version(self) -> str:
        from SciQLop import __version__
        return __version__

    _GITHUB_RELEASE_URL = "https://api.github.com/repos/SciQLop/SciQLop/releases/latest"

    @Slot()
    def fetch_latest_release(self) -> None:
        def _fetch():
            try:
                req = urllib.request.Request(
                    self._GITHUB_RELEASE_URL,
                    headers={"Accept": "application/vnd.github.v3+json"},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read())
                result = json.dumps({
                    "tag": data["tag_name"],
                    "name": data.get("name", data["tag_name"]),
                    "url": data["html_url"],
                    "published": data.get("published_at", ""),
                })
            except Exception as e:
                log.debug(f"Could not fetch latest release: {e}")
                result = "null"
            self.latest_release_ready.emit(result)

        threading.Thread(target=_fetch, daemon=True).start()

    # --- Action slots ---

    @Slot(str)
    def open_workspace(self, directory: str) -> None:
        from SciQLop.sciqlop_app import switch_workspace
        switch_workspace(directory)

    @Slot()
    def create_workspace(self) -> None:
        workspaces_manager_instance().create_workspace()

    @Slot(str)
    def delete_workspace(self, directory: str) -> None:
        workspaces_manager_instance().delete_workspace(directory)
        self.workspace_list_changed.emit()

    @Slot(str)
    def duplicate_workspace(self, directory: str) -> None:
        workspaces_manager_instance().duplicate_workspace(directory)
        self.workspace_list_changed.emit()

    @Slot(result=str)
    def get_active_workspace_dir(self) -> str:
        manager = workspaces_manager_instance()
        if manager.has_workspace:
            return json.dumps(manager.workspace.workspace_dir)
        return json.dumps(None)

    @Slot(str, str, result=str)
    def add_example_to_workspace(self, example_dir: str, workspace_dir: str) -> str:
        missing = WorkspaceManager.add_example_to_workspace(example_dir, workspace_dir)
        return json.dumps({"missing_dependencies": missing})

    @Slot(str, str)
    def add_dependencies_to_workspace(self, workspace_dir: str, dependencies_json: str) -> None:
        from SciQLop.components.workspaces.backend.uv import uv_command
        deps = json.loads(dependencies_json)
        manifest_path = os.path.join(workspace_dir, "workspace.sciqlop")
        manifest = WorkspaceManifest.load(manifest_path)
        new_deps = [d for d in deps if d not in manifest.requires]
        if new_deps:
            manifest.requires.extend(new_deps)
            manifest.save(manifest_path)
            try:
                cmd = uv_command("pip", "install", *new_deps)
                subprocess.run(cmd, check=True)
            except Exception as e:
                log.error(f"Failed to install dependencies: {e}")

    @Slot()
    def open_appstore(self) -> None:
        self.appstore_requested.emit()

    @Slot(str)
    def run_quickstart(self, name: str) -> None:
        from SciQLop.core.sciqlop_application import sciqlop_app
        shortcut = sciqlop_app().quickstart_shortcut(name)
        if shortcut:
            shortcut["callback"]()

    @Slot(str, str)
    def remove_dependency_from_workspace(self, workspace_dir: str, dependency: str) -> None:
        manifest_path = os.path.join(workspace_dir, "workspace.sciqlop")
        try:
            manifest = WorkspaceManifest.load(manifest_path)
            manifest.requires = [d for d in manifest.requires if d != dependency]
            manifest.save(manifest_path)
        except Exception as e:
            log.error(f"Failed to remove dependency: {e}")

    @Slot(str)
    def open_url(self, url: str) -> None:
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtCore import QUrl
        QDesktopServices.openUrl(QUrl(url))

    @Slot(str, str)
    def update_workspace_field(self, directory: str, field_json: str) -> None:
        update = json.loads(field_json)
        manifest_path = os.path.join(directory, "workspace.sciqlop")
        try:
            manifest = WorkspaceManifest.load(manifest_path)
            field, value = update["field"], update["value"]
            if hasattr(manifest, field):
                setattr(manifest, field, value)
                manifest.save(manifest_path)
        except Exception as e:
            log.error(f"Failed to update workspace field: {e}")
