"""An install or update failure leads with a plain sentence; the command line is left to the log."""
import pytest

from SciQLop.components.workspaces.backend.uv import error_summary
from SciQLop.components.workspaces.backend.workspace_venv import _uv_failure_message

_CMD = ["/opt/sciqlop/bin/uv", "pip", "install", "--python", "/ws/.venv/bin/python", "some-plugin"]


def _failure(stderr: str) -> Exception:
    return RuntimeError(_uv_failure_message(_CMD, 1, stderr))


@pytest.mark.parametrize("stderr, headline", [
    ("  × No solution found when resolving dependencies:\n  ╰─▶ Because numpy<2 ...",
     "It does not work with the packages already in this workspace."),
    ("error: Failed to fetch: `https://pypi.org/simple/some-plugin/`\n  Caused by: error sending request for url",
     "The package index could not be reached. Check your connection and the proxy in Settings."),
    ("error: dns error: failed to lookup address information",
     "The package index could not be reached. Check your connection and the proxy in Settings."),
    ("  ╰─▶ Because some-plugin was not found in the package registry and you require some-plugin",
     "No such package was found for this platform and Python version."),
    ("error: failed to create file: Permission denied (os error 13)",
     "SciQLop is not allowed to write in this workspace's folder."),
    ("error: No space left on device (os error 28)", "The disk is full."),
])
def test_a_known_failure_leads_with_a_plain_sentence(stderr, headline):
    summary = error_summary(_failure(stderr))
    assert summary.startswith(headline)
    assert stderr.strip() in summary
    assert "uv command failed" not in summary and "/opt/sciqlop/bin/uv" not in summary


def test_an_unknown_failure_keeps_its_reason_without_the_command_line():
    assert error_summary(_failure("error: something new")) == "error: something new"


def test_an_error_that_is_not_from_the_installer_is_kept_as_it_is():
    assert error_summary(RuntimeError("cannot determine package name")) == "cannot determine package name"
