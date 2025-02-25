import logging
import os
import sys
from typing import AnyStr, Union

from .logger import Logger
from io import StringIO

INFO = logging.INFO
WARNING = logging.WARNING
DEBUG = logging.DEBUG
ERROR = logging.ERROR


def getLogger(name="SciQLop"):
    """
    Get a SciQLop logger, with the given name. By default, returns the root logger "SciQLop". Automatically enables the logger if it was disabled.
    :param name: The name of the logger to get. Use module name for best results. Default is "SciQLop".
    :return: The logger.
    """
    l = logging.getLogger(name)
    l.disabled = False
    return l


def enable_logger_and_children(logger: logging.Logger):
    logger.disabled = False
    for child in logger.getChildren():
        enable_logger_and_children(child)


_stdout = Logger()
_stderr = Logger()
_stdin = StringIO()


def replace_stdios():
    sys.stdout = _stdout
    sys.stdin = _stdin
    sys.stderr = _stderr


def set_log_level(logger: logging.Logger, level: Union[AnyStr, int]):
    print(f"Setting log level to {level} for {logger}")
    logger.setLevel(level)
    print(f"logger level is {logger.level}")
    for child in getLogger().getChildren():
        set_log_level(child, level)

#taken from https://stackoverflow.com/questions/384076/how-can-i-color-python-logging-output
class SciQlopFormatter(logging.Formatter):
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "%(asctime)s %(module)-25s %(levelname)-8s - %(levelname)s - %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: grey + format + reset,
        logging.INFO: grey + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


def setup(log_filename=None, log_level=None, capture_stdout=True):
    if capture_stdout:
        replace_stdios()
    if 'SCIQLOP_DEBUG' in os.environ:
        set_log_level(getLogger(), logging.DEBUG)
    elif log_level is not None:
        set_log_level(getLogger(), log_level)
    else:
        set_log_level(getLogger(), os.environ.get('SCIQLOP_LOG_LEVEL', 'INFO'))
    formatter = SciQlopFormatter()
    if log_filename is not None:
        fh = logging.FileHandler(filename=log_filename)
        fh.setFormatter(formatter)
        getLogger().addHandler(fh)
    sh = logging.StreamHandler(stream=_stdout)
    sh.setFormatter(formatter)
    getLogger().addHandler(sh)
    enable_logger_and_children(getLogger())
