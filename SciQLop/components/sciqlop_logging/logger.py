from PySide6.QtCore import QObject, Signal, Slot, Qt
import logging
import os
from typing import AnyStr, Union
from inspect import getframeinfo, stack

from .formatter import SciQlopFormatter

if 'SCIQLOP_DEBUG' in os.environ:
    __default_log_level__ = logging.DEBUG
    print("Setting log level to DEBUG")
else:
    __default_log_level__ = os.environ.get('SCIQLOP_LOG_LEVEL', 'INFO')


def is_debug_mode() -> bool:
    return 'SCIQLOP_DEBUG' in os.environ


class _Logger(QObject):
    new_line = Signal(str)

    def __init__(self, parent=None):
        QObject.__init__(self, parent)
        self.buffer = ""

    @Slot(str)
    def write(self, msg):
        self.buffer += msg
        lines = self.buffer.splitlines(keepends=True)
        if len(lines) > 1:
            self.buffer = lines[-1]
            for line in lines[:-1]:
                self.new_line.emit(line)
        return len(msg)

    def flush(self):
        pass

    def read(self, size=-1):
        pass


_stdout = _Logger()


def listen_sciqlop_logger(callback):
    _stdout.new_line.connect(callback)


class SciQLopLogger(QObject):
    push_log = Signal(str)

    def __init__(self, module, parent=None):
        super().__init__(parent)
        self._level = __default_log_level__
        self._module = module
        self._formater = SciQlopFormatter()

    @property
    def level(self):
        return self._level

    @level.setter
    def level(self, value):
        if isinstance(value, str):
            self._level = getattr(logging, value)
        else:
            self._level = value

    @property
    def module(self):
        return self._module

    def debug(self, msg, *args, **kwargs):
        if self._level <= logging.DEBUG:
            self.log(logging.DEBUG, msg, *args, **kwargs)

    def info(self, msg, *args, **kwargs):
        if self._level <= logging.INFO:
            self.log(logging.INFO, msg, *args, **kwargs)

    def warning(self, msg, *args, **kwargs):
        if self._level <= logging.WARNING:
            self.log(logging.WARNING, msg, *args, **kwargs)

    def error(self, msg, *args, **kwargs):
        if self._level <= logging.ERROR:
            self.log(logging.ERROR, msg, *args, **kwargs)

    def critical(self, msg, *args, **kwargs):
        if self._level <= logging.CRITICAL:
            self.log(logging.CRITICAL, msg, *args, **kwargs)

    def log(self, level, msg, *args, **kwargs):
        for i in range(3):
            caller = getframeinfo(stack()[i][0])
            if caller.filename != __file__:
                break
        lineno = caller.lineno
        filename = caller.filename
        self.push_log.emit(
            self._formater.format(
                logging.makeLogRecord(
                    {
                        "msg": msg, "args": args, "kwargs": kwargs, "levelno": level,
                        "levelname": logging.getLevelName(level),
                        "module": self._module, "filename": filename, "lineno": lineno
                    }
                )
            ) + "\n"
        )


__Loggers__ = {}


def set_log_level(logger: SciQLopLogger, level: Union[AnyStr, int]):
    print(f"Setting log level to {level} for {logger}")
    logger.level = level
    if logger.module == "SciQLop":
        global __default_log_level__
        __default_log_level__ = level
    print(f"logger level is {logger.level}")


def getLogger(name="SciQLop"):
    global __default_log_level__  # noqa: F824
    global __Loggers__  # noqa: F824
    if name in __Loggers__:
        return __Loggers__[name]
    logger = SciQLopLogger(name)
    logger.push_log.connect(_stdout.write, type=Qt.QueuedConnection)
    logger.level = __default_log_level__
    __Loggers__[name] = logger
    return logger
