"""A failed workspace preparation is explained in plain words, above the traceback."""
import pytest

from SciQLop.components.startup.failure import explain_preparation_failure

NETWORK_FAILURE = """Traceback (most recent call last):
  File "workspace_setup.py", line 410, in sync
RuntimeError: uv sync failed
error: Failed to fetch: `https://pypi.org/simple/sciqlop/`
  Caused by: error sending request for url (https://pypi.org/simple/sciqlop/)
  Caused by: dns error: failed to lookup address information
"""
OTHER_FAILURE = """Traceback (most recent call last):
  File "workspace_setup.py", line 410, in sync
RuntimeError: uv sync failed
error: No solution found when resolving dependencies
"""


def test_a_network_failure_says_the_first_start_needs_the_network():
    text = explain_preparation_failure(NETWORK_FAILURE)
    assert "could not download" in text
    assert "network" in text and "proxy" in text
    assert "Reset" not in text  # a reset offline leaves nothing to start with


def test_any_other_failure_points_to_reset_environment():
    text = explain_preparation_failure(OTHER_FAILURE)
    assert "could not prepare this workspace" in text
    assert "--reset-environment" in text and "notebooks" in text


@pytest.fixture
def window(qtbot):
    from SciQLop.components.startup.startup_window import StartupWindow
    w = StartupWindow()
    qtbot.addWidget(w)
    w.show()
    return w


def test_the_error_screen_shows_the_explanation_above_the_details(window):
    window.show_error(OTHER_FAILURE, explain_preparation_failure(OTHER_FAILURE))
    assert window._error_headline.isVisible()
    assert "could not prepare this workspace" in window._error_headline.text()
    assert window._error_text.toPlainText() == OTHER_FAILURE


def test_the_error_screen_always_has_a_plain_headline(window):
    window.show_error("Traceback ...")
    assert window._error_headline.isVisible()
    assert window._error_headline.text() == "SciQLop could not start."


def test_the_console_launcher_ends_with_the_explanation(monkeypatch, capsys):
    """The native launcher shows the end of this output: the plain words go last."""
    from SciQLop import sciqlop_launcher

    def _offline(workspace_name, sciqlop_file):
        raise RuntimeError("dns error: failed to lookup address information")

    monkeypatch.setattr(sciqlop_launcher, "_apply_proxy_settings", lambda: None)
    monkeypatch.setattr(sciqlop_launcher, "resolve_workspace_dir", _offline)
    logged = []
    monkeypatch.setattr(sciqlop_launcher, "_append_to_own_log", logged.append)
    exit_code, _ = sciqlop_launcher._run_on_console(None, None)
    assert exit_code == 1
    err = capsys.readouterr().err.strip()
    assert "Traceback" in err
    assert err.endswith(explain_preparation_failure("dns error"))
    assert "could not download" in logged[0]
