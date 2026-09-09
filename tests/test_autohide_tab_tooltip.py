from .fixtures import *


def test_side_tab_tooltip_shows_when_hovering_opens_the_panel(main_window, qtbot):
    """Live report 2026-09-09: side-tab tooltips only ever showed when the
    panel was already open. QtAds opens a hovered auto-hide panel with a
    synthetic mouse press 500 ms in, and Qt cancels the pending tooltip
    (700 ms) on any press -- so the tooltip must be shown by us once the
    panel is open."""
    from PySide6.QtGui import QCursor
    from PySide6.QtWidgets import QToolTip
    from SciQLop.core.ui.mainwindow import _cursor_over

    dw = main_window.dock_manager.findDockWidget("Products")
    dw.autoHideDockContainer().collapseView(True)
    tab = dw.sideTabWidget()
    assert tab.toolTip()

    QCursor.setPos(tab.mapToGlobal(tab.rect().center()))
    qtbot.waitUntil(lambda: _cursor_over(tab), timeout=1000)
    dw.toggleView(True)
    qtbot.waitUntil(dw.isVisible, timeout=3000)

    qtbot.waitUntil(QToolTip.isVisible, timeout=2000)
    assert QToolTip.text() == tab.toolTip()
    QToolTip.hideText()
    dw.autoHideDockContainer().collapseView(True)
