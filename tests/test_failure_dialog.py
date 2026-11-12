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


def test_nothing_in_the_way_needs_no_question(tmp_path, qapp):
    from SciQLop.core.ui.failure_dialog import confirm_replace
    assert confirm_replace(None, tmp_path / "new.json", "template")


@pytest.mark.parametrize("answer, expected", [("Yes", True), ("No", False)])
def test_an_existing_file_is_replaced_only_on_yes(tmp_path, qapp, monkeypatch, answer, expected):
    from PySide6.QtWidgets import QMessageBox
    from SciQLop.core.ui.failure_dialog import confirm_replace
    existing = tmp_path / "mine.json"
    existing.write_text("{}")
    asked = []
    monkeypatch.setattr(QMessageBox, "question",
                        lambda parent, title, text, *a: asked.append(text) or getattr(QMessageBox.StandardButton, answer))
    assert confirm_replace(None, existing, "template") is expected
    assert asked == ['A template named "mine" already exists. Replace it?']
