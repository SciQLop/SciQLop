from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QSizePolicy

from ..backend.sciqlop_logging import _stdout, _stderr


class LogsWidget(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.setWindowTitle("Logs")
        self._view = QTextEdit(self)
        _stdout.got_text.connect(self._new_text)
        _stderr.got_text.connect(self._new_text)
        self._view.setReadOnly(True)
        self._view.setLineWrapMode(QTextEdit.NoWrap)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self._view)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding))
        self.setMinimumHeight(100)

    def _new_text(self, msg):
        prev_cursor = self._view.textCursor()
        follow = self._view.verticalScrollBar().value() >= (self._view.verticalScrollBar().maximum() - 4)
        self._view.moveCursor(QTextCursor.MoveOperation.End)
        self._view.insertPlainText(msg)
        if follow:
            self._view.moveCursor(QTextCursor.MoveOperation.End)
        else:
            self._view.setTextCursor(prev_cursor)
