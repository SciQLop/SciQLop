from .fixtures import *
import pytest
from pytestqt import qt_compat
from pytestqt.qt_compat import qt_api
from PySide6.QtWidgets import QTreeView
from PySide6.QtCore import Qt, QEvent, QVariantAnimation, QCoreApplication, QPoint, QTimer
from PySide6.QtGui import QMouseEvent, QCursor
from PySide6.QtWidgets import QWidget


def mouseMove(qapp, widget, pos, button: Qt.MouseButton = Qt.MouseButton.NoButton):
    QCursor.setPos(widget.mapToGlobal(pos))
    event = QMouseEvent(
        QEvent.Type.MouseMove,
        pos,
        Qt.MouseButton.NoButton,
        button,
        Qt.KeyboardModifier.NoModifier,
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
    item_center += QPoint(0, -10)

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


def restore_extension_points(saved: dict) -> None:
    """Puts back the registry saved before a test, but keeps the core points declared meanwhile: a core module
    declares its point once, at its first import, so dropping that point breaks every later test."""
    from SciQLop.core import extensions
    core = {ep_id: ep for ep_id, ep in extensions._EXTENSION_POINTS.items() if ep_id.startswith("sciqlop.")}
    extensions._EXTENSION_POINTS.clear()
    extensions._EXTENSION_POINTS.update({**core, **saved})


def call_from_worker_thread(qtbot, monkeypatch, fn):
    """Run fn on a plain Python thread, as a notebook cell or an agent tool would, with the cross-thread
    invoker the kernel normally installs; the main thread keeps processing events meanwhile."""
    import threading
    from jupyqt.qt.proxy import MainThreadInvoker
    from SciQLop.user_api import threading as sciqlop_threading
    monkeypatch.setattr(sciqlop_threading, "_invoker", MainThreadInvoker())
    outcome = {}

    def run():
        try:
            outcome["result"] = fn()
        except BaseException as error:
            outcome["error"] = error

    worker = threading.Thread(target=run)
    worker.start()
    qtbot.waitUntil(lambda: not worker.is_alive(), timeout=10_000)
    if "error" in outcome:
        raise outcome["error"]
    return outcome.get("result")
