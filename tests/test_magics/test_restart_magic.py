"""%restart restarts SciQLop into the same workspace, like the Settings Restart button."""
from unittest.mock import patch

import pytest


def test_restart_restarts_sciqlop(capsys):
    from SciQLop.user_api.magics.restart_magic import restart_magic
    with patch("SciQLop.sciqlop_app.restart_sciqlop") as restart:
        restart_magic("")
    restart.assert_called_once_with()
    assert "Restarting" in capsys.readouterr().out


def test_restart_takes_no_arguments():
    from SciQLop.user_api.magics.restart_magic import restart_magic
    with patch("SciQLop.sciqlop_app.restart_sciqlop") as restart:
        with pytest.raises(Exception, match="Usage"):
            restart_magic("now")
    restart.assert_not_called()


def test_restart_is_a_core_magic():
    from SciQLop.user_api.magics import contribute_core_magics
    from SciQLop.core.magics import MAGICS
    contribute_core_magics()
    assert MAGICS.get("sciqlop.restart").name == "restart"
