from .fixtures import *
import pytest
import shiboken6
import PySide6QtAds as QtAds


@pytest.fixture
def bare_main_window(qapp, sciqlop_resources):
    """A fresh, per-test main window — the shared session-scoped ``main_window``
    fixture can't tell us whether the welcome page's area got its button *before*
    any plot panel was ever created, since earlier tests already left one there."""
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow

    mw = SciQLopMainWindow()
    yield mw
    mw.close()


def _welcome_area(main_window):
    dw = next(dw for dw in main_window.dock_manager.dockWidgets()
              if dw.widget() is main_window.welcome)
    return dw.dockAreaWidget()


def _area_for(main_window, panel):
    dw = main_window.dock_manager.findDockWidget(panel.name)
    return dw.dockAreaWidget()


def test_new_native_plot_panel_docks_into_explicit_area(main_window, qtbot):
    panel1 = main_window.new_plot_panel()
    try:
        area = _area_for(main_window, panel1)
        before = area.dockWidgetsCount()

        panel2 = main_window.new_native_plot_panel(area=area)
        try:
            qtbot.waitUntil(lambda: area.dockWidgetsCount() == before + 1, timeout=1000)
            assert _area_for(main_window, panel2) is area
        finally:
            main_window.remove_panel(panel2)
    finally:
        main_window.remove_panel(panel1)


def _add_button(area):
    return area.property("sciqlop_add_panel_button")


def test_plot_panel_area_gets_add_button(main_window, qtbot):
    panel = main_window.new_plot_panel()
    try:
        area = _area_for(main_window, panel)
        qtbot.waitUntil(lambda: _add_button(area) is not None, timeout=1000)
    finally:
        main_window.remove_panel(panel)


def test_second_panel_in_same_area_does_not_duplicate_button(main_window, qtbot):
    panel1 = main_window.new_plot_panel()
    try:
        area = _area_for(main_window, panel1)
        qtbot.waitUntil(lambda: _add_button(area) is not None, timeout=1000)
        first_button = _add_button(area)

        panel2 = main_window.new_native_plot_panel(area=area)
        try:
            qtbot.wait(50)
            assert _add_button(area) is first_button
        finally:
            main_window.remove_panel(panel2)
    finally:
        main_window.remove_panel(panel1)


def test_clicking_add_button_docks_new_panel_as_tab_in_same_area(main_window, qtbot):
    panel = main_window.new_plot_panel()
    try:
        area = _area_for(main_window, panel)
        qtbot.waitUntil(lambda: _add_button(area) is not None, timeout=1000)
        button = _add_button(area)
        before = area.dockWidgetsCount()
        before_names = set(main_window.plot_panels())

        button.click()
        qtbot.waitUntil(lambda: area.dockWidgetsCount() == before + 1, timeout=1000)

        new_names = [n for n in main_window.plot_panels() if n not in before_names]
        assert len(new_names) == 1
        new_panel = main_window.plot_panel(new_names[0])
        assert _area_for(main_window, new_panel) is area
        main_window.remove_panel(new_panel)
    finally:
        main_window.remove_panel(panel)


def test_welcome_page_area_gets_add_button_before_any_plot_panel(bare_main_window, qtbot):
    area = _welcome_area(bare_main_window)
    qtbot.waitUntil(lambda: _add_button(area) is not None, timeout=1000)


def test_area_without_plot_panels_still_gets_add_button(main_window, qtbot):
    """The "+" is a general "create a plot panel here" affordance, not
    conditional on the area already holding one — see the welcome-page test
    above for the motivating case."""
    from PySide6.QtWidgets import QLabel
    from SciQLop.core.unique_names import auto_name, release_name

    name = auto_name(base="PlainDockTest")
    plain = QLabel("plain widget")
    plain.setWindowTitle(name)
    dw = QtAds.CDockWidget(name)
    dw.setWidget(plain)
    try:
        area = main_window.dock_manager.addDockWidget(
            QtAds.DockWidgetArea.BottomDockWidgetArea, dw)
        qtbot.waitUntil(lambda: _add_button(area) is not None, timeout=1000)
    finally:
        dw.takeWidget()
        dw.closeDockWidget()
        plain.deleteLater()
        release_name(name)


def test_add_button_survives_deleting_the_only_panel_in_its_area(main_window, qtbot):
    """Reproduces a real crash: delete the only panel in an area (emptying
    it), then click a still-visible "+" button to create a new one.

    QtAds does not destroy the emptied CDockAreaWidget through a path that
    emits `destroyed` as PySide6 observes it, and its own
    CDockAreaTitleBar.dockAreaWidget() backref goes stale across the
    resulting area merge/reflow -- but the button itself survives
    (reparented into a different, still-valid area's title bar) and stays
    clickable. A button whose click handler captured the *original* area
    object by closure fires with a deleted C++ CDockAreaWidget and crashes
    with `RuntimeError: libshiboken: Internal C++ object ... already
    deleted` inside addDockWidgetTabToArea."""
    panel1 = main_window.new_plot_panel()
    area1 = _area_for(main_window, panel1)
    qtbot.waitUntil(lambda: _add_button(area1) is not None, timeout=1000)
    button = _add_button(area1)

    main_window.remove_panel(panel1)
    qtbot.wait(200)

    assert not shiboken6.isValid(area1), "test assumption: the area is actually gone"
    assert shiboken6.isValid(button), "test assumption: the button survives its area's death"

    before_names = set(main_window.plot_panels())
    button.click()
    qtbot.wait(200)

    new_names = [n for n in main_window.plot_panels() if n not in before_names]
    assert len(new_names) == 1
    main_window.remove_panel(main_window.plot_panel(new_names[0]))


def test_splitting_a_plot_panel_into_a_new_area_gets_its_own_add_button(main_window, qtbot):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.components.plotting.ui.panel_container import PanelContainer
    from SciQLop.core.unique_names import auto_name, release_name

    panel1 = main_window.new_plot_panel()
    try:
        area = _area_for(main_window, panel1)
        qtbot.waitUntil(lambda: _add_button(area) is not None, timeout=1000)

        name2 = auto_name(base="SplitTestPanel")
        panel2 = TimeSyncPanel(parent=None, name=name2, time_range=main_window.default_range)
        container2 = PanelContainer(panel2)
        dw2 = QtAds.CDockWidget(container2.windowTitle())
        dw2.setWidget(container2)
        try:
            new_area = main_window.dock_manager.addDockWidget(
                QtAds.DockWidgetArea.RightDockWidgetArea, dw2, area)
            qtbot.waitUntil(lambda: _add_button(new_area) is not None, timeout=1000)
            assert new_area is not area
        finally:
            dw2.takeWidget()
            dw2.closeDockWidget()
            container2.deleteLater()
            release_name(name2)
    finally:
        main_window.remove_panel(panel1)


def _auto_hide_areas(main_window):
    return [dw.dockAreaWidget() for dw in main_window.dock_manager.dockWidgetsMap().values()
            if dw.isAutoHide()]


def test_auto_hide_side_panels_never_get_add_button(bare_main_window, qtbot):
    areas = _auto_hide_areas(bare_main_window)
    assert areas, "expected side panels (Products/Catalogs/...) to be auto-hide"
    qtbot.waitUntil(lambda: _add_button(_welcome_area(bare_main_window)) is not None, timeout=1000)
    assert all(_add_button(area) is None for area in areas)
