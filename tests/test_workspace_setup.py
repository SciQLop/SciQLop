"""Tests for workspace_setup orchestrator."""

from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from SciQLop.components.workspaces.backend.workspace_manifest import WorkspaceManifest


MODULE = "SciQLop.components.workspaces.backend.workspace_setup"


@pytest.fixture
def workspace_dir(tmp_path):
    return tmp_path / "my_workspace"


@pytest.fixture
def mock_venv():
    venv = MagicMock()
    venv.python_path = Path("/fake/.venv/bin/python")
    return venv


@pytest.fixture
def patches(mock_venv):
    """Patch external dependencies used by prepare_workspace."""
    with (
        patch(f"{MODULE}.get_globally_enabled_plugins", return_value=["pluginA", "pluginB"]),
        patch(f"{MODULE}.get_plugin_folders", return_value=["/plugins/builtin", "/plugins/user"]),
        patch(f"{MODULE}.collect_plugin_dependencies", return_value=["numpy>=1.24", "requests"]),
        patch(f"{MODULE}.generate_pyproject_toml") as mock_gen,
        patch(f"{MODULE}.WorkspaceVenv", return_value=mock_venv) as mock_venv_cls,
    ):
        yield {
            "generate_pyproject_toml": mock_gen,
            "WorkspaceVenv": mock_venv_cls,
            "venv": mock_venv,
        }


class TestPrepareWorkspaceCreatesDir:
    def test_creates_workspace_dir_if_missing(self, workspace_dir, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        assert not workspace_dir.exists()
        prepare_workspace(workspace_dir, workspace_name="Test WS")
        assert workspace_dir.exists()


class TestPrepareWorkspaceManifest:
    def test_creates_default_manifest_when_none_exists(self, workspace_dir, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        prepare_workspace(workspace_dir, workspace_name="Test WS")

        manifest_path = workspace_dir / "workspace.sciqlop"
        # The function should have saved a default manifest
        assert manifest_path.exists()

    def test_loads_existing_manifest(self, workspace_dir, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        workspace_dir.mkdir(parents=True)
        manifest = WorkspaceManifest(
            name="Existing",
            plugins_add=["extra_plugin"],
            requires=["scipy"],
        )
        import tomli_w

        manifest_path = workspace_dir / "workspace.sciqlop"
        manifest.save(manifest_path)

        prepare_workspace(workspace_dir)

        # generate_pyproject_toml should have been called with the loaded manifest
        gen_call = patches["generate_pyproject_toml"]
        gen_call.assert_called_once()
        used_manifest = gen_call.call_args[0][0]
        assert used_manifest.name == "Existing"
        assert used_manifest.plugins_add == ["extra_plugin"]
        assert used_manifest.requires == ["scipy"]

    def test_default_manifest_uses_dir_name_when_no_name_given(self, workspace_dir, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        prepare_workspace(workspace_dir)

        manifest_path = workspace_dir / "workspace.sciqlop"
        loaded = WorkspaceManifest.load(manifest_path)
        assert loaded.name == workspace_dir.name


class TestPrepareWorkspaceGeneratesPyproject:
    def test_calls_generate_pyproject_with_correct_args(self, workspace_dir, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        prepare_workspace(workspace_dir, workspace_name="Test")

        gen = patches["generate_pyproject_toml"]
        gen.assert_called_once()
        args = gen.call_args[0]
        # arg 0: manifest, arg 1: plugin_deps, arg 2: output_path
        assert isinstance(args[0], WorkspaceManifest)
        assert args[1] == ["numpy>=1.24", "requests"]
        assert Path(args[2]) == workspace_dir / "pyproject.toml"


class TestPrepareWorkspaceVenv:
    def test_calls_venv_ensure_and_sync(self, workspace_dir, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        prepare_workspace(workspace_dir, workspace_name="Test")

        patches["WorkspaceVenv"].assert_called_once_with(workspace_dir)
        patches["venv"].ensure.assert_called_once_with(on_output=None)
        patches["venv"].sync.assert_called_once_with(locked=False, on_output=None)

    def test_locked_sync(self, workspace_dir, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        prepare_workspace(workspace_dir, workspace_name="Test", locked=True)

        patches["venv"].sync.assert_called_once_with(locked=True, on_output=None)

    def test_returns_python_path(self, workspace_dir, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        result = prepare_workspace(workspace_dir, workspace_name="Test")
        assert result == Path("/fake/.venv/bin/python")


class TestPrepareWorkspaceCallback:
    def test_forwards_on_output_to_venv_methods(self, workspace_dir, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        cb = MagicMock()
        prepare_workspace(workspace_dir, workspace_name="Test", on_output=cb)

        patches["venv"].ensure.assert_called_once_with(on_output=cb)
        patches["venv"].sync.assert_called_once_with(locked=False, on_output=cb)

    def test_no_callback_by_default(self, workspace_dir, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        prepare_workspace(workspace_dir, workspace_name="Test")

        patches["venv"].ensure.assert_called_once_with(on_output=None)
        patches["venv"].sync.assert_called_once_with(locked=False, on_output=None)


class TestCollectPluginDepsArgs:
    def test_passes_workspace_overrides_to_collect(self, workspace_dir):
        """Verify that manifest plugin overrides are passed to collect_plugin_dependencies."""
        mock_venv = MagicMock()
        mock_venv.python_path = Path("/fake/python")

        workspace_dir.mkdir(parents=True)
        manifest = WorkspaceManifest(
            name="Override Test",
            plugins_add=["extra"],
            plugins_remove=["unwanted"],
        )
        manifest.save(workspace_dir / "workspace.sciqlop")

        with (
            patch(f"{MODULE}.get_globally_enabled_plugins", return_value=["pluginA"]),
            patch(f"{MODULE}.get_plugin_folders", return_value=["/plugins"]),
            patch(f"{MODULE}.collect_plugin_dependencies", return_value=[]) as mock_collect,
            patch(f"{MODULE}.generate_pyproject_toml"),
            patch(f"{MODULE}.WorkspaceVenv", return_value=mock_venv),
        ):
            from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

            prepare_workspace(workspace_dir)

            mock_collect.assert_called_once_with(
                plugin_folders=["/plugins"],
                enabled_plugins=["pluginA"],
                workspace_plugins_add=["extra"],
                workspace_plugins_remove=["unwanted"],
            )


class TestHelperFunctions:
    def test_get_globally_enabled_plugins(self):
        from SciQLop.components.plugins.backend.settings import PluginConfig

        mock_settings = MagicMock()
        mock_settings.plugins = {
            "enabled_one": PluginConfig(enabled=True),
            "disabled_one": PluginConfig(enabled=False),
            "enabled_two": PluginConfig(enabled=True),
        }

        with patch(f"{MODULE}.SciQLopPluginsSettings", return_value=mock_settings):
            from SciQLop.components.workspaces.backend.workspace_setup import get_globally_enabled_plugins

            result = get_globally_enabled_plugins()
            assert sorted(result) == ["enabled_one", "enabled_two"]

    def test_get_plugin_folders(self):
        with patch(f"{MODULE}.plugins_folders", return_value=["/a", "/b"]):
            from SciQLop.components.workspaces.backend.workspace_setup import get_plugin_folders

            assert get_plugin_folders() == ["/a", "/b"]
