"""The app-wide `workspace_loaded` signal must not keep a dead main window alive
as a receiver: a lambda closing over `self` fired after the window was deleted
and raised "Internal C++ object already deleted" inside a later test."""
from .fixtures import *


def _loaded_workspace(name):
    from SciQLop.components.workspaces.backend.workspace import Workspace
    from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
    return Workspace(manifest=WorkspaceManifest(name=name))


def test_workspace_loaded_updates_the_window_title(qapp, sciqlop_resources):
    from SciQLop.components.workspaces.backend.workspaces_manager import workspaces_manager_instance
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow

    mw = SciQLopMainWindow()
    workspaces_manager_instance().workspace_loaded.emit(_loaded_workspace("titled"))

    assert mw.windowTitle() == "SciQLop - titled"
    destroy_main_window(mw)


def test_workspace_loaded_after_window_destroyed_is_silent(qapp, sciqlop_resources, qtbot):
    from SciQLop.components.workspaces.backend.workspaces_manager import workspaces_manager_instance
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow

    mw = SciQLopMainWindow()
    destroy_main_window(mw)

    with qtbot.capture_exceptions() as exceptions:
        workspaces_manager_instance().workspace_loaded.emit(_loaded_workspace("ghost"))
        qapp.processEvents()

    assert exceptions == []
