import os
import tempfile
from pathlib import Path

import pytest

from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest


class TestDefaultManifest:
    def test_default_has_name(self):
        m = WorkspaceManifest.default_manifest("My Project")
        assert m.name == "My Project"

    def test_default_has_empty_description(self):
        m = WorkspaceManifest.default_manifest("X")
        assert m.description == ""

    def test_default_has_empty_lists(self):
        m = WorkspaceManifest.default_manifest("X")
        assert m.plugins_add == []
        assert m.plugins_remove == []
        assert m.requires == []


class TestRoundtrip:
    def test_save_and_load(self, tmp_path):
        original = WorkspaceManifest(
            name="Magnetosphere Study",
            description="Studying reconnection events in 2024",
            plugins_add=["some_extra_plugin"],
            plugins_remove=["experimental_collaboration"],
            requires=["matplotlib>=3.8", "scipy", "hapiclient"],
        )
        path = tmp_path / ".sciqlop"
        original.save(path)
        loaded = WorkspaceManifest.load(path)
        assert loaded.name == original.name
        assert loaded.description == original.description
        assert loaded.plugins_add == original.plugins_add
        assert loaded.plugins_remove == original.plugins_remove
        assert loaded.requires == original.requires

    def test_saved_file_is_valid_toml(self, tmp_path):
        import tomllib

        m = WorkspaceManifest.default_manifest("Test")
        path = tmp_path / ".sciqlop"
        m.save(path)
        with open(path, "rb") as f:
            data = tomllib.load(f)
        assert data["workspace"]["name"] == "Test"


class TestLoadMinimal:
    def test_load_only_name(self, tmp_path):
        path = tmp_path / ".sciqlop"
        path.write_text('[workspace]\nname = "Minimal"\n')
        m = WorkspaceManifest.load(path)
        assert m.name == "Minimal"
        assert m.description == ""
        assert m.plugins_add == []
        assert m.plugins_remove == []
        assert m.requires == []


class TestImageAndDefault:
    def test_roundtrip_with_image_and_default(self, tmp_path):
        m = WorkspaceManifest(name="Study", image="image.png", default=True)
        m.save(tmp_path / "workspace.sciqlop")
        loaded = WorkspaceManifest.load(tmp_path / "workspace.sciqlop")
        assert loaded.name == "Study"
        assert loaded.image == "image.png"
        assert loaded.default is True

    def test_load_without_image_defaults_empty(self, tmp_path):
        WorkspaceManifest(name="Bare").save(tmp_path / "workspace.sciqlop")
        loaded = WorkspaceManifest.load(tmp_path / "workspace.sciqlop")
        assert loaded.image == ""
        assert loaded.default is False

    def test_directory_set_on_load(self, tmp_path):
        WorkspaceManifest(name="X").save(tmp_path / "workspace.sciqlop")
        loaded = WorkspaceManifest.load(tmp_path / "workspace.sciqlop")
        assert loaded.directory == str(tmp_path)

    def test_directory_set_on_save(self, tmp_path):
        m = WorkspaceManifest(name="X")
        m.save(tmp_path / "workspace.sciqlop")
        assert m.directory == str(tmp_path)


class TestTimestamps:
    def test_last_modified_from_manifest_mtime(self, tmp_path):
        WorkspaceManifest(name="X").save(tmp_path / "workspace.sciqlop")
        assert WorkspaceManifest.last_modified(tmp_path) != ""

    def test_last_used_empty_before_touch(self, tmp_path):
        WorkspaceManifest(name="X").save(tmp_path / "workspace.sciqlop")
        assert WorkspaceManifest.last_used(tmp_path) == ""

    def test_touch_then_read_last_used(self, tmp_path):
        WorkspaceManifest(name="X").save(tmp_path / "workspace.sciqlop")
        WorkspaceManifest.touch_last_used(tmp_path)
        assert WorkspaceManifest.last_used(tmp_path) != ""


class TestLoadAllFields:
    def test_load_full_manifest(self, tmp_path):
        content = """\
[workspace]
name = "Full Project"
description = "All fields populated"

[plugins]
add = ["plugin_a", "plugin_b"]
remove = ["plugin_c"]

[dependencies]
requires = ["numpy>=1.24", "scipy"]
"""
        path = tmp_path / ".sciqlop"
        path.write_text(content)
        m = WorkspaceManifest.load(path)
        assert m.name == "Full Project"
        assert m.description == "All fields populated"
        assert m.plugins_add == ["plugin_a", "plugin_b"]
        assert m.plugins_remove == ["plugin_c"]
        assert m.requires == ["numpy>=1.24", "scipy"]
