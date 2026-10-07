"""Resetting a workspace's Python environment (the launcher's "Reset environment" button)."""
import shutil
from pathlib import Path

import pytest

from SciQLop.components.workspaces.backend import workspace_reset
from SciQLop.components.workspaces.backend.workspace_archive import is_excluded
from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
from SciQLop.components.workspaces.backend.workspace_project import MAIN_PIN


@pytest.fixture
def workspace(tmp_path):
    ws = tmp_path / "ws"
    (ws / ".venv" / "lib").mkdir(parents=True)
    (ws / ".venv" / "lib" / "pkg.py").write_text("x")
    (ws / "uv.lock").write_text("lock")
    (ws / "notebook.ipynb").write_text("{}")
    manifest = WorkspaceManifest.default_manifest("ws")
    manifest.sciqlop_version = "0.13.0"
    manifest.save(ws / "workspace.sciqlop")
    return ws


def _reset(ws, versions=("0.14.2", "0.14.1")):
    workspace_reset.reset_environment(ws, latest_versions=lambda: list(versions))


def test_environment_goes_and_user_files_stay(workspace):
    _reset(workspace)
    assert not (workspace / ".venv").exists()
    assert not (workspace / "uv.lock").exists()
    assert (workspace / "notebook.ipynb").read_text() == "{}"
    assert not [p for p in workspace.iterdir() if workspace_reset.is_reset_leftover(p.name)]


def test_pins_the_newest_release(workspace):
    _reset(workspace)
    assert WorkspaceManifest.load(workspace / "workspace.sciqlop").sciqlop_version == "0.14.2"


@pytest.mark.parametrize("pin", [MAIN_PIN, "0.15.0.dev3"])
def test_a_workspace_following_main_stays_on_main(workspace, pin):
    manifest = WorkspaceManifest.load(workspace / "workspace.sciqlop")
    manifest.sciqlop_version = pin
    manifest.save(workspace / "workspace.sciqlop")
    _reset(workspace)
    assert WorkspaceManifest.load(workspace / "workspace.sciqlop").sciqlop_version == pin


def test_offline_keeps_the_pin(workspace):
    _reset(workspace, versions=())
    assert WorkspaceManifest.load(workspace / "workspace.sciqlop").sciqlop_version == "0.13.0"


def test_never_downgrades(workspace):
    _reset(workspace, versions=("0.12.0",))
    assert WorkspaceManifest.load(workspace / "workspace.sciqlop").sciqlop_version == "0.13.0"


def test_undeletable_files_are_left_aside_and_retried_later(workspace, monkeypatch):
    real_rmtree = shutil.rmtree

    def stubborn_rmtree(path, onexc=None, **kw):
        onexc(Path.unlink, str(Path(path) / "lib" / "pkg.py"), PermissionError("locked by antivirus"))

    monkeypatch.setattr(workspace_reset.shutil, "rmtree", stubborn_rmtree)
    _reset(workspace)
    leftovers = [p.name for p in workspace.iterdir() if workspace_reset.is_reset_leftover(p.name)]
    assert not (workspace / ".venv").exists()          # the next sync builds a fresh one
    assert any(name.startswith(".venv.reset-") for name in leftovers)

    monkeypatch.setattr(workspace_reset.shutil, "rmtree", real_rmtree)
    workspace_reset.remove_reset_leftovers(workspace)  # what every later start does
    assert not [p for p in workspace.iterdir() if workspace_reset.is_reset_leftover(p.name)]


def test_several_resets_get_distinct_names(workspace, monkeypatch):
    monkeypatch.setattr(workspace_reset.shutil, "rmtree", lambda *a, **k: None)
    monkeypatch.setattr(workspace_reset, "_stamp", lambda: "20261004-070000")
    for _ in range(3):
        (workspace / ".venv").mkdir(exist_ok=True)
        _reset(workspace)
    names = sorted(p.name for p in workspace.iterdir() if p.name.startswith(".venv.reset-"))
    assert names == [".venv.reset-20261004-070000", ".venv.reset-20261004-070000-2",
                     ".venv.reset-20261004-070000-3"]


def test_a_venv_that_cannot_be_renamed_is_deleted_in_place(workspace, monkeypatch):
    def refuse(src, dst):
        raise PermissionError("in use")
    monkeypatch.setattr(workspace_reset, "_rename", refuse)
    _reset(workspace)
    assert not (workspace / ".venv").exists()


def test_leftovers_stay_out_of_archives_and_copies():
    assert is_excluded(Path(".venv.reset-20261004-070000"))
    assert is_excluded(Path(".venv.reset-20261004-070000-2/lib/x.py"))
    assert is_excluded(Path("uv.lock.reset-20261004-070000"))
    assert not is_excluded(Path("uv.lock"))


def test_by_default_pins_the_newest_release_this_installer_runs(workspace, monkeypatch):
    """A release needing a newer installer would leave the workspace unable to start."""
    runnable = {"0.15.0": False, "0.14.2": None, "0.14.1": True}
    asked = []
    monkeypatch.setattr(workspace_reset, "fetch_available_versions", lambda: list(runnable))
    monkeypatch.setattr(workspace_reset, "running_sciqlop_version", lambda: "0.14.1")
    monkeypatch.setattr(workspace_reset, "runs_here",
                        lambda version, launcher: asked.append(launcher) or runnable[version])
    workspace_reset.reset_environment(workspace)
    assert WorkspaceManifest.load(workspace / "workspace.sciqlop").sciqlop_version == "0.14.1"
    assert set(asked) == {"0.14.1"}
