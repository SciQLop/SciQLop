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


class TestHasSciqlopInstalled:
    """A freshly created venv has a Python interpreter but no packages yet —
    ``exists``/``python_path`` can't tell that apart from a venv whose last
    sync actually succeeded, which is what prepare_workspace's offline
    fallback needs to know before deciding to "keep running the old app"."""

    def test_false_when_venv_missing(self, venv):
        assert venv.has_sciqlop_installed is False

    def test_false_when_site_packages_has_no_sciqlop(self, venv, workspace_dir):
        site = workspace_dir / ".venv" / "lib" / "python3.13" / "site-packages"
        (site / "numpy-2.0.0.dist-info").mkdir(parents=True)
        assert venv.has_sciqlop_installed is False

    def test_true_when_sciqlop_dist_info_present(self, venv, workspace_dir):
        site = workspace_dir / ".venv" / "lib" / "python3.13" / "site-packages"
        (site / "sciqlop-0.13.0.dev0.dist-info").mkdir(parents=True)
        (site / "SciQLop").mkdir()
        (site / "SciQLop" / "__init__.py").touch()
        assert venv.has_sciqlop_installed is True

    def test_true_on_windows_site_packages_layout(self, venv, workspace_dir):
        site = workspace_dir / ".venv" / "Lib" / "site-packages"
        (site / "sciqlop-0.13.0.dev0.dist-info").mkdir(parents=True)
        (site / "SciQLop").mkdir()
        (site / "SciQLop" / "__init__.py").touch()
        assert venv.has_sciqlop_installed is True

    def test_false_when_dist_info_present_but_package_dir_missing(self, venv, workspace_dir):
        """A partial/interrupted install can leave dist-info behind without the
        actual package — that must not be reported as "installed"."""
        site = workspace_dir / ".venv" / "lib" / "python3.13" / "site-packages"
        (site / "sciqlop-0.13.0.dev0.dist-info").mkdir(parents=True)
        assert venv.has_sciqlop_installed is False


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
            "--native-tls",
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

        mock_uv_cmd.assert_called_once_with("sync", "--native-tls")
        mock_run.assert_called_once_with(
            mock_uv_cmd.return_value, check=True, cwd=str(workspace_dir)
        )

    @patch("SciQLop.components.workspaces.backend.workspace_venv.subprocess.run")
    @patch("SciQLop.components.workspaces.backend.workspace_venv.uv_command")
    def test_calls_uv_sync_locked(self, mock_uv_cmd, mock_run, venv, workspace_dir):
        mock_uv_cmd.return_value = ["uv", "sync", "--locked"]
        venv.sync(locked=True)

        mock_uv_cmd.assert_called_once_with("sync", "--locked", "--native-tls")
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


class TestNativeTls:
    """uv needs --native-tls to trust a corporate MITM proxy's root CA,
    the same reason SciQLop/components/appstore/backend.py passes it."""

    @patch("SciQLop.components.workspaces.backend.workspace_venv._run_uv")
    @patch("SciQLop.components.workspaces.backend.workspace_venv.uv_command",
           side_effect=lambda *args: list(args))
    def test_create_command_contains_native_tls(self, mock_uv_cmd, mock_run_uv, venv):
        venv.create()

        cmd = mock_run_uv.call_args.args[0]
        assert "--native-tls" in cmd

    @patch("SciQLop.components.workspaces.backend.workspace_venv._run_uv")
    @patch("SciQLop.components.workspaces.backend.workspace_venv.uv_command",
           side_effect=lambda *args: list(args))
    def test_sync_command_contains_native_tls(self, mock_uv_cmd, mock_run_uv, venv):
        venv.sync()

        cmd = mock_run_uv.call_args.args[0]
        assert "--native-tls" in cmd


def _write_pyvenv_cfg(venv_dir: Path, home: Path, version: str) -> None:
    (venv_dir / "pyvenv.cfg").write_text(f"home = {home}\nversion_info = {version}\n")


def _current_version() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def _make_symlinked_venv(workspace_dir: Path, target: Path, home: Path | None = None,
                          version: str | None = None) -> Path:
    """A venv whose bin/python* are symlinks to *target*, plus a sentinel file
    under site-packages to prove a repoint doesn't touch installed packages."""
    venv_dir = workspace_dir / ".venv"
    bin_dir = venv_dir / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "python").symlink_to(target)
    (bin_dir / "python3").symlink_to(target)
    _write_pyvenv_cfg(venv_dir, home or target.parent, version or _current_version())
    site = venv_dir / f"lib/python{sys.version_info.major}.{sys.version_info.minor}/site-packages"
    site.mkdir(parents=True)
    (site / "sentinel.txt").write_text("keep me")
    return venv_dir


class TestNeedsRecreateAndRepoint:
    def test_dangling_symlink_repoints_instead_of_recreating(self, venv, workspace_dir, tmp_path):
        old_target = tmp_path / "old_mount" / "bin" / "python3"  # never created: dangling
        new_target = tmp_path / "new_mount" / "bin" / "python3"
        new_target.parent.mkdir(parents=True)
        new_target.touch()
        _make_symlinked_venv(workspace_dir, old_target)

        with patch("SciQLop.components.workspaces.backend.workspace_venv.get_python",
                   return_value=str(new_target)):
            assert venv._needs_recreate() is False
            assert venv._needs_repoint() is True

    def test_stale_but_existing_symlink_repoints_instead_of_recreating(
        self, venv, workspace_dir, tmp_path
    ):
        """The AppImage case: the old mountpoint still exists (this launch's
        FUSE mount hasn't been torn down yet) but it's not *this* launch's."""
        old_target = tmp_path / "old_mount" / "bin" / "python3"
        old_target.parent.mkdir(parents=True)
        old_target.touch()
        new_target = tmp_path / "new_mount" / "bin" / "python3"
        new_target.parent.mkdir(parents=True)
        new_target.touch()
        _make_symlinked_venv(workspace_dir, old_target)

        with patch("SciQLop.components.workspaces.backend.workspace_venv.get_python",
                   return_value=str(new_target)):
            assert venv._needs_recreate() is False
            assert venv._needs_repoint() is True

    def test_version_mismatch_needs_recreate(self, venv, workspace_dir, tmp_path):
        target = tmp_path / "python3"
        target.touch()
        _make_symlinked_venv(workspace_dir, target, version="1.0.0")

        with patch("SciQLop.components.workspaces.backend.workspace_venv.get_python",
                   return_value=str(target)):
            assert venv._needs_recreate() is True

    def test_non_symlink_python_without_interpreter_in_home_needs_recreate(
        self, venv, workspace_dir, tmp_path
    ):
        venv_dir = workspace_dir / ".venv"
        bin_dir = venv_dir / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "python").touch()  # a real file, not a symlink (e.g. Windows copy)
        empty_home = tmp_path / "no_interpreter_here"
        empty_home.mkdir()
        _write_pyvenv_cfg(venv_dir, empty_home, _current_version())

        assert venv._needs_recreate() is True

    def test_malformed_version_info_needs_recreate_without_raising(
        self, venv, workspace_dir, tmp_path
    ):
        venv_dir = workspace_dir / ".venv"
        bin_dir = venv_dir / "bin"
        bin_dir.mkdir(parents=True)
        (bin_dir / "python").touch()
        _write_pyvenv_cfg(venv_dir, tmp_path, "garbage")

        assert venv._needs_recreate() is True


class TestRepointInterpreter:
    def test_ensure_repoints_without_recreating(self, workspace_dir, tmp_path):
        venv = WorkspaceVenv(workspace_dir)
        old_target = tmp_path / "old_mount" / "bin" / "python3"
        new_target = tmp_path / "new_mount" / "bin" / "python3"
        new_target.parent.mkdir(parents=True)
        new_target.touch()
        venv_dir = _make_symlinked_venv(workspace_dir, old_target)
        sentinel = venv_dir / f"lib/python{sys.version_info.major}.{sys.version_info.minor}" \
            "/site-packages/sentinel.txt"

        with patch("SciQLop.components.workspaces.backend.workspace_venv.get_python",
                   return_value=str(new_target)), \
             patch.object(WorkspaceVenv, "create") as mock_create:
            lines = []
            venv.ensure(on_output=lines.append)

        mock_create.assert_not_called()
        assert sentinel.exists()
        assert (venv_dir / "bin" / "python").resolve() == new_target.resolve()
        assert (venv_dir / "bin" / "python3").resolve() == new_target.resolve()
        cfg_text = (venv_dir / "pyvenv.cfg").read_text()
        assert f"home = {new_target.parent}" in cfg_text
        assert any("Re-linking workspace interpreter" in line for line in lines)

    def test_repoint_survives_concurrent_symlink_race(self, workspace_dir, tmp_path):
        """L-w2: a second instance can win the race and repoint the same link
        between this one's unlink() and symlink_to() — that FileExistsError
        means the link is already correct, not a real failure."""
        venv = WorkspaceVenv(workspace_dir)
        old_target = tmp_path / "old_mount" / "bin" / "python3"
        new_target = tmp_path / "new_mount" / "bin" / "python3"
        new_target.parent.mkdir(parents=True)
        new_target.touch()
        _make_symlinked_venv(workspace_dir, old_target)

        real_symlink_to = Path.symlink_to
        calls = {"n": 0}

        def flaky_symlink_to(self, target, *a, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                raise FileExistsError("raced by another instance")
            return real_symlink_to(self, target, *a, **kw)

        with patch("SciQLop.components.workspaces.backend.workspace_venv.get_python",
                   return_value=str(new_target)), \
             patch.object(Path, "symlink_to", flaky_symlink_to):
            venv._repoint_interpreter()  # must not raise

        assert calls["n"] >= 1


class TestRewritePyvenvHomeAtomic:
    def test_uses_atomic_write(self, workspace_dir, tmp_path, monkeypatch):
        """L-w3: pyvenv.cfg must never be left truncated by a crash mid-write."""
        venv = WorkspaceVenv(workspace_dir)
        venv_dir = workspace_dir / ".venv"
        venv_dir.mkdir(parents=True)
        (venv_dir / "pyvenv.cfg").write_text("home = /old\nversion_info = 3.14.0\n")
        calls = []
        monkeypatch.setattr(
            "SciQLop.components.workspaces.backend.workspace_venv.write_text_atomic",
            lambda path, text: calls.append((path, text)),
        )

        venv._rewrite_pyvenv_home(tmp_path / "new_home")

        assert len(calls) == 1
        path, text = calls[0]
        assert path == venv_dir / "pyvenv.cfg"
        assert f"home = {tmp_path / 'new_home'}" in text


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
