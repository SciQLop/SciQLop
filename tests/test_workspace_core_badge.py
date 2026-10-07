"""The SciQLop-version badge on each welcome-page workspace card."""
import json

import pytest
from unittest.mock import patch as _patch


@pytest.fixture(autouse=True)
def _no_release_needs_fetch():
    with _patch("SciQLop.components.workspaces.backend.launcher_compat.fetch_release_needs", return_value=None):
        yield

from SciQLop.components.workspaces.backend.workspace_project import (
    core_version_badge, installed_sciqlop_version,
)


def test_a_pinned_release_shows_its_version():
    badge = core_version_badge("0.13.0", running="0.13.0", latest="0.13.0")
    assert badge["label"] == "0.13.0" and badge["outdated"] is False


def test_a_pin_older_than_the_latest_release_is_outdated():
    badge = core_version_badge("0.12.2", running="0.13.0", latest="0.13.1")
    assert badge["outdated"] is True
    assert "0.13.1" in badge["tooltip"]


def test_main_is_never_outdated():
    badge = core_version_badge("main", running="0.13.0", latest="0.14.0")
    assert badge["label"] == "main" and badge["outdated"] is False


def test_an_unpinned_workspace_follows_the_running_sciqlop():
    badge = core_version_badge("", running="0.13.0", latest="0.13.1")
    assert badge["label"] == "0.13.0"
    assert badge["outdated"] is True
    assert "not pinned" in badge["tooltip"]


def test_an_unpinned_workspace_on_a_dev_launcher_follows_main():
    badge = core_version_badge("", running="0.13.1.dev0", latest="0.13.0")
    assert badge["label"] == "main" and badge["outdated"] is False


def test_nothing_is_outdated_until_the_latest_release_is_known():
    assert core_version_badge("0.10.0", running="0.13.0", latest=None)["outdated"] is False


def test_a_dev_pin_is_shown_as_main():
    assert core_version_badge("0.13.1.dev0", running="0.13.0", latest="0.13.1")["label"] == "main"


@pytest.mark.parametrize("pin", ["garbage", "1.x"])
def test_an_unparsable_pin_is_shown_but_not_marked_outdated(pin):
    badge = core_version_badge(pin, running="0.13.0", latest="0.13.1")
    assert badge["label"] == pin and badge["outdated"] is False


def test_the_welcome_payload_carries_each_workspace_badge(tmp_path, monkeypatch):
    from SciQLop.components.welcome import backend
    from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
    monkeypatch.setattr(backend, "running_sciqlop_version", lambda: "0.13.0")
    ws = WorkspaceManifest(name="W", sciqlop_version="main")
    ws._directory = str(tmp_path)
    d = backend._workspace_to_dict(ws)
    assert d["core_badge"]["label"] == "main"
    json.dumps(d)


def test_badges_are_resent_with_the_latest_release_fetched_once(qtbot, tmp_path, monkeypatch):
    from unittest.mock import patch
    from PySide6.QtCore import QObject
    from SciQLop.components.welcome import backend as wb
    from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest

    old = WorkspaceManifest(name="Old", sciqlop_version="0.12.0")
    old._directory = str(tmp_path / "old")
    monkeypatch.setattr(wb, "workspaces_manager_instance",
                        lambda: type("M", (), {"list_workspaces": lambda self: [old]})())
    monkeypatch.setattr(wb, "running_sciqlop_version", lambda: "0.13.0")
    backend = wb.WelcomeBackend.__new__(wb.WelcomeBackend)
    QObject.__init__(backend)
    backend._latest_core_release = None

    with patch("SciQLop.components.workspaces.backend.workspace_project.fetch_available_versions",
               return_value=["0.13.1", "0.13.0"]) as fetch:
        for _ in range(2):
            with qtbot.waitSignal(backend.core_badges_ready, timeout=2000) as blocker:
                backend.fetch_core_version_badges()
    badge = json.loads(blocker.args[0])[old.directory]
    assert badge["outdated"] is True and badge["label"] == "0.12.0"
    assert fetch.call_count == 1


def test_outdated_means_behind_the_newest_release_this_installer_runs(qtbot, tmp_path, monkeypatch):
    """A release needing a new installer is not offered by the workspace picker."""
    from unittest.mock import patch
    from PySide6.QtCore import QObject
    from SciQLop.components.welcome import backend as wb
    from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest

    current = WorkspaceManifest(name="Current", sciqlop_version="0.13.1")
    current._directory = str(tmp_path / "current")
    monkeypatch.setattr(wb, "workspaces_manager_instance",
                        lambda: type("M", (), {"list_workspaces": lambda self: [current]})())
    backend = wb.WelcomeBackend.__new__(wb.WelcomeBackend)
    QObject.__init__(backend)
    backend._latest_core_release = None

    with (
        patch("SciQLop.components.workspaces.backend.workspace_project.fetch_available_versions",
              return_value=["0.14.0", "0.13.1"]),
        patch("SciQLop.components.workspaces.backend.launcher_compat.runs_here",
              side_effect=lambda v: v != "0.14.0"),
    ):
        with qtbot.waitSignal(backend.core_badges_ready, timeout=2000) as blocker:
            backend.fetch_core_version_badges()
    assert json.loads(blocker.args[0])[current.directory]["outdated"] is False


def _fake_install(workspace_dir, version, site="lib/python3.14/site-packages"):
    dist_info = workspace_dir / ".venv" / site / f"sciqlop-{version}.dist-info"
    dist_info.mkdir(parents=True)
    (dist_info / "METADATA").write_text(f"Metadata-Version: 2.1\nName: SciQLop\nVersion: {version}\n")


def test_installed_version_is_read_from_the_workspace_venv(tmp_path):
    _fake_install(tmp_path, "0.13.0")
    assert installed_sciqlop_version(tmp_path) == "0.13.0"


def test_installed_version_reads_the_windows_venv_layout(tmp_path):
    _fake_install(tmp_path, "0.13.0", site="Lib/site-packages")
    assert installed_sciqlop_version(tmp_path) == "0.13.0"


def test_installed_version_is_empty_without_a_venv(tmp_path):
    assert installed_sciqlop_version(tmp_path) == ""


def test_an_unpinned_card_shows_what_the_workspace_has_installed(tmp_path, monkeypatch):
    """An unpinned workspace follows the launcher, not the SciQLop showing the page:
    a main build listing a workspace its 0.13.0 launcher installed must say 0.13.0."""
    from SciQLop.components.welcome import backend
    from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
    monkeypatch.setattr(backend, "running_sciqlop_version", lambda: "0.13.1.dev0")
    _fake_install(tmp_path, "0.13.0")
    ws = WorkspaceManifest(name="W")
    ws._directory = str(tmp_path)
    assert backend._workspace_to_dict(ws)["core_badge"]["label"] == "0.13.0"


def test_an_unpinned_card_without_a_venv_falls_back_to_the_running_version(tmp_path, monkeypatch):
    from SciQLop.components.welcome import backend
    from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
    monkeypatch.setattr(backend, "running_sciqlop_version", lambda: "0.13.0")
    ws = WorkspaceManifest(name="W")
    ws._directory = str(tmp_path)
    assert backend._workspace_to_dict(ws)["core_badge"]["label"] == "0.13.0"


def test_a_failed_release_fetch_is_retried_on_the_next_refresh(qtbot, tmp_path, monkeypatch):
    """Offline at startup must not hide the "outdated" badges for the session."""
    from unittest.mock import patch
    from PySide6.QtCore import QObject
    from SciQLop.components.welcome import backend as wb
    from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest

    old = WorkspaceManifest(name="Old", sciqlop_version="0.12.0")
    old._directory = str(tmp_path / "old")
    monkeypatch.setattr(wb, "workspaces_manager_instance",
                        lambda: type("M", (), {"list_workspaces": lambda self: [old]})())
    backend = wb.WelcomeBackend.__new__(wb.WelcomeBackend)
    QObject.__init__(backend)
    backend._latest_core_release = None

    with patch("SciQLop.components.workspaces.backend.workspace_project.fetch_available_versions",
               side_effect=[[], ["0.13.1"]]):
        for _ in range(2):
            with qtbot.waitSignal(backend.core_badges_ready, timeout=2000) as blocker:
                backend.fetch_core_version_badges()
    assert json.loads(blocker.args[0])[old.directory]["outdated"] is True


def test_example_dependencies_install_like_every_other_live_install(qtbot, tmp_path, monkeypatch):
    """Adding an example's dependencies to the running workspace used a bare
    `uv pip install`: unguarded (could move the running Qt stack) and aimed at
    whatever .venv the current directory held. It must use guarded_install."""
    from types import SimpleNamespace
    from PySide6.QtCore import QObject
    from SciQLop.components.welcome import backend as wb
    from SciQLop.components.workspaces.backend import live_install
    from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest

    WorkspaceManifest(name="W").save(tmp_path / "workspace.sciqlop")
    monkeypatch.setenv("SCIQLOP_WORKSPACE_DIR", str(tmp_path))
    installed = []
    monkeypatch.setattr(live_install, "guarded_install",
                        lambda specs: installed.append(specs) or SimpleNamespace(returncode=0, stderr=""))
    backend = wb.WelcomeBackend.__new__(wb.WelcomeBackend)
    QObject.__init__(backend)

    with qtbot.waitSignal(backend.dependency_install_finished, timeout=5000) as blocker:
        backend.add_dependencies_to_workspace(str(tmp_path), json.dumps(["spok"]))

    assert installed == [["spok"]]
    assert json.loads(blocker.args[0])["ok"] is True
    assert WorkspaceManifest.load(tmp_path / "workspace.sciqlop").requires == ["spok"]
