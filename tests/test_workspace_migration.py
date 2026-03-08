"""Tests for workspace migration from old JSON format to .sciqlop TOML."""

import json

from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest
from SciQLop.components.workspaces.backend.workspace_migration import migrate_workspace


def test_migrate_old_workspace(tmp_path):
    """Converts workspace.json to workspace.sciqlop."""
    old_spec = {
        "name": "Old Study",
        "description": "Legacy workspace",
        "dependencies": ["matplotlib", "scipy>=1.10"],
        "python_path": ["/some/old/path"],
        "notebooks": ["nb1.ipynb"],
        "last_used": "2025-01-01",
        "last_modified": "2025-01-01",
        "image": "",
        "default_workspace": False,
    }
    (tmp_path / "workspace.json").write_text(json.dumps(old_spec))
    deps_dir = tmp_path / "dependencies"
    deps_dir.mkdir()

    migrated = migrate_workspace(tmp_path)

    assert migrated is True
    assert (tmp_path / "workspace.sciqlop").exists()
    m = WorkspaceManifest.load(tmp_path / "workspace.sciqlop")
    assert m.name == "Old Study"
    assert m.description == "Legacy workspace"
    assert "matplotlib" in m.requires
    assert "scipy>=1.10" in m.requires
    assert (tmp_path / "workspace.json.bak").exists()
    assert not deps_dir.exists()


def test_skip_already_migrated(tmp_path):
    """Skip migration when workspace.sciqlop already exists."""
    WorkspaceManifest(name="Already New").save(tmp_path / "workspace.sciqlop")
    migrated = migrate_workspace(tmp_path)
    assert migrated is False


def test_skip_no_old_format(tmp_path):
    """Skip migration when no workspace.json exists."""
    migrated = migrate_workspace(tmp_path)
    assert migrated is False
