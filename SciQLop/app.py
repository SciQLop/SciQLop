import platform
import os
import sys

os.environ['QT_API'] = 'PySide6'
print("Forcing TZ to UTC")
os.environ['TZ'] = 'UTC'
if platform.system() == 'Linux':
    os.environ['QT_QPA_PLATFORM'] = 'xcb'


def main():
    from PySide6 import QtWidgets
    from SciQLop.widgets.mainwindow import SciQLopMainWindow
    from SciQLop.plugins import load_all

    class SciQLopApp(QtWidgets.QApplication):
        def __init__(self, args):
            super(SciQLopApp, self).__init__(args)
            self.setOrganizationName("LPP")
            self.setOrganizationDomain("lpp.fr")
            self.setApplicationName("SciQLop")

    app = SciQLopApp(sys.argv)
    w = SciQLopMainWindow()
    w.show()
    p = load_all(w)
    app.exec()


if __name__ == '__main__':
    main()
