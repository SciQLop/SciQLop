from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QSizePolicy, QMessageBox, QErrorMessage
from qtconsole.rich_jupyter_widget import RichJupyterWidget

from ..backend.sciqlop_logging import _stdout, _stderr
from ..backend.common.terminal_messages import parse_all_sciqlop_message



class LogsWidget(RichJupyterWidget):
    def __init__(self, parent):
        RichJupyterWidget.__init__(self, parent)
        self.setWindowTitle("Logs")
        self._dialogs = {}

        _stdout.got_text.connect(self._new_text)
        _stderr.got_text.connect(self._new_text)

        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.MinimumExpanding))
        self.setMinimumHeight(100)

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

    def _new_text(self, msg):
        for message in parse_all_sciqlop_message(msg):
            self._handle_message(**message)
        self.append_stream(msg)
