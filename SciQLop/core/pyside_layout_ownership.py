"""PySide6 6.12.0 only: the widgets of a child layout that was filled before it was added to a layout
installed on a widget stay owned by Python while Qt owns them too, so they are destroyed twice.

https://bugreports.qt.io/browse/PYSIDE-3479 (fixed in PySide6 6.12.1): remove this module with 6.12.0.
"""
from functools import wraps

import PySide6
import shiboken6
from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QBoxLayout, QFormLayout, QGridLayout, QWidget

_AFFECTED_VERSION = (6, 12, 0)

_METHODS_ADDING_A_LAYOUT = (
    (QBoxLayout, "addLayout"),
    (QBoxLayout, "insertLayout"),
    (QGridLayout, "addLayout"),
    (QFormLayout, "addRow"),
    (QFormLayout, "insertRow"),
    (QFormLayout, "setLayout"),
)


def _hand_python_owned_children_to_qt(layout):
    parent = layout.parentWidget()
    if parent is None:
        return
    for child in parent.findChildren(QWidget, options=Qt.FindChildOption.FindDirectChildrenOnly):
        if shiboken6.ownedByPython(child):
            # QObject.setParent, not QWidget.setParent: same parent, so Qt does nothing (QWidget's would
            # hide the widget) and PySide records that Qt owns the child.
            QObject.setParent(child, parent)


def _then_hand_children_to_qt(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        result = method(self, *args, **kwargs)
        _hand_python_owned_children_to_qt(self)
        return result

    return wrapper


def install():
    if tuple(PySide6.__version_info__[:3]) != _AFFECTED_VERSION:
        return
    for layout_type, name in _METHODS_ADDING_A_LAYOUT:
        setattr(layout_type, name, _then_hand_children_to_qt(getattr(layout_type, name)))
