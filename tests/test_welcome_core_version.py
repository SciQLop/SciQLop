"""Tests for WelcomeBackend's SciQLop-core-version slots and signals."""

import json
from unittest.mock import patch

import pytest
from PySide6.QtCore import QObject

from SciQLop.components.welcome.backend import WelcomeBackend, _workspace_to_dict
from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest

WORKSPACE_PROJECT_MODULE = "SciQLop.components.workspaces.backend.workspace_project"
WORKSPACE_SETUP_MODULE = "SciQLop.components.workspaces.backend.workspace_setup"
LAUNCHER_COMPAT_MODULE = "SciQLop.components.workspaces.backend.launcher_compat"


@pytest.fixture(autouse=True)
def _no_release_needs_fetch():
    """Whether a release runs under this installer is fetched from GitHub: unknown here."""
    with patch(f"{LAUNCHER_COMPAT_MODULE}.fetch_release_needs", return_value=None):
        yield


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
            patch(f"{WORKSPACE_SETUP_MODULE}.apply_core_version", return_value=tmp_path / "python") as mock_apply,
            patch(f"{WORKSPACE_SETUP_MODULE}.stage_core_version") as mock_pin,
        ):
            with qtbot.waitSignal(backend.core_update_finished, timeout=2000) as blocker:
                backend.apply_core_version(str(tmp_path), "0.13.0")
        payload = json.loads(blocker.args[0])
        assert payload["ok"] is True
        assert payload["dir"] == str(tmp_path)
        assert payload["version"] == "0.13.0"
        assert payload["is_active_workspace"] is False
        mock_apply.assert_called_once_with(str(tmp_path), "0.13.0")
        mock_pin.assert_not_called()

    def test_success_includes_dropped_packages_when_notice_file_exists(self, qtbot, tmp_path):
        """The notice file's raw dep strings (here a wheel URL) must be
        rendered as package names, not passed through verbatim."""
        from SciQLop.components.workspaces.backend.workspace_setup import DROPPED_DEPS_FILENAME

        backend = _make_backend()
        (tmp_path / DROPPED_DEPS_FILENAME).write_text(
            json.dumps({
                "dropped": ["https://example.com/wheels/radio_plugin-1.2.0-py3-none-any.whl"],
                "error": "boom",
            })
        )
        with (
            patch(f"{WORKSPACE_PROJECT_MODULE}.fetch_available_versions", return_value=["0.13.0"]),
            patch(f"{WORKSPACE_PROJECT_MODULE}.validate_core_version", return_value=True),
            patch(f"{WORKSPACE_SETUP_MODULE}.apply_core_version", return_value=tmp_path / "python"),
            patch(f"{WORKSPACE_SETUP_MODULE}.stage_core_version"),
        ):
            with qtbot.waitSignal(backend.core_update_finished, timeout=2000) as blocker:
                backend.apply_core_version(str(tmp_path), "0.13.0")
        payload = json.loads(blocker.args[0])
        assert payload["dropped"] == ["radio-plugin"]

    def test_success_with_no_notice_file_reports_empty_dropped_list(self, qtbot, tmp_path):
        backend = _make_backend()
        with (
            patch(f"{WORKSPACE_PROJECT_MODULE}.fetch_available_versions", return_value=["0.13.0"]),
            patch(f"{WORKSPACE_PROJECT_MODULE}.validate_core_version", return_value=True),
            patch(f"{WORKSPACE_SETUP_MODULE}.apply_core_version", return_value=tmp_path / "python"),
        ):
            with qtbot.waitSignal(backend.core_update_finished, timeout=2000) as blocker:
                backend.apply_core_version(str(tmp_path), "0.13.0")
        payload = json.loads(blocker.args[0])
        assert payload["dropped"] == []

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

    def test_active_workspace_is_staged_not_applied(self, qtbot, tmp_path, monkeypatch):
        """The running workspace gets the new version built in its other venv
        slot (venv_slots); applying in place would rewrite the running venv."""
        monkeypatch.setenv("SCIQLOP_WORKSPACE_DIR", str(tmp_path))
        backend = _make_backend()
        with (
            patch(f"{WORKSPACE_PROJECT_MODULE}.fetch_available_versions", return_value=["0.13.0"]),
            patch(f"{WORKSPACE_PROJECT_MODULE}.validate_core_version", return_value=True),
            patch(f"{WORKSPACE_SETUP_MODULE}.stage_core_version") as mock_stage,
            patch(f"{WORKSPACE_SETUP_MODULE}.apply_core_version") as mock_apply,
        ):
            with qtbot.waitSignal(backend.core_update_finished, timeout=2000) as blocker:
                backend.apply_core_version(str(tmp_path), "0.13.0")
        payload = json.loads(blocker.args[0])
        assert payload["is_active_workspace"] is True
        assert payload["ok"] is True
        mock_stage.assert_called_once_with(str(tmp_path), "0.13.0")
        mock_apply.assert_not_called()

    def test_active_workspace_reports_what_staging_left_out(self, qtbot, tmp_path, monkeypatch):
        from SciQLop.components.workspaces.backend.workspace_setup import DROPPED_DEPS_FILENAME

        monkeypatch.setenv("SCIQLOP_WORKSPACE_DIR", str(tmp_path))
        backend = _make_backend()

        def stage(workspace_dir, version):
            (tmp_path / DROPPED_DEPS_FILENAME).write_text(
                json.dumps({"dropped": ["radio-plugin"], "error": "boom"}))

        with (
            patch(f"{WORKSPACE_PROJECT_MODULE}.fetch_available_versions", return_value=["0.13.0"]),
            patch(f"{WORKSPACE_PROJECT_MODULE}.validate_core_version", return_value=True),
            patch(f"{WORKSPACE_SETUP_MODULE}.stage_core_version", side_effect=stage),
        ):
            with qtbot.waitSignal(backend.core_update_finished, timeout=2000) as blocker:
                backend.apply_core_version(str(tmp_path), "0.13.0")
        payload = json.loads(blocker.args[0])
        assert payload["dropped"] == ["radio-plugin"]


class TestApplyCoreVersionNeedsAnInstallerThatRunsIt:
    def test_a_version_needing_a_newer_installer_is_refused(self, qtbot, tmp_path):
        backend = _make_backend()
        with (
            patch(f"{WORKSPACE_PROJECT_MODULE}.fetch_available_versions", return_value=["0.15.0"]),
            patch(f"{LAUNCHER_COMPAT_MODULE}.runs_here", return_value=False),
            patch(f"{WORKSPACE_SETUP_MODULE}.stage_core_version") as mock_stage,
            patch(f"{WORKSPACE_SETUP_MODULE}.apply_core_version") as mock_apply,
        ):
            with qtbot.waitSignal(backend.core_update_finished, timeout=2000) as blocker:
                backend.apply_core_version(str(tmp_path), "0.15.0")
        payload = json.loads(blocker.args[0])
        assert payload["ok"] is False
        assert "installer" in payload["error"]
        mock_stage.assert_not_called()
        mock_apply.assert_not_called()

    def test_unknown_compatibility_does_not_block_the_picker(self, qtbot, tmp_path):
        backend = _make_backend()
        with (
            patch(f"{WORKSPACE_PROJECT_MODULE}.fetch_available_versions", return_value=["0.15.0"]),
            patch(f"{LAUNCHER_COMPAT_MODULE}.runs_here", return_value=None),
            patch(f"{WORKSPACE_SETUP_MODULE}.apply_core_version"),
        ):
            with qtbot.waitSignal(backend.core_update_finished, timeout=2000) as blocker:
                backend.apply_core_version(str(tmp_path), "0.15.0")
        assert json.loads(blocker.args[0])["ok"] is True


class TestReleaseOffer:
    """The welcome banner: update the workspace in place, or get a new installer."""

    @staticmethod
    def _offer(runs, latest="0.15.0", running="0.14.2", workspace_dir="/ws", follow_latest=True, launcher="0.14.2"):
        from SciQLop.components.welcome.backend import release_offer
        with (
            patch(f"{LAUNCHER_COMPAT_MODULE}.runs_here", return_value=runs),
            patch(f"{LAUNCHER_COMPAT_MODULE}.follows_latest_release", return_value=follow_latest),
            patch(f"{LAUNCHER_COMPAT_MODULE}.launcher_version", return_value=launcher),
        ):
            return release_offer(latest, running, workspace_dir)

    def test_a_release_this_installer_runs_is_installed_in_the_workspace(self):
        offer = self._offer(True)
        assert offer["is_update"] is True
        assert offer["route"] == "workspace"
        assert offer["workspace_dir"] == "/ws"

    @pytest.mark.parametrize("runs", [False, None])
    def test_otherwise_a_new_installer_is_proposed(self, runs):
        offer = self._offer(runs)
        assert offer["route"] == "installer"
        assert offer["url"].startswith("https://github.com/SciQLop/SciQLop/releases")

    def test_up_to_date(self):
        assert self._offer(True, latest="0.14.2")["is_update"] is False

    def test_a_workspace_on_main_is_not_moved_to_a_release(self):
        assert self._offer(True, running="0.15.0.dev1", latest="0.15.0")["route"] == "installer"

    def test_without_a_workspace_there_is_nothing_to_update_in_place(self):
        assert self._offer(True, workspace_dir="")["route"] == "installer"


class TestReleaseOfferStickingToTheInstaller:
    """The "Installer's version" setting: updates come with installers."""

    def _offer(self, **kwargs):
        return TestReleaseOffer._offer(True, follow_latest=False, **kwargs)

    def test_a_release_newer_than_the_installer_needs_a_new_installer(self):
        offer = self._offer(latest="0.15.0", running="0.14.2", launcher="0.14.2")
        assert offer["is_update"] is True and offer["route"] == "installer"

    def test_a_workspace_behind_its_installer_moves_to_the_installer_version(self):
        offer = self._offer(latest="0.15.0", running="0.14.2", launcher="0.15.0")
        assert offer["route"] == "workspace" and offer["version"] == "0.15.0"

    def test_an_installer_behind_the_latest_release_is_proposed_first(self):
        offer = self._offer(latest="0.16.0", running="0.14.2", launcher="0.15.0")
        assert offer["route"] == "installer" and offer["version"] == "0.16.0"

    def test_up_to_date_with_its_installer(self):
        assert self._offer(latest="0.15.0", running="0.15.0", launcher="0.15.0")["is_update"] is False
