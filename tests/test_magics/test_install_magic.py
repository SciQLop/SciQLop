"""%install delegates to user_api.install_packages and reports the result."""
from unittest.mock import patch

import pytest

from SciQLop.user_api.magics.install_magic import install_magic


def test_install_delegates_and_reports(capsys):
    with patch("SciQLop.user_api.magics.install_magic.install_packages") as m:
        m.return_value = {"ok": True, "installed": ["astropy", "spacepy"],
                          "already_present": [], "error": ""}
        install_magic("astropy spacepy")
    m.assert_called_once_with("astropy", "spacepy")
    assert "astropy" in capsys.readouterr().out


def test_install_no_args_raises():
    with pytest.raises(Exception, match="Usage"):
        install_magic("")


def test_install_failure_raises(capsys):
    with patch("SciQLop.user_api.magics.install_magic.install_packages") as m:
        m.return_value = {"ok": False, "installed": [],
                          "already_present": [], "error": "boom"}
        with pytest.raises(Exception, match="failed"):
            install_magic("nonexistent-pkg-xyz")
    assert "boom" in capsys.readouterr().out


@pytest.mark.parametrize("line", ["-e .", "--no-deps foo", "foo --upgrade"])
def test_install_refuses_uv_options(line):
    """Every token is recorded in the manifest as a requirement, so an option
    such as `-e` became a bogus "-e" dependency that broke the next workspace
    sync. Options are refused up front instead of being installed half-way."""
    with patch("SciQLop.user_api.magics.install_magic.install_packages") as m:
        with pytest.raises(Exception, match="package names"):
            install_magic(line)
    m.assert_not_called()
