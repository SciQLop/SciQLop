"""Every writer of workspace.sciqlop must re-read it before saving.

The running Workspace kept the manifest it loaded at startup and wrote that
copy back on %install or a rename, silently undoing what the welcome page had
saved in between (a pinned SciQLop version, example dependencies, installed
examples). Long operations (a core-version sync) had the same stale window.
"""
import threading
import time
from pathlib import Path
from types import SimpleNamespace

from SciQLop.components.workspaces.backend.workspace_manifest import (
    InstalledExample, WorkspaceManifest, edit_manifest,
)


def _manifest(tmp_path) -> Path:
    path = tmp_path / "workspace.sciqlop"
    WorkspaceManifest(name="W").save(path)
    return path


def _edit_elsewhere(path: Path) -> None:
    other = WorkspaceManifest.load(path)
    other.sciqlop_version = "0.13.0"
    other.requires.append("spok")
    other.examples.append(InstalledExample(name="MMS", source="x", version="1"))
    other.save(path)


def _assert_other_edits_kept(path: Path) -> WorkspaceManifest:
    manifest = WorkspaceManifest.load(path)
    assert manifest.sciqlop_version == "0.13.0"
    assert "spok" in manifest.requires
    assert [e.name for e in manifest.examples] == ["MMS"]
    return manifest


def _workspace(path: Path):
    from SciQLop.components.workspaces.backend.workspace import Workspace
    workspace = Workspace(WorkspaceManifest.load(path))
    workspace._uv_install = lambda specs: SimpleNamespace(returncode=0, stderr="")
    return workspace


def test_install_keeps_what_was_saved_since_startup(qapp, tmp_path):
    path = _manifest(tmp_path)
    workspace = _workspace(path)
    _edit_elsewhere(path)

    workspace.add_packages(["scipy"])

    assert "scipy" in _assert_other_edits_kept(path).requires


def test_renaming_keeps_what_was_saved_since_startup(qapp, tmp_path):
    path = _manifest(tmp_path)
    workspace = _workspace(path)
    _edit_elsewhere(path)

    workspace.name = "Renamed"

    assert _assert_other_edits_kept(path).name == "Renamed"


def test_two_simultaneous_edits_both_land(tmp_path):
    path = _manifest(tmp_path)
    first_is_editing = threading.Event()

    def slow_edit():
        with edit_manifest(path) as manifest:
            first_is_editing.set()
            time.sleep(0.2)
            manifest.requires.append("first")

    thread = threading.Thread(target=slow_edit)
    thread.start()
    first_is_editing.wait()
    with edit_manifest(path) as manifest:
        manifest.requires.append("second")
    thread.join()

    assert sorted(WorkspaceManifest.load(path).requires) == ["first", "second"]


def test_a_core_version_update_keeps_edits_made_during_its_sync(tmp_path, monkeypatch):
    from SciQLop.components.workspaces.backend import workspace_setup
    path = _manifest(tmp_path)

    def sync_while_someone_edits(workspace_dir, manifest, **kwargs):
        with edit_manifest(path) as live:
            live.requires.append("added-during-sync")
        return Path("python")

    monkeypatch.setattr(workspace_setup, "prepare_workspace", sync_while_someone_edits)

    workspace_setup.apply_core_version(tmp_path, "0.14.0")

    manifest = WorkspaceManifest.load(path)
    assert manifest.sciqlop_version == "0.14.0"
    assert manifest.requires == ["added-during-sync"]
