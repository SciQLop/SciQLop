import os
import platform
import sys

if platform.system() == 'Windows':
    import matplotlib.pyplot as plt

    plt.ion()

else:
    os.environ['QT_API'] = 'PySide6'  # breaks ipython kernel event loop on windows

print("Forcing TZ to UTC")
os.environ['TZ'] = 'UTC'
if platform.system() == 'Linux':
    os.environ['QT_QPA_PLATFORM'] = os.environ.get("SCIQLOP_QT_QPA_PLATFORM", 'xcb')

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)) + '/..'))


def main():
    os.environ['INSIDE_SCIQLOP'] = '1'
    from PySide6 import QtWidgets, QtPrintSupport, QtOpenGL, QtQml, QtCore, QtGui
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QSplashScreen
    from shiboken6 import isValid
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
    # import PySide6QtAds

    from SciQLop.resources import icons
    from SciQLop.backend.sciqlop_application import sciqlop_event_loop, sciqlop_app

    print(str(icons) + str(QtPrintSupport) + str(QtOpenGL) + str(QtQml))

    app = sciqlop_app()
    envent_loop = sciqlop_event_loop()
    pixmap = QPixmap(":/splash.png")
    splash = QSplashScreen(pixmap)
    splash.show()
    app.processEvents()
    splash.showMessage("Loading SciQLop...")
    app.processEvents()

    from SciQLop.widgets.mainwindow import SciQLopMainWindow
    from SciQLop.plugins import load_all, loaded_plugins
    app.processEvents()
    main_windows = SciQLopMainWindow()

    main_windows.show()
    app.processEvents()
    load_all(main_windows)
    main_windows.push_variables_to_console({"plugins": loaded_plugins})
    app.processEvents()
    splash.finish(main_windows)
    try:
        main_windows.start()
    except Exception as e:
        print(e)


if __name__ == '__main__':
    main()
    if os.environ.get("RESTART_SCIQLOP", None) is not None:
        sys.exit(64)
    sys.exit(1)
