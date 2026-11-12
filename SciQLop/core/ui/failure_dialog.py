"""One way to tell the user an action failed: a plain sentence, what to try, the raw error under Details."""
import errno
import traceback
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QMessageBox, QWidget

_WHAT_TO_TRY = {
    errno.EACCES: "You are not allowed to write there. Choose another folder.",
    errno.EPERM: "You are not allowed to write there. Choose another folder.",
    errno.EROFS: "That location is read-only. Choose another folder.",
    errno.ENOENT: "The folder does not exist. Choose an existing folder.",
    errno.ENOSPC: "The disk is full. Free some space, or choose another disk.",
    errno.EISDIR: "That name is a folder. Choose a file name.",
}


def what_to_try(exc: BaseException) -> str:
    return _WHAT_TO_TRY.get(getattr(exc, "errno", None), "")


def failure_box(parent: Optional[QWidget], title: str, what_failed: str, exc: BaseException) -> QMessageBox:
    box = QMessageBox(QMessageBox.Icon.Warning, title, what_failed, QMessageBox.StandardButton.Ok, parent)
    box.setInformativeText(what_to_try(exc) or str(exc))
    box.setDetailedText("".join(traceback.format_exception(exc)))
    return box


def confirm_replace(parent: Optional[QWidget], path, what: str) -> bool:
    """True when nothing is in the way, or the user agrees to replace what is."""
    path = Path(path)
    if not path.exists():
        return True
    return QMessageBox.question(
        parent, f"Replace {what}?", f'A {what} named "{path.stem}" already exists. Replace it?',
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes


def show_failure(parent: Optional[QWidget], title: str, what_failed: str, exc: BaseException) -> None:
    failure_box(parent, title, what_failed, exc).exec()
