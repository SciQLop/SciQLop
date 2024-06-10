from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QSizePolicy, QMessageBox, QErrorMessage

from ..backend.sciqlop_logging import _stdout, _stderr
from ..backend.common.terminal_messages import parse_all_sciqlop_message


class LogsWidget(QWidget):
    def __init__(self, parent):
        QWidget.__init__(self, parent)
        self.setWindowTitle("Logs")
        self._dialogs = {}
        self._view = QTextEdit(self)
        _stdout.got_text.connect(self._new_text)
        _stderr.got_text.connect(self._new_text)
        self._last_cursor = self._view.textCursor().position()
        self._last_editing_cursor = self._view.textCursor().position()
        self._view.setReadOnly(True)
        self._view.setLineWrapMode(QTextEdit.NoWrap)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self._view)
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding))
        self.setMinimumHeight(100)

    def _save_cursor(self):
        self._last_cursor = self._view.textCursor().position()

    def _restore_cursor(self):
        cursor = self._view.textCursor()
        cursor.setPosition(self._last_cursor)
        self._view.setTextCursor(cursor)

    def _save_editing_cursor(self):
        self._last_editing_cursor = self._view.textCursor().position()

    def _restore_editing_cursor(self):
        cursor = self._view.textCursor()
        cursor.setPosition(self._last_editing_cursor)
        self._view.setTextCursor(cursor)

    def _handle_message(self, msg_type, action, uuid, title, msg):
        if action == 'dialog':
            if msg_type == 'error':
                QMessageBox.critical(self, title, msg)
            elif msg_type == 'message':
                self._dialogs[uuid] = QMessageBox.information(self, title, msg)
                ##self._dialogs[uuid].exec()
        elif action == 'close':
            if uuid in self._dialogs:
                del self._dialogs[uuid]

    def _parse(self, txt: str):
        self._save_cursor()
        self._restore_editing_cursor()

        for message in parse_all_sciqlop_message(txt):
            self._handle_message(**message)

        if txt.startswith('\r') or txt.startswith('\b'):
            self._view.moveCursor(QTextCursor.MoveOperation.StartOfLine)
            txt = txt[1:]
        if '\b' in txt:
            blocks = txt.split('\b')
            for t in blocks[:-1]:
                self._view.insertPlainText(txt)
                self._view.moveCursor(QTextCursor.MoveOperation.StartOfLine)
            self._view.insertPlainText(blocks[-1])

            if txt.endswith('\b'):
                self._view.moveCursor(QTextCursor.MoveOperation.StartOfLine)
        else:
            self._view.insertPlainText(txt)
        self._save_editing_cursor()
        self._restore_cursor()

    def _new_text(self, msg):
        prev_cursor = self._view.textCursor()
        follow = self._view.verticalScrollBar().value() >= (self._view.verticalScrollBar().maximum() - 4)
        self._view.moveCursor(QTextCursor.MoveOperation.End)
        self._parse(msg)
        if follow:
            self._view.moveCursor(QTextCursor.MoveOperation.End)
        else:
            self._view.setTextCursor(prev_cursor)
