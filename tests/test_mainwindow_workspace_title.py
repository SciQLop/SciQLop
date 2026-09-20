"""The app-wide `workspace_loaded` signal must not keep a dead main window alive
as a receiver: a lambda closing over `self` fired after the window was deleted
and raised "Internal C++ object already deleted" inside a later test."""
from .fixtures import *


def test_workspace_loaded_after_window_destroyed_is_silent(qapp, sciqlop_resources, qtbot):
    from SciQLop.components.workspaces.backend.workspace import Workspace
    from SciQLop.components.workspaces.backend.workspaces_manager import workspaces_manager_instance
    from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow

    mw = SciQLopMainWindow()
    destroy_main_window(mw)

    workspaces_manager_instance().workspace_loaded.emit(
        Workspace(manifest=WorkspaceManifest(name="ghost")))
    qapp.processEvents()
