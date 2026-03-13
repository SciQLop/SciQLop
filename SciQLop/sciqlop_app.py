import os
import platform
import sys
from pathlib import Path

if platform.system() == 'Windows':
    import matplotlib.pyplot as plt

    plt.ion()

else:
    os.environ['QT_API'] = 'PySide6'  # breaks ipython kernel event loop on windows

print("Forcing TZ to UTC")
os.environ['TZ'] = 'UTC'
if platform.system() == 'Linux':
    os.environ['QT_QPA_PLATFORM'] = os.environ.get("SCIQLOP_QT_QPA_PLATFORM", 'xcb')
    print(f"Setting QT_QPA_PLATFORM to {os.environ['QT_QPA_PLATFORM']}")

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)) + '/..'))


EXIT_SWITCH_WORKSPACE = 65
SWITCH_WORKSPACE_FILE = ".sciqlop_switch_target"


def switch_workspace(workspace_name: str) -> None:
    """Signal the launcher to restart with a different workspace.

    Writes the target workspace name to a file in the current workspace dir
    (from SCIQLOP_WORKSPACE_DIR env var), then exits with code 65 so the
    launcher restarts into the target workspace.
    """
    ws_dir = os.environ.get("SCIQLOP_WORKSPACE_DIR", ".")
    (Path(ws_dir) / SWITCH_WORKSPACE_FILE).write_text(workspace_name)
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    app._sciqlop_exit_code = EXIT_SWITCH_WORKSPACE
    QApplication.exit(EXIT_SWITCH_WORKSPACE)


def start_sciqlop():
    os.environ['INSIDE_SCIQLOP'] = '1'
    from PySide6 import QtPrintSupport, QtOpenGL, QtQml, QtCore
    from PySide6.QtGui import QPixmap
    from PySide6.QtWidgets import QSplashScreen
    # import PySide6QtAds

    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseDesktopOpenGL, True)
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_ShareOpenGLContexts, True)

    from SciQLop.core.sciqlop_application import sciqlop_event_loop, sciqlop_app
    from SciQLop.resources import qInitResources

    print(str(QtPrintSupport) + str(QtOpenGL) + str(QtQml))

    app = sciqlop_app()
    qInitResources()
    from SciQLop.components.theming.icons import flush_deferred_icons
    flush_deferred_icons()
    envent_loop = sciqlop_event_loop()
    pixmap = QPixmap(":/splash.png")
    splash = QSplashScreen(pixmap)
    splash.show()
    app.processEvents()
    splash.showMessage("Loading SciQLop...")
    app.processEvents()

    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    from SciQLop.components.plugins import load_all, loaded_plugins
    app.processEvents()
    main_windows = SciQLopMainWindow()

    main_windows.show()
    app.processEvents()
    load_all(main_windows)

    from SciQLop.components.command_palette.commands import register_builtin_commands
    register_builtin_commands(app.command_registry)

    from SciQLop.components.command_palette.backend.harvester import harvest_qactions
    harvest_qactions(app.command_registry, main_windows)

    main_windows.push_variables_to_console({"plugins": loaded_plugins})

    app.processEvents()
    splash.finish(main_windows)
    return main_windows

def main():
    main_windows = start_sciqlop()
    try:
        main_windows.start()
    except Exception as e:
        print(e)


if __name__ == '__main__':
    main()
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    exit_code = getattr(app, '_sciqlop_exit_code', 0) if app else 0
    if os.environ.get("RESTART_SCIQLOP", None) is not None:
        exit_code = 64
    sys.exit(exit_code)
