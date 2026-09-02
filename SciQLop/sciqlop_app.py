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
if platform.system() == 'Linux' and not os.environ.get('SCIQLOP_NATIVE_WAYLAND', ''):
    os.environ['QT_QPA_PLATFORM'] = 'xcb'

print("Forcing TZ to UTC")
os.environ['TZ'] = 'UTC'

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from SciQLop.sciqlop_launcher import EXIT_SWITCH_WORKSPACE, SWITCH_WORKSPACE_FILE


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


def _signal_ready_and_wait_for_splash(timeout: float = 5.0) -> None:
    """Write the ready-file so the launcher knows the main window is built,
    then wait for the launcher to acknowledge (by deleting the file) before
    returning. The acknowledgement means the splash window has been closed,
    so the main window can be shown next without flashing on top of it.

    Falls through after `timeout` seconds so a stuck launcher cannot hang
    SciQLop startup — the worst case is a brief splash/main overlap.
    """
    import time
    ready_path = os.environ.get("SCIQLOP_STARTUP_READY_FILE")
    if not ready_path:
        return
    ready_file = Path(ready_path)
    ready_file.touch()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not ready_file.exists():
            return
        time.sleep(0.05)


def start_sciqlop():
    os.environ['INSIDE_SCIQLOP'] = '1'
    from PySide6 import QtPrintSupport, QtQml

    from SciQLop.core.sciqlop_application import sciqlop_event_loop, sciqlop_app

    print(str(QtPrintSupport) + str(QtQml))

    app = sciqlop_app()
    from SciQLop.components.settings.backend.network import apply_qt_application_proxy
    apply_qt_application_proxy()
    from SciQLop.core import tracing as _tracing
    _tracing.set_thread_name("Qt-Main")
    from SciQLop.components.theming.icons import flush_deferred_icons
    flush_deferred_icons()
    from SciQLop.components.products import register_smart_search_domain
    register_smart_search_domain()
    from SciQLop.components.smart_search import initialize as initialize_smart_search
    initialize_smart_search()
    sciqlop_event_loop()

    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    from SciQLop.components.plugins import load_all, loaded_plugins
    app.processEvents()
    main_windows = SciQLopMainWindow()
    app.processEvents()
    load_all(main_windows)

    from SciQLop.components.command_palette.commands import register_builtin_commands
    register_builtin_commands(app.command_registry)

    from SciQLop.components.command_palette.backend.harvester import harvest_qactions
    harvest_qactions(app.command_registry, main_windows)

    main_windows.push_variables_to_console({"plugins": loaded_plugins})

    app.processEvents()
    _signal_ready_and_wait_for_splash()
    main_windows.show()
    app.processEvents()
    return main_windows

def main():
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    from SciQLop.core.sciqlop_application import sciqlop_event_loop

    loop = sciqlop_event_loop()

    def _run_startup():
        try:
            main_windows = start_sciqlop()
            try:
                main_windows.start()
            except Exception as e:
                print(e)
        except Exception:
            import traceback
            traceback.print_exc(file=sys.stderr)
            app = QApplication.instance()
            if app is not None:
                app._sciqlop_exit_code = 1
            QApplication.exit(1)

    # Deferred via a zero-delay timer scheduled *before* exec() below, rather
    # than called directly here: start_sciqlop() builds the whole MainWindow
    # and loads plugins (pumping Qt events along the way with several
    # app.processEvents() calls). qasync only marks its loop as "the running
    # loop" (asyncio.events._set_running_loop) once run_forever()/
    # run_until_complete() actually runs — i.e. once exec() is reached. A
    # plugin that eagerly schedules an asyncio Task during startup (e.g. an
    # agent backend's load() binding a chat session) used to get that Task's
    # first step dispatched by one of those processEvents() calls while the
    # loop wasn't marked running yet, raising
    # "RuntimeError: <loop> is not the running loop" (silently tolerated on
    # Python 3.13, a hard error on 3.14 — reproduced live on both). Running
    # the whole startup sequence as the first thing Qt dispatches once exec()
    # has genuinely entered its running state fixes the ordering at the root
    # instead of at each individual eager-Task call site.
    QTimer.singleShot(0, _run_startup)
    loop.exec()


if __name__ == '__main__':
    main()
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    exit_code = getattr(app, '_sciqlop_exit_code', 0) if app else 0
    sys.exit(exit_code)
