from PySide6 import QtWidgets
from SciQLop.widgets.mainwindow import SciQLopMainWindow
from SciQLop.plugins import load_all
import os
import sys
os.environ['QT_API'] = 'PySide6'


class SciQLopApp(QtWidgets.QApplication):
    def __init__(self, args):
        super(SciQLopApp, self).__init__(args)
        self.setOrganizationName("LPP")
        self.setOrganizationDomain("lpp.fr")
        self.setApplicationName("SciQLop")


if __name__ == '__main__':
    app = SciQLopApp(sys.argv)
    w = SciQLopMainWindow()
    w.show()
    p=load_all(w)
    app.exec()
