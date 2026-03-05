import os
import shutil
from unittest.mock import patch

import pytest

from SciQLop.core.common.uv import find_uv, uv_command


class TestFindUv:
    def test_find_uv_on_path(self):
        """If uv is on PATH, find_uv should return its path."""
        uv_path = shutil.which("uv")
        if uv_path is None:
            pytest.skip("uv not found on PATH")
        with patch.dict(os.environ, {}, clear=False):
            # Remove APPDIR so it falls through to PATH lookup
            os.environ.pop("APPDIR", None)
            result = find_uv()
        assert result is not None
        assert "uv" in os.path.basename(result)

    def test_find_uv_appdir(self, tmp_path):
        """When APPDIR is set, find_uv should return the bundled uv path."""
        uv_dir = tmp_path / "opt" / "uv"
        uv_dir.mkdir(parents=True)
        uv_bin = uv_dir / "uv"
        uv_bin.touch()
        uv_bin.chmod(0o755)

        with patch.dict(os.environ, {"APPDIR": str(tmp_path)}):
            result = find_uv()
        assert result == str(uv_bin)

    def test_find_uv_appdir_missing_binary(self, tmp_path):
        """When APPDIR is set but uv binary doesn't exist, fall back to PATH."""
        with patch.dict(os.environ, {"APPDIR": str(tmp_path)}):
            with patch("shutil.which", return_value="/usr/bin/uv"):
                result = find_uv()
        assert result == "/usr/bin/uv"

    def test_find_uv_returns_none_when_not_found(self):
        """When uv is not available anywhere, find_uv should return None."""
        env = os.environ.copy()
        env.pop("APPDIR", None)
        with patch.dict(os.environ, env, clear=True):
            with patch("shutil.which", return_value=None):
                result = find_uv()
        assert result is None


class TestUvCommand:
    def test_uv_command_builds_list(self):
        """uv_command should build a command list with args."""
        with patch("SciQLop.core.common.uv.find_uv", return_value="/usr/bin/uv"):
            result = uv_command("venv", "--python", "3.12")
        assert result == ["/usr/bin/uv", "venv", "--python", "3.12"]

    def test_uv_command_no_args(self):
        """uv_command with no args should return just the uv path."""
        with patch("SciQLop.core.common.uv.find_uv", return_value="/usr/bin/uv"):
            result = uv_command()
        assert result == ["/usr/bin/uv"]

    def test_uv_command_raises_when_not_found(self):
        """uv_command should raise RuntimeError when uv is not found."""
        with patch("SciQLop.core.common.uv.find_uv", return_value=None):
            with pytest.raises(RuntimeError, match="Could not find uv"):
                uv_command("sync")
