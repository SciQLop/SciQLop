from .fixtures import *
import pytest
from pytestqt import qt_compat
from pytestqt.qt_compat import qt_api
from PySide6.QtWidgets import QTreeView
from PySide6.QtCore import  Qt, QEvent, QVariantAnimation, QCoreApplication, QPoint, QTimer
from PySide6.QtGui import QMouseEvent, QCursor
from PySide6.QtWidgets import QWidget


def mouseMove(qapp, widget, pos, button=Qt.MouseButton.NoButton):
    QCursor.setPos(widget.mapToGlobal(pos))
    event = QMouseEvent(
        QEvent.Type.MouseMove,
        pos,
        Qt.MouseButton.NoButton,
        button,
        Qt.NoModifier,
    )
    if hasattr(widget, 'viewport') and isinstance(widget, QWidget):
        qapp.sendEvent(widget.viewport(), event)
    else:
        qapp.sendEvent(widget, event)
    qapp.processEvents()


def drag_and_drop(qapp, qtbot, source_widget, item, target_widget):
    item_center = source_widget.visualRect(item).center()
    if hasattr(source_widget, 'viewport'):
        qtbot.mousePress(source_widget.viewport(), Qt.MouseButton.LeftButton, pos=item_center)
    else:
        qtbot.mousePress(source_widget, Qt.MouseButton.LeftButton, pos=item_center)
    qtbot.wait(1)
    mouseMove(qapp, source_widget, item_center, Qt.MouseButton.LeftButton)
    item_center += QPoint(0,-10)
    def _move():
        mouseMove(qapp, target_widget, target_widget.rect().topLeft(), Qt.MouseButton.LeftButton)
        mouseMove(qapp, target_widget, target_widget.rect().center(), Qt.MouseButton.LeftButton)
        if hasattr(target_widget, 'viewport'):
            qtbot.mouseRelease(target_widget.viewport(), Qt.MouseButton.LeftButton)
        else:
            qtbot.mouseRelease(target_widget, Qt.MouseButton.LeftButton)
    QTimer.singleShot(1, _move)
    mouseMove(qapp, source_widget, item_center, Qt.MouseButton.LeftButton)
    for i in range(10):
        qtbot.wait(1)
