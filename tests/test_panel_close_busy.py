"""GH #137: destroying a graph joined its data-provider thread on the GUI thread, so
closing a panel whose callback was still running froze the whole application until
the callback returned. Fixed in SciQLopPlots 0.37.0: destroying a graph no longer waits."""
import threading

import numpy as np
import pytest
import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from tests.fixtures import *  # noqa: F401,F403

_FAILSAFE_S = 15.0


def _plot_a_blocked_callback(qtbot):
    from SciQLop.user_api.plot import TimeRange, create_plot_panel
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType

    started, release, returned = threading.Event(), threading.Event(), threading.Event()

    def blocked(start: float, stop: float):
        started.set()
        release.wait(_FAILSAFE_S)
        returned.set()
        return np.array([start, stop]), np.zeros(2)

    vp = create_virtual_product("close_busy/blocked", blocked, VirtualProductType.Scalar, labels=["x"])
    panel = create_plot_panel()
    panel.time_range = TimeRange(0.0, 10.0)
    panel.plot(vp)
    qtbot.waitUntil(started.is_set, timeout=5000)
    return panel, release, returned


def _close_with_the_api(panel, dock_widget):
    panel.close()


def _close_with_the_tab_x_button(panel, dock_widget):
    dock_widget.tabWidget().closeRequested.emit()


def test_removing_a_bare_panel_docked_without_a_container_is_harmless(qtbot, qapp, main_window):
    """The VP debug panel docks a TimeSyncPanel directly, with no PanelContainer."""
    import PySide6QtAds as QtAds
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core.unique_names import auto_name

    panel = TimeSyncPanel(parent=None, name=auto_name(base="Panel", name="bare panel"),
                          show_search_overlay=False)
    dock_widget = QtAds.CDockWidget(panel.windowTitle())
    dock_widget.setWidget(panel)
    dock_widget.setFeature(QtAds.CDockWidget.DockWidgetDeleteOnClose, True)
    main_window.dock_manager.addDockWidget(QtAds.DockWidgetArea.RightDockWidgetArea, dock_widget)

    with qtbot.captureExceptions() as exceptions:
        main_window.remove_panel(panel)
        qtbot.waitUntil(lambda: not shiboken6.isValid(panel), timeout=5000)

    assert exceptions == []


@pytest.mark.parametrize("close", [_close_with_the_api, _close_with_the_tab_x_button],
                         ids=["PlotPanel.close", "tab X button"])
def test_closing_a_panel_does_not_wait_for_its_running_callback(qtbot, qapp, main_window, close):
    """Timing-free: destroying the graph used to join the callback's thread, so the
    callback had already returned by the time the deferred delete was flushed."""
    panel, release, returned = _plot_a_blocked_callback(qtbot)
    panel_name = panel._get_impl_or_raise().name
    dock_widget = main_window.dock_manager.findDockWidget(panel_name)
    container = dock_widget.widget()

    close(panel, dock_widget)
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()

    assert not returned.is_set(), "the GUI thread waited for the callback"
    assert not shiboken6.isValid(container)
    assert main_window.dock_manager.findDockWidget(panel_name) is None, "a hidden empty dock is left behind"
    release.set()
