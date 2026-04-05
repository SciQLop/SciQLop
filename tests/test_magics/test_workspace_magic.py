from unittest.mock import patch, MagicMock
import pytest

from SciQLop.user_api.magics.workspace_magic import (
    workspace_magic, _cmd_status, _cmd_deps, _cmd_plugins,
    _cmd_examples, _cmd_help, SUBCOMMANDS,
)


def _make_fake_manifest(name="TestWS", directory="/tmp/ws", description="A test workspace",
                        requires=None, plugins_add=None, plugins_remove=None):
    m = MagicMock()
    m.name = name
    m.directory = directory
    m.description = description
    m.requires = requires or []
    m.plugins_add = plugins_add or []
    m.plugins_remove = plugins_remove or []
    return m


def _make_fake_workspace(manifest=None):
    ws = MagicMock()
    m = manifest or _make_fake_manifest()
    ws._manifest = m
    ws.name = m.name
    ws.workspace_dir = m.directory
    return ws


class TestWorkspaceStatus:
    @patch("SciQLop.user_api.magics.workspace_magic._get_workspace")
    def test_status_shows_name_and_path(self, mock_get, capsys):
        mock_get.return_value = _make_fake_workspace()
        _cmd_status()
        out = capsys.readouterr().out
        assert "TestWS" in out
        assert "/tmp/ws" in out

    @patch("SciQLop.user_api.magics.workspace_magic._get_workspace")
    def test_status_no_workspace(self, mock_get, capsys):
        mock_get.return_value = None
        _cmd_status()
        assert "No workspace" in capsys.readouterr().out

    @patch("SciQLop.user_api.magics.workspace_magic._get_workspace")
    def test_status_shows_deps_count(self, mock_get, capsys):
        m = _make_fake_manifest(requires=["numpy", "scipy"])
        mock_get.return_value = _make_fake_workspace(m)
        _cmd_status()
        assert "2" in capsys.readouterr().out

    @patch("SciQLop.user_api.magics.workspace_magic._get_workspace")
    def test_status_shows_plugin_overrides(self, mock_get, capsys):
        m = _make_fake_manifest(plugins_add=["extra"], plugins_remove=["broken"])
        mock_get.return_value = _make_fake_workspace(m)
        _cmd_status()
        out = capsys.readouterr().out
        assert "extra" in out
        assert "broken" in out


class TestWorkspaceDeps:
    @patch("SciQLop.user_api.magics.workspace_magic._get_manifest")
    def test_deps_lists_all(self, mock_manifest, capsys):
        mock_manifest.return_value = _make_fake_manifest(requires=["numpy>=1.26", "scipy"])
        _cmd_deps()
        out = capsys.readouterr().out
        assert "numpy>=1.26" in out
        assert "scipy" in out

    @patch("SciQLop.user_api.magics.workspace_magic._get_manifest")
    def test_deps_empty(self, mock_manifest, capsys):
        mock_manifest.return_value = _make_fake_manifest()
        _cmd_deps()
        assert "No dependencies" in capsys.readouterr().out


class TestWorkspacePlugins:
    @patch("SciQLop.user_api.magics.workspace_magic._get_manifest")
    def test_plugins_shows_overrides(self, mock_manifest, capsys):
        mock_manifest.return_value = _make_fake_manifest(plugins_add=["a"], plugins_remove=["b"])
        _cmd_plugins()
        out = capsys.readouterr().out
        assert "+ a" in out
        assert "- b" in out

    @patch("SciQLop.user_api.magics.workspace_magic._get_manifest")
    def test_plugins_empty(self, mock_manifest, capsys):
        mock_manifest.return_value = _make_fake_manifest()
        _cmd_plugins()
        assert "No plugin overrides" in capsys.readouterr().out


class TestWorkspaceInstall:
    @patch("SciQLop.user_api.magics.install_magic.install_magic")
    def test_install_delegates(self, mock_install):
        from SciQLop.user_api.magics.workspace_magic import _cmd_install
        _cmd_install(["numpy", "scipy>=1.0"])
        mock_install.assert_called_once_with("numpy scipy>=1.0")


class TestWorkspaceExamples:
    @patch("SciQLop.user_api.magics.workspace_magic._list_examples")
    def test_examples_lists_names(self, mock_list, capsys):
        ex = MagicMock()
        ex.name = "Simple Virtual Product"
        ex.tags = ["basic"]
        ex.description = "A simple example"
        mock_list.return_value = [ex]
        _cmd_examples()
        out = capsys.readouterr().out
        assert "Simple Virtual Product" in out
        assert "basic" in out

    @patch("SciQLop.user_api.magics.workspace_magic._list_examples")
    def test_examples_empty(self, mock_list, capsys):
        mock_list.return_value = []
        _cmd_examples()
        assert "No examples" in capsys.readouterr().out


class TestWorkspaceDispatch:
    @patch("SciQLop.user_api.magics.workspace_magic._get_workspace")
    def test_default_is_status(self, mock_get, capsys):
        mock_get.return_value = _make_fake_workspace()
        workspace_magic("")
        assert "TestWS" in capsys.readouterr().out

    def test_help(self, capsys):
        workspace_magic("help")
        out = capsys.readouterr().out
        for subcmd in SUBCOMMANDS:
            assert subcmd in out

    def test_unknown_subcommand_raises(self):
        with pytest.raises(Exception, match="Unknown subcommand"):
            workspace_magic("nonexistent")


class TestWorkspaceCompletion:
    def test_completer_returns_subcommands(self):
        from SciQLop.user_api.magics.completions import _match_workspace
        ctx = MagicMock()
        ctx.line_with_cursor = "%workspace "
        ctx.token = ""
        result = _match_workspace(ctx)
        texts = [c.text for c in result["completions"]]
        assert "status" in texts
        assert "deps" in texts
        assert "install" in texts

    def test_completer_filters_subcommands(self):
        from SciQLop.user_api.magics.completions import _match_workspace
        ctx = MagicMock()
        ctx.line_with_cursor = "%workspace dep"
        ctx.token = "dep"
        result = _match_workspace(ctx)
        texts = [c.text for c in result["completions"]]
        assert "deps" in texts
        assert "status" not in texts

    def test_completer_ignores_other_magics(self):
        from SciQLop.user_api.magics.completions import _match_workspace
        ctx = MagicMock()
        ctx.line_with_cursor = "%plot something"
        ctx.token = "something"
        result = _match_workspace(ctx)
        assert len(result["completions"]) == 0
