"""When several auto-hide side panels are open at once (one per edge), the
"on top" one gets a `focused` cue on its side bar icon (see
`SciQLopMainWindow._on_focused_dock_widget_changed`).

QtAds only ever assigns focus when a panel is *opened* -- collapsing/hiding
the currently-focused panel does not pick a new focused one on its own (see
AutoHideDockContainer.cpp: `collapseView(false)` calls `setDockWidgetFocused`,
`collapseView(true)` does not touch focus at all). So if the top panel is
closed, SciQLop has to hand focus to another still-open panel itself.
"""
import pytest
import shiboken6
from PySide6 import QtWidgets
import PySide6QtAds as QtAds

from .fixtures import *


def _is_focused(dock_widget) -> bool:
    tab = dock_widget.autoHideDockContainer().autoHideTab()
    return bool(tab.property("focused"))


@pytest.fixture
def two_side_panels(main_window):
    """Two throwaway side panels on different edges, cleaned up afterwards."""
    left = QtWidgets.QLabel("left probe")
    left.setWindowTitle("Focus tracking probe (left)")
    right = QtWidgets.QLabel("right probe")
    right.setWindowTitle("Focus tracking probe (right)")

    main_window.add_side_pan(left, location=QtAds.PySide6QtAds.ads.SideBarLocation.SideBarLeft)
    main_window.add_side_pan(right, location=QtAds.PySide6QtAds.ads.SideBarLocation.SideBarRight)

    left_dw = main_window.dock_manager.findDockWidget(left.windowTitle())
    right_dw = main_window.dock_manager.findDockWidget(right.windowTitle())

    yield left_dw, right_dw

    for dw in (left_dw, right_dw):
        if dw is not None and shiboken6.isValid(dw):
            dw.takeWidget()
            dw.closeDockWidget()


def test_hiding_the_focused_panel_moves_the_cue_to_the_still_open_one(main_window, qtbot, two_side_panels):
    left_dw, right_dw = two_side_panels

    left_dw.autoHideDockContainer().collapseView(False)
    qtbot.wait(1)
    right_dw.autoHideDockContainer().collapseView(False)
    qtbot.wait(1)

    assert _is_focused(right_dw) is True, "the most recently opened panel should be on top"
    assert _is_focused(left_dw) is False

    right_dw.autoHideDockContainer().collapseView(True)
    qtbot.wait(1)

    assert _is_focused(left_dw) is True, (
        "closing the on-top panel left another panel open (left) -- it "
        "should now carry the on-top cue instead of nothing being highlighted"
    )
