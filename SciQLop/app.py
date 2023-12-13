import os
import platform
import sys
from io import StringIO

os.environ['QT_API'] = 'PySide6'
print("Forcing TZ to UTC")
os.environ['TZ'] = 'UTC'
if platform.system() == 'Linux':
    os.environ['QT_QPA_PLATFORM'] = os.environ.get("SCIQLOP_QT_QPA_PLATFORM", 'xcb')

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)) + '/..'))


def main():
    from PySide6 import QtWidgets, QtPrintSupport, QtOpenGL, QtQml, QtCore, QtGui
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
    import PySide6QtAds
    from SciQLop.resources import icons
    from SciQLop.backend.sciqlop_application import SciQLopApp

    print(str(icons) + str(QtPrintSupport) + str(QtOpenGL) + str(QtQml) + str(PySide6QtAds))

    app = SciQLopApp(sys.argv)
    pixmap = QtGui.QPixmap(":/splash.png")
    splash = QtWidgets.QSplashScreen(pixmap)
    splash.show()
    app.processEvents()
    splash.showMessage("Loading SciQLop...")
    app.processEvents()

    from SciQLop.widgets.mainwindow import SciQLopMainWindow
    from SciQLop.plugins import load_all, loaded_plugins
    app.processEvents()
    main_windows = SciQLopMainWindow(app)
    main_windows.show()
    app.processEvents()
    load_all(main_windows)
    main_windows.push_variables_to_console({"plugins": loaded_plugins})
    app.processEvents()
    splash.finish(main_windows)
    main_windows.start()


if __name__ == '__main__':
    main()
