"""Picking "main (development)" for a workspace must install from git main.

The picker sent an empty version, and an empty pin falls back to the running
launcher's version: from an installed SciQLop 0.13.0, choosing main quietly
reinstalled 0.13.0. "main" is now an explicit pin; empty keeps meaning "follow
the launcher" so workspaces created before pinning existed do not jump to main.
"""
import tempfile
from pathlib import Path

import pytest

from SciQLop.components.workspaces.backend import workspace_project as wp
from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest

GIT_MAIN = "sciqlop[all] @ git+https://github.com/SciQLop/SciQLop.git@main"


@pytest.fixture
def released_launcher(monkeypatch):
    monkeypatch.setattr(wp, "running_sciqlop_version", lambda: "0.13.0")


def test_main_pin_installs_git_main_from_a_released_launcher(released_launcher):
    assert wp.sciqlop_requirement("main") == GIT_MAIN


def test_main_pin_counts_as_a_dev_build_so_uv_refreshes_it():
    assert wp.is_dev_build_version("main") is True


def test_main_is_a_valid_core_version():
    assert wp.validate_core_version("main", ["0.13.0"]) is True


def test_an_unpinned_workspace_still_follows_a_released_launcher(released_launcher):
    assert wp.sciqlop_requirement("") == "sciqlop[all]==0.13.0"


def test_main_pin_survives_a_manifest_round_trip(tmp_path):
    path = tmp_path / "workspace.sciqlop"
    WorkspaceManifest(name="Dev", sciqlop_version="main").save(path)
    assert WorkspaceManifest.load_or_repair(path).sciqlop_version == "main"
