"""Tests for WelcomeBackend's SciQLop-core-version slots and signals."""

import json
from unittest.mock import patch

import pytest
from PySide6.QtCore import QObject

from SciQLop.components.welcome.backend import WelcomeBackend, _workspace_to_dict
from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest

WORKSPACE_PROJECT_MODULE = "SciQLop.components.workspaces.backend.workspace_project"
WORKSPACE_SETUP_MODULE = "SciQLop.components.workspaces.backend.workspace_setup"


def _make_backend():
    """A WelcomeBackend built without running its heavy __init__.

    WelcomeBackend.__init__ wires QFileSystemWatcher against the real
    workspaces/templates directories and touches sciqlop_app() -- none of
    which the two new slots under test need. Mirrors the same
    __new__-then-init-the-base-class trick tests/test_workspace_add_packages.py
    uses for Workspace.
    """
    backend = WelcomeBackend.__new__(WelcomeBackend)
    QObject.__init__(backend)
    return backend


def _make_manifest(tmp_path, **kwargs):
    manifest = WorkspaceManifest(name="T", **kwargs)
    manifest.save(tmp_path / "workspace.sciqlop")
    return manifest


class TestWorkspaceToDictExposesCoreVersion:
    def test_includes_sciqlop_version(self, tmp_path):
        manifest = _make_manifest(tmp_path, sciqlop_version="0.13.0")
        assert _workspace_to_dict(manifest)["sciqlop_version"] == "0.13.0"

    def test_empty_when_tracking_main(self, tmp_path):
        manifest = _make_manifest(tmp_path)
        assert _workspace_to_dict(manifest)["sciqlop_version"] == ""


class TestFetchAvailableCoreVersionsSlot:
    def test_emits_versions_and_echoes_directory(self, qtbot, tmp_path):
        backend = _make_backend()
        with patch(f"{WORKSPACE_PROJECT_MODULE}.fetch_available_versions", return_value=["0.13.0", "0.12.0"]):
            with qtbot.waitSignal(backend.core_versions_ready, timeout=2000) as blocker:
                backend.fetch_available_core_versions(str(tmp_path))
        payload = json.loads(blocker.args[0])
        assert payload == {"ok": True, "dir": str(tmp_path), "versions": ["0.13.0", "0.12.0"]}

    def test_reports_not_ok_on_empty_list(self, qtbot, tmp_path):
        backend = _make_backend()
        with patch(f"{WORKSPACE_PROJECT_MODULE}.fetch_available_versions", return_value=[]):
            with qtbot.waitSignal(backend.core_versions_ready, timeout=2000) as blocker:
                backend.fetch_available_core_versions(str(tmp_path))
        payload = json.loads(blocker.args[0])
        assert payload["ok"] is False

    def test_unexpected_exception_still_emits_a_signal(self, qtbot, tmp_path):
        backend = _make_backend()
        with patch(f"{WORKSPACE_PROJECT_MODULE}.fetch_available_versions", side_effect=RuntimeError("boom")):
            with qtbot.waitSignal(backend.core_versions_ready, timeout=2000) as blocker:
                backend.fetch_available_core_versions(str(tmp_path))
        payload = json.loads(blocker.args[0])
        assert payload["ok"] is False


class TestApplyCoreVersionSlot:
    def test_success_emits_ok_with_version_and_dir(self, qtbot, tmp_path):
        backend = _make_backend()
        with (
            patch(f"{WORKSPACE_PROJECT_MODULE}.fetch_available_versions", return_value=["0.13.0"]),
            patch(f"{WORKSPACE_PROJECT_MODULE}.validate_core_version", return_value=True),
            patch(f"{WORKSPACE_SETUP_MODULE}.apply_core_version", return_value=tmp_path / "python"),
        ):
            with qtbot.waitSignal(backend.core_update_finished, timeout=2000) as blocker:
                backend.apply_core_version(str(tmp_path), "0.13.0")
        payload = json.loads(blocker.args[0])
        assert payload["ok"] is True
        assert payload["dir"] == str(tmp_path)
        assert payload["version"] == "0.13.0"

    def test_invalid_version_never_calls_apply_and_reports_error(self, qtbot, tmp_path):
        backend = _make_backend()
        with (
            patch(f"{WORKSPACE_PROJECT_MODULE}.fetch_available_versions", return_value=["0.13.0"]),
            patch(f"{WORKSPACE_PROJECT_MODULE}.validate_core_version", return_value=False),
            patch(f"{WORKSPACE_SETUP_MODULE}.apply_core_version") as mock_apply,
        ):
            with qtbot.waitSignal(backend.core_update_finished, timeout=2000) as blocker:
                backend.apply_core_version(str(tmp_path), "'; rm -rf /")
            mock_apply.assert_not_called()
        payload = json.loads(blocker.args[0])
        assert payload["ok"] is False

    def test_sync_failure_reports_error_detail(self, qtbot, tmp_path):
        backend = _make_backend()
        exc = RuntimeError("uv sync failed")
        with (
            patch(f"{WORKSPACE_PROJECT_MODULE}.fetch_available_versions", return_value=["0.13.0"]),
            patch(f"{WORKSPACE_PROJECT_MODULE}.validate_core_version", return_value=True),
            patch(f"{WORKSPACE_SETUP_MODULE}.apply_core_version", side_effect=exc),
        ):
            with qtbot.waitSignal(backend.core_update_finished, timeout=2000) as blocker:
                backend.apply_core_version(str(tmp_path), "0.13.0")
        payload = json.loads(blocker.args[0])
        assert payload["ok"] is False
        assert "uv sync failed" in payload["error"]

    def test_active_workspace_flag_reflects_env_var(self, qtbot, tmp_path, monkeypatch):
        monkeypatch.setenv("SCIQLOP_WORKSPACE_DIR", str(tmp_path))
        backend = _make_backend()
        with (
            patch(f"{WORKSPACE_PROJECT_MODULE}.fetch_available_versions", return_value=["0.13.0"]),
            patch(f"{WORKSPACE_PROJECT_MODULE}.validate_core_version", return_value=True),
            patch(f"{WORKSPACE_SETUP_MODULE}.apply_core_version", return_value=tmp_path / "python"),
        ):
            with qtbot.waitSignal(backend.core_update_finished, timeout=2000) as blocker:
                backend.apply_core_version(str(tmp_path), "0.13.0")
        payload = json.loads(blocker.args[0])
        assert payload["is_active_workspace"] is True
