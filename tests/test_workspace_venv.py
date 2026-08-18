"""Tests for WorkspaceVenv."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from SciQLop.components.workspaces.backend.workspace_venv import WorkspaceVenv


@pytest.fixture
def workspace_dir(tmp_path):
    return tmp_path / "my_workspace"


@pytest.fixture
def venv(workspace_dir):
    return WorkspaceVenv(workspace_dir)


class TestPythonPath:
    def test_returns_correct_path(self, venv, workspace_dir):
        if sys.platform == "win32":
            expected = workspace_dir / ".venv" / "Scripts" / "python.exe"
        else:
            expected = workspace_dir / ".venv" / "bin" / "python"
        assert venv.python_path == expected


class TestExists:
    def test_false_when_venv_dir_missing(self, venv):
        assert venv.exists is False

    def test_false_when_python_missing(self, venv, workspace_dir):
        (workspace_dir / ".venv").mkdir(parents=True)
        assert venv.exists is False

    def test_true_when_venv_and_python_exist(self, venv, workspace_dir):
        python_path = venv.python_path
        python_path.parent.mkdir(parents=True)
        python_path.touch()
        assert venv.exists is True


class TestCreate:
    @patch("SciQLop.components.workspaces.backend.workspace_venv.subprocess.run")
    @patch("SciQLop.components.workspaces.backend.workspace_venv.uv_command")
    def test_creates_a_self_contained_venv(self, mock_uv_cmd, mock_run, venv, workspace_dir):
        """No --system-site-packages: the workspace installs its own SciQLop,
        and inheriting the launcher's would shadow it with a second copy."""
        mock_uv_cmd.return_value = ["uv", "venv", str(workspace_dir / ".venv"),
                                     "--python", sys.executable]
        venv.create()

        mock_uv_cmd.assert_called_once_with(
            "venv",
            str(workspace_dir / ".venv"),
            "--clear",
            "--python",
            sys.executable,
        )
        assert "--system-site-packages" not in mock_uv_cmd.call_args.args
        mock_run.assert_called_once_with(mock_uv_cmd.return_value, check=True)


class TestSync:
    @patch("SciQLop.components.workspaces.backend.workspace_venv.subprocess.run")
    @patch("SciQLop.components.workspaces.backend.workspace_venv.uv_command")
    def test_calls_uv_sync(self, mock_uv_cmd, mock_run, venv, workspace_dir):
        mock_uv_cmd.return_value = ["uv", "sync"]
        venv.sync()

        mock_uv_cmd.assert_called_once_with("sync")
        mock_run.assert_called_once_with(
            mock_uv_cmd.return_value, check=True, cwd=str(workspace_dir)
        )

    @patch("SciQLop.components.workspaces.backend.workspace_venv.subprocess.run")
    @patch("SciQLop.components.workspaces.backend.workspace_venv.uv_command")
    def test_calls_uv_sync_locked(self, mock_uv_cmd, mock_run, venv, workspace_dir):
        mock_uv_cmd.return_value = ["uv", "sync", "--locked"]
        venv.sync(locked=True)

        mock_uv_cmd.assert_called_once_with("sync", "--locked")
        mock_run.assert_called_once_with(
            mock_uv_cmd.return_value, check=True, cwd=str(workspace_dir)
        )


class TestCreateWithCallback:
    @patch("SciQLop.components.workspaces.backend.workspace_venv.subprocess.Popen")
    @patch("SciQLop.components.workspaces.backend.workspace_venv.uv_command")
    def test_streams_stderr_to_callback(self, mock_uv_cmd, mock_popen, venv, workspace_dir):
        mock_uv_cmd.return_value = ["uv", "venv", str(workspace_dir / ".venv")]
        proc = MagicMock()
        proc.stderr.__iter__ = MagicMock(return_value=iter(["Creating venv...\n", "Done\n"]))
        proc.wait.return_value = 0
        mock_popen.return_value = proc

        lines = []
        venv.create(on_output=lines.append)

        assert lines == ["Creating venv...", "Done"]
        mock_popen.assert_called_once_with(
            mock_uv_cmd.return_value, stderr=subprocess.PIPE, text=True,
        )

    @patch("SciQLop.components.workspaces.backend.workspace_venv.subprocess.Popen")
    @patch("SciQLop.components.workspaces.backend.workspace_venv.uv_command")
    def test_raises_on_nonzero_exit(self, mock_uv_cmd, mock_popen, venv, workspace_dir):
        mock_uv_cmd.return_value = ["uv", "venv"]
        proc = MagicMock()
        proc.stderr.__iter__ = MagicMock(return_value=iter([]))
        proc.wait.return_value = 1
        mock_popen.return_value = proc

        with pytest.raises(RuntimeError, match="uv command failed"):
            venv.create(on_output=lambda _: None)


class TestSyncWithCallback:
    @patch("SciQLop.components.workspaces.backend.workspace_venv.subprocess.Popen")
    @patch("SciQLop.components.workspaces.backend.workspace_venv.uv_command")
    def test_streams_stderr_to_callback(self, mock_uv_cmd, mock_popen, venv, workspace_dir):
        mock_uv_cmd.return_value = ["uv", "sync"]
        proc = MagicMock()
        proc.stderr.__iter__ = MagicMock(return_value=iter(["Resolved 10 packages\n"]))
        proc.wait.return_value = 0
        mock_popen.return_value = proc

        lines = []
        venv.sync(on_output=lines.append)

        assert lines == ["Resolved 10 packages"]
        mock_popen.assert_called_once_with(
            mock_uv_cmd.return_value, stderr=subprocess.PIPE, text=True,
            cwd=str(workspace_dir),
        )


class TestEnsure:
    @patch.object(WorkspaceVenv, "create")
    def test_calls_create_when_venv_missing(self, mock_create, venv):
        venv.ensure()
        mock_create.assert_called_once()

    def _make_venv(self, venv, workspace_dir, system_site_packages: bool):
        venv_dir = workspace_dir / ".venv"
        python_path = venv.python_path
        python_path.parent.mkdir(parents=True)
        python_path.touch()
        version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        cfg = f"version_info = {version}\n"
        if system_site_packages:
            cfg += "include-system-site-packages = true\n"
        (venv_dir / "pyvenv.cfg").write_text(cfg)

    @patch.object(WorkspaceVenv, "create")
    def test_skips_create_when_venv_exists(self, mock_create, venv, workspace_dir):
        self._make_venv(venv, workspace_dir, system_site_packages=False)
        venv.ensure()
        mock_create.assert_not_called()

    @patch.object(WorkspaceVenv, "create")
    def test_rebuilds_a_venv_that_inherited_the_host(self, mock_create, venv, workspace_dir):
        """Workspaces created before self-contained venvs have no SciQLop of
        their own — they read one out of the host — so they must be rebuilt
        rather than synced into the new layout."""
        self._make_venv(venv, workspace_dir, system_site_packages=True)
        venv.ensure()
        mock_create.assert_called_once()
