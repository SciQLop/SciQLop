"""Tests for WorkspaceVenv."""

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
        assert venv.python_path == workspace_dir / ".venv" / "bin" / "python"


class TestExists:
    def test_false_when_venv_dir_missing(self, venv):
        assert venv.exists is False

    def test_false_when_python_missing(self, venv, workspace_dir):
        (workspace_dir / ".venv").mkdir(parents=True)
        assert venv.exists is False

    def test_true_when_venv_and_python_exist(self, venv, workspace_dir):
        python_path = workspace_dir / ".venv" / "bin" / "python"
        python_path.parent.mkdir(parents=True)
        python_path.touch()
        assert venv.exists is True


class TestCreate:
    @patch("SciQLop.components.workspaces.backend.workspace_venv.subprocess.run")
    @patch("SciQLop.components.workspaces.backend.workspace_venv.uv_command")
    def test_calls_uv_venv_with_system_site_packages(self, mock_uv_cmd, mock_run, venv, workspace_dir):
        mock_uv_cmd.return_value = ["uv", "venv", str(workspace_dir / ".venv"),
                                     "--system-site-packages", "--python", sys.executable]
        venv.create()

        mock_uv_cmd.assert_called_once_with(
            "venv",
            str(workspace_dir / ".venv"),
            "--system-site-packages",
            "--python",
            sys.executable,
        )
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


class TestEnsure:
    @patch.object(WorkspaceVenv, "create")
    def test_calls_create_when_venv_missing(self, mock_create, venv):
        venv.ensure()
        mock_create.assert_called_once()

    @patch.object(WorkspaceVenv, "create")
    def test_skips_create_when_venv_exists(self, mock_create, venv, workspace_dir):
        python_path = workspace_dir / ".venv" / "bin" / "python"
        python_path.parent.mkdir(parents=True)
        python_path.touch()

        venv.ensure()
        mock_create.assert_not_called()
