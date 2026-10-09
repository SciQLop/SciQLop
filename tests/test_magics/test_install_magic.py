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


def _ok(installed, **extra):
    return {"ok": True, "installed": installed, "already_present": [], "error": "",
            "restart_required": [], "not_loaded": {}, **extra}


def test_unquoted_pep508_url_spec_stays_one_package():
    """Without quotes the space-separated `name @ url` was split into three
    bogus packages: "sciqlop-vdf", "@" and the URL."""
    spec = "sciqlop-vdf @ git+https://github.com/nicolasaunai/sciqlop-vdf@v0.3.0"
    with patch("SciQLop.user_api.magics.install_magic.install_packages") as m:
        m.return_value = _ok([spec])
        install_magic(f"{spec} astropy")
    m.assert_called_once_with(spec, "astropy")


def test_install_reports_what_still_needs_a_restart_or_was_refused(capsys):
    with patch("SciQLop.user_api.magics.install_magic.install_packages") as m:
        m.return_value = _ok(["a", "b"], restart_required=["a"],
                             not_loaded={"b": "needs SciQLop >=9"})
        install_magic("a b")
    out = capsys.readouterr().out
    assert "Restart SciQLop to use the new version of: a" in out
    assert "b was not loaded: needs SciQLop >=9" in out


def test_a_plain_install_does_not_mention_restart(capsys):
    with patch("SciQLop.user_api.magics.install_magic.install_packages") as m:
        m.return_value = _ok(["sciqlop-vdf"])
        install_magic("sciqlop-vdf")
    assert "estart" not in capsys.readouterr().out


@pytest.mark.parametrize("line", ["-e .", "--no-deps foo", "foo --upgrade"])
def test_install_refuses_uv_options(line):
    """Every token is recorded in the manifest as a requirement, so an option
    such as `-e` became a bogus "-e" dependency that broke the next workspace
    sync. Options are refused up front instead of being installed half-way."""
    with patch("SciQLop.user_api.magics.install_magic.install_packages") as m:
        with pytest.raises(Exception, match="package names"):
            install_magic(line)
    m.assert_not_called()
