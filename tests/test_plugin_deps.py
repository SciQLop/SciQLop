import json
import os
import pytest
from pathlib import Path

from SciQLop.core.plugin_deps import collect_plugin_dependencies


@pytest.fixture
def plugin_dir(tmp_path):
    """Create a temporary plugin directory with several plugins."""
    # Plugin A: has python_dependencies
    plugin_a = tmp_path / "plugin_a"
    plugin_a.mkdir()
    (plugin_a / "__init__.py").write_text("")
    (plugin_a / "plugin.json").write_text(json.dumps({
        "name": "Plugin A",
        "version": "1.0.0",
        "description": "Test plugin A",
        "authors": [{"name": "Test", "email": "test@test.com", "organization": "Test"}],
        "license": "MIT",
        "python_dependencies": ["numpy>=1.20", "requests"],
    }))

    # Plugin B: has different dependencies
    plugin_b = tmp_path / "plugin_b"
    plugin_b.mkdir()
    (plugin_b / "__init__.py").write_text("")
    (plugin_b / "plugin.json").write_text(json.dumps({
        "name": "Plugin B",
        "version": "0.1.0",
        "description": "Test plugin B",
        "authors": [{"name": "Test", "email": "test@test.com", "organization": "Test"}],
        "license": "MIT",
        "python_dependencies": ["scipy>=1.7"],
    }))

    # Plugin C: no plugin.json
    plugin_c = tmp_path / "plugin_c"
    plugin_c.mkdir()
    (plugin_c / "__init__.py").write_text("")

    # Plugin D: malformed plugin.json
    plugin_d = tmp_path / "plugin_d"
    plugin_d.mkdir()
    (plugin_d / "__init__.py").write_text("")
    (plugin_d / "plugin.json").write_text("this is not valid json {{{")

    # Plugin E: plugin.json without python_dependencies field
    plugin_e = tmp_path / "plugin_e"
    plugin_e.mkdir()
    (plugin_e / "__init__.py").write_text("")
    (plugin_e / "plugin.json").write_text(json.dumps({
        "name": "Plugin E",
        "version": "1.0.0",
        "description": "No deps",
        "authors": [],
        "license": "MIT",
    }))

    return tmp_path


def test_collect_deps_from_enabled_plugins(plugin_dir):
    deps = collect_plugin_dependencies(
        plugin_folders=[plugin_dir],
        enabled_plugins=["plugin_a", "plugin_b"],
    )
    assert "numpy>=1.20" in deps
    assert "requests" in deps
    assert "scipy>=1.7" in deps


def test_skips_disabled_plugins(plugin_dir):
    deps = collect_plugin_dependencies(
        plugin_folders=[plugin_dir],
        enabled_plugins=["plugin_a"],
    )
    assert "numpy>=1.20" in deps
    assert "requests" in deps
    assert "scipy>=1.7" not in deps


def test_workspace_add_override(plugin_dir):
    deps = collect_plugin_dependencies(
        plugin_folders=[plugin_dir],
        enabled_plugins=["plugin_a"],
        workspace_plugins_add=["plugin_b"],
    )
    assert "numpy>=1.20" in deps
    assert "scipy>=1.7" in deps


def test_workspace_remove_override(plugin_dir):
    deps = collect_plugin_dependencies(
        plugin_folders=[plugin_dir],
        enabled_plugins=["plugin_a", "plugin_b"],
        workspace_plugins_remove=["plugin_b"],
    )
    assert "numpy>=1.20" in deps
    assert "requests" in deps
    assert "scipy>=1.7" not in deps


def test_missing_plugin_json_skipped(plugin_dir):
    """Plugin C has no plugin.json -- should be skipped gracefully."""
    deps = collect_plugin_dependencies(
        plugin_folders=[plugin_dir],
        enabled_plugins=["plugin_c"],
    )
    assert deps == []


def test_malformed_plugin_json_skipped(plugin_dir):
    """Plugin D has invalid JSON -- should be skipped gracefully."""
    deps = collect_plugin_dependencies(
        plugin_folders=[plugin_dir],
        enabled_plugins=["plugin_d"],
    )
    assert deps == []


def test_no_python_dependencies_field(plugin_dir):
    """Plugin E has valid JSON but no python_dependencies -- returns empty."""
    deps = collect_plugin_dependencies(
        plugin_folders=[plugin_dir],
        enabled_plugins=["plugin_e"],
    )
    assert deps == []


def test_multiple_plugin_folders(tmp_path):
    """Plugins can come from multiple folders."""
    folder1 = tmp_path / "folder1"
    folder1.mkdir()
    p1 = folder1 / "alpha"
    p1.mkdir()
    (p1 / "plugin.json").write_text(json.dumps({
        "name": "Alpha",
        "version": "1.0",
        "description": "",
        "authors": [],
        "license": "MIT",
        "python_dependencies": ["pandas"],
    }))

    folder2 = tmp_path / "folder2"
    folder2.mkdir()
    p2 = folder2 / "beta"
    p2.mkdir()
    (p2 / "plugin.json").write_text(json.dumps({
        "name": "Beta",
        "version": "1.0",
        "description": "",
        "authors": [],
        "license": "MIT",
        "python_dependencies": ["matplotlib"],
    }))

    deps = collect_plugin_dependencies(
        plugin_folders=[folder1, folder2],
        enabled_plugins=["alpha", "beta"],
    )
    assert "pandas" in deps
    assert "matplotlib" in deps


def test_nonexistent_plugin_folder(tmp_path):
    """A non-existent folder should be skipped gracefully."""
    deps = collect_plugin_dependencies(
        plugin_folders=[tmp_path / "does_not_exist"],
        enabled_plugins=["anything"],
    )
    assert deps == []


def test_plugin_not_found_in_any_folder(tmp_path):
    """An enabled plugin that doesn't exist in any folder is simply ignored."""
    folder = tmp_path / "empty_folder"
    folder.mkdir()
    deps = collect_plugin_dependencies(
        plugin_folders=[folder],
        enabled_plugins=["nonexistent_plugin"],
    )
    assert deps == []
