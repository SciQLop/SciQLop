import logging
import sys

INFO = logging.INFO
WARNING = logging.WARNING
DEBUG = logging.DEBUG
ERROR = logging.ERROR


def getLogger(name=None):
    if name:
        return logging.getLogger("SciQLop").getChild(name)
    return logging.getLogger("SciQLop")


def setup(log_filename=None, log_level=logging.INFO):
    getLogger().setLevel(log_level)
    formatter = logging.Formatter('%(asctime)s %(module)-25s %(levelname)-8s %(message)s')
    if log_filename is not None:
        fh = logging.FileHandler(filename=log_filename)
        fh.setFormatter(formatter)
        getLogger().addHandler(fh)
    sh = logging.StreamHandler(stream=sys.stdout)
    sh.setFormatter(formatter)
    getLogger().addHandler(sh)
