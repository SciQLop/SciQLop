"""How a right-click reaches TimeSyncPanel's context menu.

The panel used to install itself as a Python eventFilter on every plot
child, so every paint/mouse/timer event took the GIL (GH #143). The menu
must still open from anywhere inside a plot, without that filter."""
import numpy as np
from PySide6.QtCore import QPoint
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtWidgets import QApplication


def _shown_panel_with_plot(qtbot):
    from SciQLop.components.plotting.ui.time_sync_panel import (
        TimeSyncPanel, plot_static_data,
    )
    panel = TimeSyncPanel("routing-test", show_search_overlay=False)
    qtbot.addWidget(panel)
    panel.resize(800, 600)
    panel.show()
    qtbot.waitExposed(panel)
    plot, _graph = plot_static_data(
        panel, np.array([0.0, 1.0, 2.0]), np.array([0.0, 1.0, 0.0]))
    qtbot.waitUntil(lambda: plot.isVisible() and plot.width() > 0)
    return panel, plot


def _record_menu_requests(panel, monkeypatch):
    requests = []
    monkeypatch.setattr(panel, "_show_context_menu",
                        lambda global_pos, source=None: requests.append(source))
    return requests


def _right_click(widget):
    local = QPoint(widget.width() // 2, widget.height() // 2)
    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, local,
                              widget.mapToGlobal(local))
    QApplication.sendEvent(widget, event)


def _real_right_click(widget):
    """Through the window, as the platform delivers it: Qt picks the deepest child
    under the cursor and synthesises the QContextMenuEvent itself."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    window = widget.window().windowHandle()
    local = widget.mapTo(widget.window(), QPoint(widget.width() // 2, widget.height() // 2))
    QTest.mouseClick(window, Qt.MouseButton.RightButton, Qt.KeyboardModifier.NoModifier, local)


def test_real_right_click_on_plot_opens_panel_menu(qtbot, monkeypatch):
    panel, plot = _shown_panel_with_plot(qtbot)
    requests = _record_menu_requests(panel, monkeypatch)
    _real_right_click(plot)
    qtbot.waitUntil(lambda: len(requests) == 1, timeout=1000)
    assert panel._plot_containing(requests[0]) is plot


def test_panel_does_not_filter_every_event():
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    assert "eventFilter" not in vars(TimeSyncPanel)


def test_right_click_on_plot_opens_panel_menu(qtbot, monkeypatch):
    panel, plot = _shown_panel_with_plot(qtbot)
    requests = _record_menu_requests(panel, monkeypatch)
    _right_click(plot)
    assert len(requests) == 1
    assert panel._plot_containing(requests[0]) is plot

