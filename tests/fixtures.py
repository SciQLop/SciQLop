import os
import pytest
from typing import Tuple


@pytest.fixture(scope="session")
def qapp_cls():
    from SciQLop.core.sciqlop_application import SciQLopApp
    return SciQLopApp


@pytest.fixture(scope="session")
def sciqlop_resources(qapp):
    """One-time session setup: Qt resources, icons, event loop."""
    from SciQLop.resources import qInitResources
    from SciQLop.components.theming.icons import flush_deferred_icons
    from SciQLop.core.sciqlop_application import sciqlop_event_loop

    qInitResources()
    flush_deferred_icons()
    sciqlop_event_loop()


@pytest.fixture(scope="module")
def main_window(qapp, sciqlop_resources):
    """Module-scoped main window with plugins loaded.

    Shared across all tests in a workflow file. No splash screen.
    Teardown closes the window and clears the command registry.
    """
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

    yield mw

    mw.close()
    for cmd in list(qapp.command_registry.commands()):
        qapp.command_registry.unregister(cmd.id)
    qapp.processEvents()


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
