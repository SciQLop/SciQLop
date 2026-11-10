"""The release-candidate channel: workspaces that opt in see pre-releases newer than the latest
release, in the version picker, the update banner and for new workspaces."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from SciQLop.components.workspaces.backend import launcher_compat, settings
from SciQLop.components.workspaces.backend.workspace_project import (
    fetch_available_versions, installable_versions, validate_core_version)

_PYPI = {v: [{"yanked": False}] for v in
         ("0.14.0", "0.14.1", "0.14.1rc1", "0.15.0b1", "0.15.0rc1", "0.15.0rc2", "0.15.1.dev0")}


def _channel(choice):
    return patch.object(settings, "SciQLopWorkspacesSettings", lambda: SimpleNamespace(sciqlop_version=choice))


def test_the_stable_channel_lists_releases_only():
    assert installable_versions(_PYPI, release_candidates=False) == ["0.14.1", "0.14.0"]


def test_the_candidate_channel_adds_pre_releases_newer_than_the_latest_release():
    assert installable_versions(_PYPI, release_candidates=True) == [
        "0.15.0rc2", "0.15.0rc1", "0.15.0b1", "0.14.1", "0.14.0"]


def test_once_the_release_is_out_its_candidates_are_no_longer_listed():
    released = dict(_PYPI, **{"0.15.0": [{"yanked": False}]})
    assert installable_versions(released, release_candidates=True) == ["0.15.0", "0.14.1", "0.14.0"]


def test_a_yanked_candidate_is_not_listed():
    yanked = dict(_PYPI, **{"0.15.0rc2": [{"yanked": True}]})
    assert installable_versions(yanked, release_candidates=True)[0] == "0.15.0rc1"


@pytest.mark.parametrize("choice, candidates", [
    (settings.LATEST_RELEASE, False), (settings.LATEST_RELEASE_CANDIDATE, True), (settings.INSTALLERS_VERSION, False)])
def test_fetch_follows_the_sciqlop_version_setting(choice, candidates):
    resp = MagicMock()
    resp.read.return_value = json.dumps({"releases": _PYPI}).encode()
    resp.__enter__.return_value = resp
    with (patch("urllib.request.urlopen", return_value=resp),
          _channel(choice)):
        assert ("0.15.0rc2" in fetch_available_versions()) is candidates


def test_the_candidate_channel_follows_the_latest_too():
    with _channel(settings.LATEST_RELEASE_CANDIDATE):
        assert launcher_compat.follows_latest_release()
        assert settings.follows_release_candidates()


def test_new_workspaces_on_the_candidate_channel_start_on_the_newest_candidate():
    with (patch.object(launcher_compat, "follows_latest_release", return_value=True),
          patch.object(launcher_compat, "fetch_available_versions",
                       return_value=installable_versions(_PYPI, release_candidates=True)),
          patch.object(launcher_compat, "runs_here", return_value=True)):
        assert launcher_compat.preferred_release("0.14.1") == "0.15.0rc2"


@pytest.mark.parametrize("pin", ["0.15.0rc1", "0.15.0b2", "0.15.0a1", "1.0rc3"])
def test_a_candidate_pin_is_accepted_even_offline(pin):
    assert validate_core_version(pin, [])


@pytest.mark.parametrize("pin", ["0.15.0rc", "0.15.0rc1 ; x", "0.15.0.dev0", "0.15.0rc1@main", "0.15.0-rc1"])
def test_anything_else_shaped_like_a_candidate_is_refused(pin):
    assert not validate_core_version(pin, [])


def test_a_candidate_workspace_is_outdated_once_the_release_is_out():
    from SciQLop.components.workspaces.backend.workspace_project import core_version_badge
    assert core_version_badge("0.15.0rc2", "", "0.15.0")["outdated"]
    assert not core_version_badge("0.15.0rc2", "", "0.14.1")["outdated"]
