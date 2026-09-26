"""The SciQLop-version badge on each welcome-page workspace card."""
import json

import pytest

from SciQLop.components.workspaces.backend.workspace_project import core_version_badge


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
    assert "same as SciQLop" in badge["tooltip"]


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
