import logging
import os
from .logger import  SciQLopLogger, listen_sciqlop_logger, set_log_level, getLogger


INFO = logging.INFO
WARNING = logging.WARNING
DEBUG = logging.DEBUG
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL



def setup(log_filename=None, log_level=None, capture_stdout=True):
    if log_level is not None:
        set_log_level(getLogger(), log_level)
