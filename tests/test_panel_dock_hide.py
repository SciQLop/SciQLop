"""Hiding a panel's dock (QtAds toggleView(False), also used on auto-hide docks
in a floating container) emits the same `closed` signal as deleting it; only
a real close may destroy the panel."""
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from tests.fixtures import *  # noqa: F401,F403


def _flush():
    # Timers first: when a tab closes, QtAds queues a 0 ms timer holding a raw
    # pointer to the tab that becomes current (DockAreaTabBar.cpp). Flushing
    # deferred deletes before it runs can free that tab (a leftover dock from
    # an earlier test on the shared window) under it: a segfault.
    QApplication.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()


def test_hiding_a_panel_dock_keeps_the_panel(qtbot, qapp, main_window):
    panel = main_window.new_native_plot_panel()
    dock_widget = main_window.dock_manager.findDockWidget(panel.name)

    dock_widget.toggleView(False)
    _flush()

    assert shiboken6.isValid(panel)
    dock_widget.toggleView(True)
    _flush()
    assert shiboken6.isValid(panel)
    assert main_window.plot_panel(panel.name) is not None
    main_window.remove_panel(panel)
    _flush()


def test_force_closing_a_panel_dock_still_destroys_the_panel(qtbot, qapp, main_window):
    panel = main_window.new_native_plot_panel()
    dock_widget = main_window.dock_manager.findDockWidget(panel.name)

    dock_widget.closeDockWidget()
    _flush()

    assert not shiboken6.isValid(panel)
