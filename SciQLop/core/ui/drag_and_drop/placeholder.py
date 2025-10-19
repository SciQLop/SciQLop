from PySide6.QtCore import Signal, QMimeData
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QDropEvent, QDragEnterEvent, QDragMoveEvent, QDragLeaveEvent
from enum import Enum


class PlaceHolderPosition(Enum):
    NONE = 0
    TOP = 1
    BOTTOM = 2


class PlaceHolder(QWidget):
    gotDrop = Signal(QMimeData)
    closed = Signal()

    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)
        self.setAcceptDrops(True)
        self.setStyleSheet("background-color: #BBD5EE; border: 1px solid #2A7FD4")

    def leave(self):
        parent = self.parentWidget()
        layout = parent.layout()
        layout.removeWidget(self)
        self.deleteLater()
        self.closed.emit()

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        event.acceptProposedAction()

    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        event.accept()
        self.leave()

    def dropEvent(self, event: QDropEvent) -> None:
        self.gotDrop.emit(event.mimeData())
