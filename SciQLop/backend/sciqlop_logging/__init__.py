import logging
import os
import sys
from .logger import Logger
from io import StringIO

INFO = logging.INFO
WARNING = logging.WARNING
DEBUG = logging.DEBUG
ERROR = logging.ERROR


def getLogger(name=None):
    if name:
        return logging.getLogger("SciQLop").getChild(name)
    return logging.getLogger("SciQLop")


_stdout = Logger()
_stderr = Logger()
_stdin = StringIO()


def replace_stdios():
    sys.stdout = _stdout
    sys.stdin = _stdin
    sys.stderr = _stderr


def setup(log_filename=None, log_level=None):
    replace_stdios()
    if log_level is not None:
        getLogger().setLevel(log_level)
    else:
        getLogger().setLevel(os.environ.get('SCIQLOP_LOG_LEVEL', 'INFO'))
    formatter = logging.Formatter('%(asctime)s %(module)-25s %(levelname)-8s %(message)s')
    if log_filename is not None:
        fh = logging.FileHandler(filename=log_filename)
        fh.setFormatter(formatter)
        getLogger().addHandler(fh)
    sh = logging.StreamHandler(stream=sys.stdout)
    sh.setFormatter(formatter)
    getLogger().addHandler(sh)
