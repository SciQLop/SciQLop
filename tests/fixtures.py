import os
import pytest
from typing import Tuple


@pytest.fixture(scope="session")
def qapp_cls():
    from SciQLop.core.sciqlop_application import SciQLopApp
    return SciQLopApp


@pytest.fixture(scope="session")
def sciqlop_resources(qapp):
    """One-time session setup: icons, event loop."""
    from concurrent.futures import ThreadPoolExecutor
    from SciQLop.components.theming.icons import flush_deferred_icons
    from SciQLop.core.sciqlop_application import sciqlop_event_loop

    flush_deferred_icons()
    loop = sciqlop_event_loop()
    # qasync's lazily-created default executor runs on QThreads it only stops
    # in loop.close(), which tests never reach: the interpreter then aborts
    # with "QThread: Destroyed while thread is still running" after an
    # otherwise green run. Python threads shut down cleanly instead.
    executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="sciqlop-test-executor")
    loop.set_default_executor(executor)
    yield
    executor.shutdown(wait=True)


_shared_main_window = []


def _build_main_window(qapp):
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    from SciQLop.components.plugins import load_all, loaded_plugins
    from SciQLop.components.command_palette.commands import register_builtin_commands
    from SciQLop.components.command_palette.backend.harvester import harvest_qactions

    mw = SciQLopMainWindow()
    mw.show()
    qapp.processEvents()
    load_all(mw)
    register_builtin_commands(qapp.command_registry)
    harvest_qactions(qapp.command_registry, mw)
    mw.push_variables_to_console({"plugins": loaded_plugins})
    qapp.processEvents()
    return mw


@pytest.fixture(scope="session")
def main_window(qapp, sciqlop_resources):
    """One main window with plugins loaded per process.

    Test modules pull this in with `from .fixtures import *`, and pytest
    registers every imported copy as its own fixture -- so without the shared
    cache each of ~70 modules built its own ~1GB window that lived until the
    end of the run.
    """
    creator = not _shared_main_window
    if creator:
        _shared_main_window.append(_build_main_window(qapp))
    yield _shared_main_window[0]
    if creator:
        _shared_main_window[0].hide()
        for cmd in list(qapp.command_registry.commands()):
            qapp.command_registry.unregister(cmd.id)
        qapp.processEvents()


def destroy_main_window(mw):
    """close() only hides a window, so its ~1GB widget tree stays alive; and it
    runs closeEvent, whose unsaved-catalogs QMessageBox blocks a headless run
    forever. hide() + deleteLater() frees it without either."""
    import gc
    from PySide6 import QtCore, QtWidgets
    mw.hide()
    mw.deleteLater()
    QtCore.QCoreApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    QtWidgets.QApplication.processEvents()
    gc.collect()


@pytest.fixture(scope="function")
def test_plugin(qtbot, qapp, main_window):
    from SciQLop.components.plugins.backend.loader import load_plugin, plugins_folders
    p = load_plugin(plugins_folders()[0], "test_plugin", main_window)
    qtbot.wait(1)
    return p


@pytest.fixture(scope="function")
def simple_vp_callback():
    import numpy as np

    def callback(start: float, end: float) -> Tuple[np.ndarray, np.ndarray]:
        x = np.linspace(start, end, int(end - start))
        y = np.sin(x)
        return x, y

    return callback


@pytest.fixture(scope="function")
def plot_panel(main_window):
    from SciQLop.user_api.plot import create_plot_panel
    return create_plot_panel()
