"""A failed action is told in one plain sentence, with what to try; the raw error is under Details."""
import errno

import pytest

from .fixtures import qapp_cls  # noqa: F401 — fixture
from SciQLop.core.ui.failure_dialog import failure_box, what_to_try


@pytest.mark.parametrize("exc, expected", [
    (PermissionError(errno.EACCES, "Permission denied", "/root/x.png"), "not allowed to write"),
    (FileNotFoundError(errno.ENOENT, "No such file or directory", "/nope/x.png"), "folder does not exist"),
    (OSError(errno.ENOSPC, "No space left on device"), "disk is full"),
    (IsADirectoryError(errno.EISDIR, "Is a directory", "/tmp"), "is a folder"),
])
def test_common_file_errors_say_what_to_try(exc, expected):
    assert expected in what_to_try(exc)


def test_an_unknown_error_gives_no_advice():
    assert what_to_try(ValueError("weird")) == ""


def test_the_box_leads_with_the_sentence_and_keeps_the_error_under_details(qapp):
    try:
        raise PermissionError(errno.EACCES, "Permission denied", "/root/x.png")
    except PermissionError as e:
        box = failure_box(None, "Export failed", "Could not export the panel to /root/x.png.", e)
    assert box.text() == "Could not export the panel to /root/x.png."
    assert "not allowed to write" in box.informativeText()
    assert "PermissionError" in box.detailedText() and "Traceback" in box.detailedText()
    box.deleteLater()
