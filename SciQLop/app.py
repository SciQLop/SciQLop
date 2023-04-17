import os
import platform
import sys

os.environ['QT_API'] = 'PySide6'
print("Forcing TZ to UTC")
os.environ['TZ'] = 'UTC'
if platform.system() == 'Linux':
    os.environ['QT_QPA_PLATFORM'] = os.environ.get("SCIQLOP_QT_QPA_PLATFORM", 'xcb')

_STYLE_SHEET_ = """
QWidget:focus { border: 1px dashed light blue }
"""


def main():
    from PySide6 import QtWidgets, QtPrintSupport, QtOpenGL, QtQml
    import PySide6QtAds
    from SciQLop.widgets.mainwindow import SciQLopMainWindow
    from SciQLop.plugins import load_all, loaded_plugins
    from SciQLop.resources import icons
    from SciQLop.backend import logging
    logging.setup()
    logging.getLogger().info(str(icons) + str(QtPrintSupport) + str(QtOpenGL) + str(QtQml) + str(PySide6QtAds))

    class SciQLopApp(QtWidgets.QApplication):
        def __init__(self, args):
            super(SciQLopApp, self).__init__(args)
            self.setOrganizationName("LPP")
            self.setOrganizationDomain("lpp.fr")
            self.setApplicationName("SciQLop")
            self.setStyleSheet(_STYLE_SHEET_)

    app = SciQLopApp(sys.argv)
    w = SciQLopMainWindow()
    w.show()
    w.push_variables_to_console({"plugins": loaded_plugins})
    p = load_all(w)
    app.exec()


if __name__ == '__main__':
    main()
