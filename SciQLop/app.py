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
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts)
    import PySide6QtAds

    from SciQLop.resources import icons
    from SciQLop.backend.sciqlop_application import sciqlop_event_loop, sciqlop_app

    print(str(icons) + str(QtPrintSupport) + str(QtOpenGL) + str(QtQml) + str(PySide6QtAds))

    app = sciqlop_app()
    envent_loop = sciqlop_event_loop()
    pixmap = QtGui.QPixmap(":/splash.png")
    splash = QtWidgets.QSplashScreen(pixmap)
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
    main_windows.start()


if __name__ == '__main__':
    main()

if os.environ.get("INSIDE_SCIQLOP", None) is None:
    # faking imports to make pyinstaller happy
    from markupsafe import Markup  # noqa: F401
    from jupyterlab import labapp  # noqa: F401
    from qtconsole import qtconsoleapp  # noqa: F401
    import jinja2  # noqa: F401
    import markupsafe  # noqa: F401
    import jupyter_events  # noqa: F401
