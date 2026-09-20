"""The app-wide `workspace_loaded` signal must not keep a dead main window alive
as a receiver: a lambda closing over `self` fired after the window was deleted
and raised "Internal C++ object already deleted" inside a later test."""
import sys

import pytest

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


@pytest.fixture
def fresh_workspace_manager(qapp, monkeypatch):
    """Let the test build its own WorkspaceManager, then put the shared one back.
    (`monkeypatch.delattr(raising=False)` records nothing when the attribute is
    absent, which would leak the test's manager into later tests.)"""
    monkeypatch.setattr(sys, "path", list(sys.path))  # Workspace.activate() prepends
    previous = qapp.__dict__.pop("workspaces_manager", None)
    yield
    created = qapp.__dict__.pop("workspaces_manager", None)
    if created is not None:
        created.deleteLater()
    if previous is not None:
        qapp.workspaces_manager = previous


def test_window_built_after_a_workspace_autoload_still_gets_its_title_and_tour(
        qapp, sciqlop_resources, tmp_path, monkeypatch, fresh_workspace_manager):
    """SCIQLOP_WORKSPACE_DIR makes the manager load its workspace while it is
    being constructed -- before the window can connect to `workspace_loaded`."""
    from SciQLop.components.onboarding.backend.settings import OnboardingSettings
    from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow

    ws_dir = tmp_path / "autoloaded"
    ws_dir.mkdir()
    WorkspaceManifest(name="autoloaded").save(ws_dir / "workspace.sciqlop")
    monkeypatch.setenv("SCIQLOP_WORKSPACE_DIR", str(ws_dir))
    with OnboardingSettings() as s:
        s.completed_tours = {}

    mw = SciQLopMainWindow()

    assert mw.windowTitle() == "SciQLop - autoloaded"
    assert mw._tour_timer.isActive()
    destroy_main_window(mw)
