"""Duplicate must not switch/restart, must exclude .venv, and (at the
WelcomeBackend layer) must not block the GUI thread with the copy."""

import os
import time
from unittest.mock import patch

from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
from SciQLop.components.workspaces.backend.workspaces_manager import WorkspaceManager


def _make_workspace(tmp_path, name="My WS", default=False):
    ws_dir = tmp_path / "source"
    ws_dir.mkdir()
    manifest = WorkspaceManifest(name=name, default=default)
    manifest.save(ws_dir / "workspace.sciqlop")
    return ws_dir


def _duplicate(tmp_path, source_dir):
    dest_root = tmp_path / "workspaces"
    dest_root.mkdir(exist_ok=True)
    manager = WorkspaceManager.__new__(WorkspaceManager)
    with patch(
        "SciQLop.components.workspaces.backend.workspaces_manager.SciQLopWorkspacesSettings",
        create=True,
    ) as MockSettings:
        MockSettings.return_value.workspaces_dir = str(dest_root)
        manager.duplicate_workspace(str(source_dir))
    copies = [d for d in dest_root.iterdir() if d.is_dir()]
    assert len(copies) == 1, "duplicate must create exactly one new workspace directory"
    return copies[0]


def test_duplicate_does_not_switch_workspace(tmp_path):
    source = _make_workspace(tmp_path)
    with patch("SciQLop.sciqlop_app.switch_workspace") as mock_switch:
        _duplicate(tmp_path, source)
    mock_switch.assert_not_called()


def test_duplicate_names_copy_and_clears_default(tmp_path):
    source = _make_workspace(tmp_path, name="My WS", default=True)
    copy_dir = _duplicate(tmp_path, source)
    manifest = WorkspaceManifest.load(copy_dir / "workspace.sciqlop")
    assert manifest.name == "Copy of My WS"
    assert manifest.default is False


def test_duplicate_excludes_venv(tmp_path):
    source = _make_workspace(tmp_path)
    venv_bin = source / ".venv" / "bin"
    venv_bin.mkdir(parents=True)
    (venv_bin / "python").write_text("fake interpreter")
    copy_dir = _duplicate(tmp_path, source)
    assert not (copy_dir / ".venv").exists()


def test_duplicate_workspace_runs_off_gui_thread_and_emits_when_done(qapp, qtbot, monkeypatch):
    """WelcomeBackend.duplicate_workspace must return immediately and only
    report the new workspace once the (slow) copy has actually finished."""
    import threading

    from SciQLop.components.welcome.backend import WelcomeBackend

    calling_thread = threading.current_thread()
    worker_thread = {}

    class FakeManager:
        def duplicate_workspace(self, directory):
            worker_thread["thread"] = threading.current_thread()
            time.sleep(0.2)

    monkeypatch.setattr(
        "SciQLop.components.welcome.backend.workspaces_manager_instance",
        lambda: FakeManager(),
    )

    backend = WelcomeBackend()
    with qtbot.waitSignal(backend.workspace_list_changed, timeout=2000):
        start = time.monotonic()
        backend.duplicate_workspace("/fake/workspace/dir")
        elapsed = time.monotonic() - start

    assert elapsed < 0.1, "duplicate_workspace must not block the calling (GUI) thread"
    assert worker_thread["thread"] is not calling_thread


def test_failed_duplicate_leaves_no_partial_workspace(tmp_path):
    import pytest
    source = _make_workspace(tmp_path)
    dest_root = tmp_path / "workspaces"
    dest_root.mkdir()
    manager = WorkspaceManager.__new__(WorkspaceManager)
    with patch(
        "SciQLop.components.workspaces.backend.workspaces_manager.SciQLopWorkspacesSettings",
        create=True,
    ) as MockSettings, patch(
        "SciQLop.components.workspaces.backend.workspaces_manager.WorkspaceManifest.load_or_repair",
        side_effect=OSError("disk full"),
    ):
        MockSettings.return_value.workspaces_dir = str(dest_root)
        with pytest.raises(OSError):
            manager.duplicate_workspace(str(source))
    assert list(dest_root.iterdir()) == []
