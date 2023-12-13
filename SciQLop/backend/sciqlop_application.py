from PySide6 import QtWidgets, QtPrintSupport, QtOpenGL, QtQml, QtCore, QtGui

import sys
from io import StringIO

_STYLE_SHEET_ = """
QWidget:focus { border: 1px dashed light blue }
"""


class SciQLopApp(QtWidgets.QApplication):
    def __init__(self, args):
        from . import sciqlop_logging
        super(SciQLopApp, self).__init__(args)
        self.setOrganizationName("LPP")
        self.setOrganizationDomain("lpp.fr")
        self.setApplicationName("SciQLop")
        self.setStyleSheet(_STYLE_SHEET_)
        sciqlop_logging.setup()
