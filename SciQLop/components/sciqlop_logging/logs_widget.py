import re

from PySide6.QtWidgets import QSizePolicy, QMessageBox
from qtconsole.rich_jupyter_widget import RichJupyterWidget

from SciQLop.components.sciqlop_logging import is_debug_mode, listen_sciqlop_logger
from SciQLop.core.common.terminal_messages import parse_all_sciqlop_message

_STYLE = """
    QPlainTextEdit, QTextEdit {
        background-color: palette(base);
        background-clip: padding;
        color: palette(text);
        selection-background-color: palette(highlight);
    }
"""

_LEVELS = "DEBUG|INFO|WARNING|ERROR|CRITICAL"
_DARK_BAND = ";48;5;236"
_INFO_YELLOW = "\x1b[38;5;220m"
_LOG_LINE = re.compile(rf" ({_LEVELS})\s+- \1 - ")
_REPEATED_LEVEL = re.compile(rf" - ({_LEVELS}) -")
_SOURCE = re.compile(r" \([^()\n]*:\d+\)(?=(\x1b\[0m)?\s*$)")


def for_display(line: str, debug: bool) -> str:
    """A log line as the pane shows it. The formatter writes for a dark
    terminal and for the session log file; here the theme gives the colours,
    and the source file is noise unless someone is debugging."""
    if not _LOG_LINE.search(line):
        return line
    line = line.replace(_DARK_BAND, "")
    if line.startswith(_INFO_YELLOW):
        line = line.removeprefix(_INFO_YELLOW).replace("\x1b[0m", "")
    line = _REPEATED_LEVEL.sub("", line, count=1)
    return line if debug else _SOURCE.sub("", line)


class LogsWidget(RichJupyterWidget):
    def __init__(self, parent):
        RichJupyterWidget.__init__(self, parent)
        self.setWindowTitle("Logs")
        self._dialogs = {}
        self.style_sheet = _STYLE
        listen_sciqlop_logger(self._new_text)

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
        self.append_stream(for_display(msg, is_debug_mode()))
