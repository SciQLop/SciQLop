import os
import platform
import sys
from pathlib import Path

if platform.system() == 'Windows':
    import matplotlib.pyplot as plt

    plt.ion()

else:
    os.environ['QT_API'] = 'PySide6'  # breaks ipython kernel event loop on windows

# QtADS drag-and-drop relies on QCursor::pos() which returns garbage on
# native Wayland.  Force XCB (XWayland) unless the user explicitly opts in
# to native Wayland via SCIQLOP_NATIVE_WAYLAND=1.
if 'WAYLAND_DISPLAY' in os.environ and 'QT_QPA_PLATFORM' not in os.environ:
    if not os.environ.get('SCIQLOP_NATIVE_WAYLAND', ''):
        os.environ['QT_QPA_PLATFORM'] = 'xcb'

print("Forcing TZ to UTC")
os.environ['TZ'] = 'UTC'

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


EXIT_SWITCH_WORKSPACE = 65
SWITCH_WORKSPACE_FILE = ".sciqlop_switch_target"


def switch_workspace(workspace_name: str) -> None:
    """Signal the launcher to restart with a different workspace.

    Writes the target workspace name to a file in the current workspace dir
    (from SCIQLOP_WORKSPACE_DIR env var), then exits with code 65 so the
    launcher restarts into the target workspace.
    """
    ws_dir = Path(os.environ.get("SCIQLOP_WORKSPACE_DIR", "."))
    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / SWITCH_WORKSPACE_FILE).write_text(workspace_name)
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    app._sciqlop_exit_code = EXIT_SWITCH_WORKSPACE
    QApplication.exit(EXIT_SWITCH_WORKSPACE)


def _signal_ready() -> None:
    """Write the ready-file so the launcher knows the main window is up."""
    ready_path = os.environ.get("SCIQLOP_STARTUP_READY_FILE")
    if ready_path:
        Path(ready_path).touch()


def start_sciqlop():
    os.environ['INSIDE_SCIQLOP'] = '1'
    from PySide6 import QtPrintSupport, QtQml

    from SciQLop.core.sciqlop_application import sciqlop_event_loop, sciqlop_app
    from SciQLop.resources import qInitResources

    print(str(QtPrintSupport) + str(QtQml))

    app = sciqlop_app()
    qInitResources()
    from SciQLop.components.theming.icons import flush_deferred_icons
    flush_deferred_icons()
    sciqlop_event_loop()

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
    _signal_ready()
    return main_windows

def main():
    main_windows = start_sciqlop()
    try:
        main_windows.start()
    except Exception as e:
        print(e)
    from SciQLop.core.sciqlop_application import sciqlop_event_loop
    sciqlop_event_loop().exec()


if __name__ == '__main__':
    main()
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    exit_code = getattr(app, '_sciqlop_exit_code', 0) if app else 0
    if os.environ.get("RESTART_SCIQLOP", None) is not None:
        exit_code = 64
    sys.exit(exit_code)
