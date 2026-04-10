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
        "version": ex.version,
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
    {"icon": "\U0001f4c2", "title": "Catalog Browser \u2014 browse, create, edit and overlay catalogs on plots", "date": "2026-04-10"},
    {"icon": "\U0001f6cd\ufe0f", "title": "App Store \u2014 discover and install community plugins", "date": "2026-04-10"},
    {"icon": "\u2318", "title": "Command Palette \u2014 press Ctrl+K to search and execute any action", "date": "2026-04-10"},
    {"icon": "\U0001f3a8", "title": "New dark & neutral themes with runtime switching", "date": "2026-04-10"},
    {"icon": "\U0001f4d3", "title": "Workspace overhaul \u2014 TOML manifests, uv venvs, examples & templates", "date": "2026-04-10"},
    {"icon": "\U0001f50c", "title": "Plugin system \u2014 entry-point discovery, dependency resolution, product context menus", "date": "2026-04-10"},
    {"icon": "\U0001f9ea", "title": "Expanded user API \u2014 catalog service, %plot / %%vp magics, fluent API, graphic primitives", "date": "2026-04-10"},
    {"icon": "\U0001f4e6", "title": "Packaging \u2014 AppImage, Windows installer, Flatpak, and macOS DMG with notarization", "date": "2026-04-10"},
]

_APPSTORE_URL = "https://sciqlop.github.io/sciqlop-appstore/index.json"


class WelcomeBackend(QObject):
    """Python backend exposed to the welcome page via QWebChannel."""

    workspace_list_changed = Signal()
    quickstart_changed = Signal()
    appstore_requested = Signal()
    latest_release_ready = Signal(str)
    templates_changed = Signal()
    dependency_install_finished = Signal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        workspaces_dir = SciQLopWorkspacesSettings().workspaces_dir
        self._watcher = QFileSystemWatcher([workspaces_dir], self)
        self._watch_workspace_subdirs(workspaces_dir)
        self._watcher.directoryChanged.connect(self._on_directory_changed)
        from SciQLop.core.sciqlop_application import sciqlop_app
        sciqlop_app().quickstart_shortcuts_added.connect(lambda _: self.quickstart_changed.emit())
        from SciQLop.components.plotting.panel_template import templates_dir
        tpl_dir = str(templates_dir())
        self._watcher.addPath(tpl_dir)
        self._watcher.directoryChanged.connect(self._on_templates_dir_changed)
        self._templates_dir = tpl_dir

    def _on_templates_dir_changed(self, path: str):
        if path == self._templates_dir:
            self.templates_changed.emit()

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
    def list_templates(self) -> str:
        from SciQLop.components.plotting.panel_template import list_templates as _list_templates, preview_path
        from pathlib import Path
        results = []
        for t in _list_templates():
            src = Path(t._source_path) if t._source_path else None
            img = ""
            if src:
                pp = preview_path(str(src))
                if pp.exists():
                    img = str(pp)
            results.append({
                "name": t.name,
                "stem": src.stem if src else t.name,
                "description": t.description,
                "image": img,
            })
        return json.dumps(results)

    @Slot(str)
    def load_template(self, name: str) -> None:
        from SciQLop.components.plotting.panel_template import find_template
        from SciQLop.user_api.gui import get_main_window
        t = find_template(name)
        if t:
            t.create_panel(get_main_window())

    @Slot(str)
    def delete_template(self, name: str) -> None:
        from SciQLop.components.plotting.panel_template import delete_template as _delete
        _delete(name)

    @Slot(str, str)
    def rename_template(self, old_name: str, new_name: str) -> None:
        from SciQLop.components.plotting.panel_template import rename_template as _rename
        _rename(old_name, new_name)

    @Slot()
    def import_template(self) -> None:
        from PySide6.QtWidgets import QFileDialog
        from SciQLop.components.plotting.panel_template import PanelTemplate, templates_dir
        from pathlib import Path
        import shutil
        path, _ = QFileDialog.getOpenFileName(
            None, "Import template",
            str(Path.home()),
            "Templates (*.json *.yaml *.yml)",
        )
        if path:
            dest = templates_dir() / Path(path).name
            shutil.copy2(path, dest)

    featured_packages_ready = Signal(str)

    @Slot()
    def fetch_featured_packages(self) -> None:
        def _fetch():
            try:
                req = urllib.request.Request(
                    _APPSTORE_URL,
                    headers={"Accept": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    packages = json.loads(resp.read())
                self.featured_packages_ready.emit(json.dumps(packages))
            except Exception as e:
                log.debug(f"Could not fetch featured packages: {e}")
                self.featured_packages_ready.emit(json.dumps([]))

        threading.Thread(target=_fetch, daemon=True).start()

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
        result = WorkspaceManager.add_example_to_workspace(example_dir, workspace_dir)
        return json.dumps(result)

    @Slot(str, result=str)
    def get_installed_examples(self, workspace_dir: str) -> str:
        manifest_path = os.path.join(workspace_dir, "workspace.sciqlop")
        if not os.path.exists(manifest_path):
            return json.dumps([])
        from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
        manifest = WorkspaceManifest.load(manifest_path)
        return json.dumps([{"name": e.name, "version": e.version} for e in manifest.examples])

    @Slot(str, str)
    def add_dependencies_to_workspace(self, workspace_dir: str, dependencies_json: str) -> None:
        from SciQLop.components.workspaces.backend.uv import uv_command
        deps = json.loads(dependencies_json)
        manifest_path = os.path.join(workspace_dir, "workspace.sciqlop")
        manifest = WorkspaceManifest.load(manifest_path)
        new_deps = [d for d in deps if d not in manifest.requires]
        if not new_deps:
            return

        active_dir = os.environ.get("SCIQLOP_WORKSPACE_DIR", "")
        is_active = os.path.realpath(workspace_dir) == os.path.realpath(active_dir)

        def _install():
            try:
                if is_active:
                    cmd = uv_command("pip", "install", *new_deps)
                else:
                    cmd = uv_command("pip", "install", "--dry-run", *new_deps)
                subprocess.run(cmd, check=True, capture_output=True, text=True)
            except Exception as e:
                log.error(f"Failed to install dependencies: {e}")
                self.dependency_install_finished.emit(
                    json.dumps({"ok": False, "deps": new_deps, "dir": workspace_dir, "error": str(e)}))
                return
            manifest.requires.extend(new_deps)
            manifest.save(manifest_path)
            self.dependency_install_finished.emit(
                json.dumps({"ok": True, "deps": new_deps, "dir": workspace_dir}))

        threading.Thread(target=_install, daemon=True).start()

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
