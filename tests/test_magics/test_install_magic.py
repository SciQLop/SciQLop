"""Tests for %install magic — install + manifest recording."""
from unittest.mock import patch, MagicMock
import pytest

from SciQLop.user_api.magics.install_magic import install_magic


def test_install_calls_uv_and_records():
    mock_ws = MagicMock()

    with patch("SciQLop.user_api.magics.install_magic._run_uv_install") as mock_uv, \
         patch("SciQLop.user_api.magics.install_magic._record_in_manifest") as mock_record, \
         patch("SciQLop.user_api.threading._invoker", None):

        mock_uv.return_value = MagicMock(returncode=0, stdout="OK\n", stderr="")
        install_magic("astropy spacepy")

    mock_uv.assert_called_once_with(["astropy", "spacepy"])
    mock_record.assert_called_once_with(["astropy", "spacepy"])


def test_install_no_args_raises():
    with pytest.raises(Exception, match="Usage"):
        install_magic("")


def test_install_failure_raises():
    with patch("SciQLop.user_api.magics.install_magic._run_uv_install") as mock_uv:
        mock_uv.return_value = MagicMock(returncode=1, stdout="", stderr="error\n")
        with pytest.raises(Exception, match="failed"):
            install_magic("nonexistent-pkg-xyz")
