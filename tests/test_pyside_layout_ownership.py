"""PYSIDE-3479: PySide6 6.12.0 destroys twice the widgets of a child layout that was filled before it was added."""
from .fixtures import *  # noqa: F401,F403
import pytest
import shiboken6
from PySide6.QtWidgets import QFormLayout, QGridLayout, QHBoxLayout, QPushButton, QVBoxLayout, QWidget


def _filled_row():
    button, row = QPushButton("x"), QHBoxLayout()
    row.addWidget(button)
    return button, row


ATTACHMENTS = {
    "box.addLayout": (QVBoxLayout, lambda outer, row: outer.addLayout(row)),
    "box.insertLayout": (QVBoxLayout, lambda outer, row: outer.insertLayout(0, row)),
    "grid.addLayout": (QGridLayout, lambda outer, row: outer.addLayout(row, 0, 0)),
    "form.addRow": (QFormLayout, lambda outer, row: outer.addRow("label", row)),
    "form.insertRow": (QFormLayout, lambda outer, row: outer.insertRow(0, "label", row)),
}


@pytest.mark.parametrize("attachment", ATTACHMENTS)
def test_the_widgets_of_a_filled_child_layout_belong_to_qt(qapp, qtbot, attachment):
    outer_type, attach = ATTACHMENTS[attachment]
    root = QWidget()
    qtbot.addWidget(root)
    outer = outer_type(root)
    button, row = _filled_row()

    attach(outer, row)

    assert button.parentWidget() is root
    assert not shiboken6.ownedByPython(button)


def test_a_nested_filled_layout_is_covered_too(qapp, qtbot):
    root = QWidget()
    qtbot.addWidget(root)
    outer = QVBoxLayout(root)
    button, inner = _filled_row()
    row = QHBoxLayout()
    row.addLayout(inner)

    outer.addLayout(row)

    assert not shiboken6.ownedByPython(button)
