from __future__ import annotations

import base64
import glob
import json
import os

from PySide6.QtCore import QBuffer, QFileSystemWatcher, QIODevice, QObject, Signal, Slot

from SciQLop.components.workspaces.backend.example import Example
from SciQLop.components.workspaces.backend.settings import SciQLopWorkspacesSettings
from SciQLop.components.workspaces.backend.workspaces_manager import workspaces_manager_instance

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


def _workspace_to_dict(ws) -> dict:
    image_path = os.path.join(str(ws.directory), ws.image) if ws.image else ""
    return {
        "name": ws.name,
        "directory": str(ws.directory),
        "description": ws.description,
        "last_used": ws.last_used,
        "last_modified": ws.last_modified,
        "image": image_path if image_path and os.path.exists(image_path) else "",
        "is_default": ws.default_workspace,
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


class WelcomeBackend(QObject):
    """Python backend exposed to the welcome page via QWebChannel."""

    workspace_list_changed = Signal()
    quickstart_changed = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._watcher = QFileSystemWatcher([SciQLopWorkspacesSettings().workspaces_dir], self)
        self._watcher.directoryChanged.connect(lambda: self.workspace_list_changed.emit())
        from SciQLop.core.sciqlop_application import sciqlop_app
        sciqlop_app().quickstart_shortcuts_added.connect(lambda _: self.quickstart_changed.emit())

    # --- Data slots ---

    @Slot(result=str)
    def list_workspaces(self) -> str:
        workspaces = workspaces_manager_instance().list_workspaces()
        workspaces.sort(key=lambda ws: ws.last_used, reverse=True)
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

    # --- Action slots ---

    @Slot(str)
    def open_workspace(self, directory: str) -> None:
        manager = workspaces_manager_instance()
        for ws in manager.list_workspaces():
            if str(ws.directory) == directory:
                manager.load_workspace(ws)
                return

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

    @Slot(str)
    def open_example(self, directory: str) -> None:
        workspaces_manager_instance().load_example(directory)

    @Slot(str)
    def run_quickstart(self, name: str) -> None:
        from SciQLop.core.sciqlop_application import sciqlop_app
        shortcut = sciqlop_app().quickstart_shortcut(name)
        if shortcut:
            shortcut["callback"]()

    @Slot(str, str)
    def update_workspace_field(self, directory: str, field_json: str) -> None:
        manager = workspaces_manager_instance()
        update = json.loads(field_json)
        for ws in manager.list_workspaces():
            if str(ws.directory) == directory:
                field, value = update["field"], update["value"]
                if hasattr(ws, field):
                    setattr(ws, field, value)
                break
