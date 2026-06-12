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
        patch(f"{MODULE}.repair_lab_assets") as mock_repair,
    ):
        yield {
            "generate_pyproject_toml": mock_gen,
            "WorkspaceVenv": mock_venv_cls,
            "venv": mock_venv,
            "repair_lab_assets": mock_repair,
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

    def test_repairs_lab_assets_after_sync(self, workspace_dir, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        prepare_workspace(workspace_dir, workspace_name="Test")

        patches["repair_lab_assets"].assert_called_once_with(
            patches["venv"].venv_dir, on_output=None)

    def test_repairs_lab_assets_even_when_sync_fails(self, workspace_dir, patches, tmp_path):
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        venv = patches["venv"]
        python_path = tmp_path / "python"
        python_path.write_text("")
        venv.python_path = python_path
        venv.sync.side_effect = RuntimeError("offline")

        prepare_workspace(workspace_dir, workspace_name="Test")

        patches["repair_lab_assets"].assert_called_once()


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


class TestPrepareWorkspaceOffline:
    """Issue #115: SciQLop must not abort startup when sync fails offline."""

    def test_sync_failure_is_tolerated_when_python_exists(self, workspace_dir, patches, tmp_path):
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        venv = patches["venv"]
        python_path = tmp_path / ".venv" / "bin" / "python"
        python_path.parent.mkdir(parents=True)
        python_path.write_text("")
        venv.python_path = python_path
        venv.sync.side_effect = RuntimeError(
            "uv command failed (exit 2):\n  uv sync\nNetwork is unreachable"
        )

        cb = MagicMock()
        result = prepare_workspace(workspace_dir, workspace_name="Test", on_output=cb)

        assert result == python_path
        cb.assert_any_call(
            "Workspace dependency sync failed: "
            "uv command failed (exit 2):\n  uv sync\nNetwork is unreachable"
        )
        cb.assert_any_call(
            "Continuing with existing venv. Run with network to install missing packages."
        )

    def test_sync_failure_propagates_when_python_missing(self, workspace_dir, patches, tmp_path):
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        venv = patches["venv"]
        venv.python_path = tmp_path / "missing" / "python"
        venv.sync.side_effect = RuntimeError("uv venv failed")

        with pytest.raises(RuntimeError):
            prepare_workspace(workspace_dir, workspace_name="Test")


class TestStaleLockfileInvalidation:
    """A uv.lock older than pyproject.toml is stale and must be removed."""

    def _make_pyproject_writer(self, content="dummy"):
        def writer(manifest, deps, output_path):
            Path(output_path).write_text(content)
        return writer

    def test_stale_lockfile_is_removed(self, workspace_dir, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        patches["generate_pyproject_toml"].side_effect = self._make_pyproject_writer()
        workspace_dir.mkdir(parents=True)
        lockfile = workspace_dir / "uv.lock"
        lockfile.write_text("old lock")
        import os, time
        old_mtime = time.time() - 3600
        os.utime(lockfile, (old_mtime, old_mtime))

        prepare_workspace(workspace_dir, workspace_name="Test")

        assert not lockfile.exists()

    def test_fresh_lockfile_is_kept(self, workspace_dir, patches):
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        patches["generate_pyproject_toml"].side_effect = self._make_pyproject_writer()
        workspace_dir.mkdir(parents=True)
        pyproject = workspace_dir / "pyproject.toml"
        pyproject.write_text("dummy")
        lockfile = workspace_dir / "uv.lock"
        lockfile.write_text("fresh lock")
        import os, time
        future = time.time() + 3600
        os.utime(lockfile, (future, future))

        prepare_workspace(workspace_dir, workspace_name="Test")

        assert lockfile.exists()

    def test_lockfile_preserved_in_locked_mode(self, workspace_dir, patches):
        """Archive imports pass locked=True and ship their own lockfile;
        invalidating it would force re-resolution and contradict the archive's
        promise of reproducibility."""
        from SciQLop.components.workspaces.backend.workspace_setup import prepare_workspace

        patches["generate_pyproject_toml"].side_effect = self._make_pyproject_writer()
        workspace_dir.mkdir(parents=True)
        lockfile = workspace_dir / "uv.lock"
        lockfile.write_text("archive lock")
        import os, time
        old_mtime = time.time() - 3600
        os.utime(lockfile, (old_mtime, old_mtime))

        prepare_workspace(workspace_dir, workspace_name="Test", locked=True)

        assert lockfile.exists()


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
