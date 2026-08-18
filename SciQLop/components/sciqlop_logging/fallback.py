"""Plain stdlib logging, used when Qt is not installed.

The Qt logger exists to feed the in-app log dock through signals. A thin
(``pip install sciqlop``) install has no GUI and nothing to feed, so the
launcher gets ordinary loggers writing to stderr instead.
"""

import logging
import os
from typing import AnyStr, Union

from .formatter import SciQlopFormatter

SciQLopLogger = logging.Logger


def is_debug_mode() -> bool:
    return 'SCIQLOP_DEBUG' in os.environ


def _default_level() -> Union[AnyStr, int]:
    if is_debug_mode():
        return logging.DEBUG
    return os.environ.get('SCIQLOP_LOG_LEVEL', 'INFO')


def listen_sciqlop_logger(callback):
    """No-op: there is no log dock to forward lines to without Qt."""


def set_log_level(logger: logging.Logger, level: Union[AnyStr, int]):
    logger.setLevel(level)


def getLogger(name="SciQLop") -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(SciQlopFormatter())
        logger.addHandler(handler)
        logger.setLevel(_default_level())
    return logger
