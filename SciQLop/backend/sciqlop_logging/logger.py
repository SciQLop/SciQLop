from PySide6.QtCore import QObject, Signal
from datetime import datetime


class Logger(QObject):
    new_line = Signal(str)
    got_text = Signal(str)

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self.buffer = ""

    def write(self, msg):
        self.got_text.emit(msg)
        self.buffer += msg
        lines = self.buffer.splitlines()
        if len(lines) > 1:
            self.buffer = lines[-1]
            for line in lines[:-1]:
                self.new_line.emit(line)
        return len(msg)

    def flush(self):
        pass

    def read(self, size=-1):
        pass
