"""Renaming a panel from the Properties inspector (SciQLopPlots' panel delegate
calls setObjectName) must reach the dock tab and the name-based lookups (#152)."""
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from tests.fixtures import *  # noqa: F401,F403


def _flush():
    QApplication.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()


def test_renamed_panel_updates_its_dock_tab(qtbot, qapp, main_window):
    panel = main_window.new_native_plot_panel()
    dock_widget = main_window.dock_manager.findDockWidget(panel.name)

    panel.setObjectName("Renamed152")

    assert dock_widget.windowTitle() == "Renamed152"
    assert dock_widget.tabWidget().text() == "Renamed152"
    main_window.remove_panel(panel)
    _flush()


def test_renamed_panel_is_found_by_its_new_name(qtbot, qapp, main_window):
    panel = main_window.new_native_plot_panel()
    old_name = panel.name

    panel.setObjectName("Renamed152b")

    assert main_window.plot_panel("Renamed152b") is panel
    assert main_window.plot_panel(old_name) is None
    assert "Renamed152b" in main_window.plot_panels()
    main_window.remove_panel(panel)
    _flush()


def test_renamed_panel_can_be_removed(qtbot, qapp, main_window):
    panel = main_window.new_native_plot_panel()
    panel.setObjectName("Renamed152c")

    main_window.remove_panel(panel)
    _flush()

    assert "Renamed152c" not in main_window.plot_panels()


def test_floating_panel_is_still_listed_and_found(qtbot, qapp, main_window):
    # dock_manager.dockWidgets() only lists the main container's docks, not floating ones.
    panel = main_window.new_native_plot_panel()
    main_window.dock_manager.findDockWidget(panel.name).setFloating()

    assert panel.name in main_window.plot_panels()
    assert main_window.plot_panel(panel.name) is panel
    name = panel.name
    main_window.remove_panel(panel)
    _flush()
    assert name not in main_window.plot_panels()
