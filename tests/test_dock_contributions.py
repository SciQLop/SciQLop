"""Docks and side panes are contributions to sciqlop.docks; the main window follows them."""
import pytest
import shiboken6
from PySide6.QtWidgets import QLabel

from SciQLop.core.docks import DOCKS, Dock
from SciQLop.core.extensions import owned_by

from .fixtures import *  # noqa: F401,F403


@pytest.fixture
def demo_docks(qtbot):
    yield
    DOCKS.remove_owner("dock_demo")
    qtbot.wait(50)


def _contribute(replace=False, **fields):
    with owned_by("dock_demo"):
        return DOCKS.contribute(Dock(**fields), replace=replace)


def _label_dock(title, placement="center", text="probe", **fields):
    return dict(id=f"dock_demo.{title}", title=title, build=lambda: QLabel(text), placement=placement, **fields)


def _action_texts(mw):
    return {holder: [a.text() for a in getattr(mw, holder).actions()] for holder in ("viewMenu", "toolBar", "toolsMenu")}


def _docks_titled(mw, title):
    return [dw for dw in mw.dock_manager.dockWidgetsMap().values() if dw.windowTitle() == title]


def test_core_side_panes_are_contributions(main_window):
    for title in ("Products", "Catalogs", "Settings", "Properties"):
        assert DOCKS.owner_of(f"sciqlop.{title}") == "sciqlop"


@pytest.mark.parametrize("toolbar", [False, True])
def test_a_center_dock_tabs_with_welcome(main_window, demo_docks, toolbar):
    _contribute(**_label_dock("Center probe", visible=False, toolbar=toolbar))

    dw = main_window.dock_manager.findDockWidget("Center probe")
    welcome = main_window.dock_manager.findDockWidget("Welcome")
    assert dw.dockAreaWidget() is welcome.dockAreaWidget()
    assert dw.isClosed()
    texts = _action_texts(main_window)
    assert "Center probe" in texts["viewMenu"]
    assert ("Center probe" in texts["toolBar"]) is toolbar
    assert ("Center probe" in texts["toolsMenu"]) is toolbar


def _docked(dw):
    return dw


def _floating(dw):
    dw.setFloating()
    return dw.floatingDockContainer()


def _side_pane(dw):
    return dw.autoHideDockContainer()


@pytest.mark.parametrize("placement, holder_of", [("center", _docked), ("center", _floating), ("left", _side_pane)],
                         ids=["docked", "floating", "side-pane"])
def test_withdrawal_closes_the_dock_and_its_actions(main_window, qtbot, demo_docks, placement, holder_of):
    _contribute(**_label_dock("Withdrawn probe", placement=placement, toolbar=True))
    dw = main_window.dock_manager.findDockWidget("Withdrawn probe")
    holder = holder_of(dw)
    assert holder is not None
    qtbot.wait(50)

    DOCKS.remove_owner("dock_demo")
    qtbot.wait(50)

    assert main_window.dock_manager.findDockWidget("Withdrawn probe") is None
    assert not shiboken6.isValid(dw) and not shiboken6.isValid(holder)
    assert all("Withdrawn probe" not in texts for texts in _action_texts(main_window).values())


def test_withdrawing_a_floating_dock_that_holds_a_plot(main_window, qtbot, demo_docks):
    """Run it with MALLOC_PERTURB_=165 too: glibc otherwise hides a read of the freed QRhi
    (docs/qt-bugs/qrhiwidget_reparent_uaf.py)."""
    from SciQLopPlots import SciQLopPlot
    plot = SciQLopPlot()
    _contribute(id="dock_demo.Plot probe", title="Plot probe", build=lambda: plot)
    window = _floating(main_window.dock_manager.findDockWidget("Plot probe"))
    qtbot.wait(300)

    DOCKS.remove_owner("dock_demo")
    qtbot.wait(300)

    assert not shiboken6.isValid(plot) and not shiboken6.isValid(window)


def test_replace_rebuilds(main_window, qtbot, demo_docks):
    second = QLabel("second")
    _contribute(**_label_dock("Replaced probe", text="first"))
    _contribute(replace=True, id="dock_demo.Replaced probe", title="Replaced probe", build=lambda: second)
    qtbot.wait(50)

    docks = _docks_titled(main_window, "Replaced probe")
    assert len(docks) == 1
    assert docks[0].widget() is second


def test_add_side_pan_is_an_adapter(main_window):
    first, second = QLabel("p"), QLabel("q")
    first.setWindowTitle("Pane")
    second.setWindowTitle("Pane")
    try:
        main_window.add_side_pan(first)
        assert DOCKS.owner_of("user.Pane") == "user"
        with pytest.raises(ValueError, match="Pane"):
            main_window.add_side_pan(second)
    finally:
        DOCKS.remove("user.Pane")


def test_bad_placement_is_refused():
    with pytest.raises(ValueError, match="top"):
        Dock(id="dock_demo.bad", title="Bad", build=QLabel, placement="top")


def _raise():
    raise RuntimeError("broken factory")


@pytest.fixture
def logged_errors(monkeypatch):
    from SciQLop.core.ui import mainwindow
    errors = []
    monkeypatch.setattr(mainwindow.log, "error", lambda msg, *a, **k: errors.append(msg))
    return errors


def test_a_raising_build_is_logged_not_raised(main_window, demo_docks, logged_errors):
    _contribute(id="dock_demo.broken", title="Broken probe", build=_raise)

    assert main_window.dock_manager.findDockWidget("Broken probe") is None
    assert len(logged_errors) == 1 and "dock_demo.broken" in logged_errors[0]


def test_a_build_returning_no_widget_is_logged(main_window, demo_docks, logged_errors):
    _contribute(id="dock_demo.not_a_widget", title="Not a widget probe", build=lambda: "text")

    assert main_window.dock_manager.findDockWidget("Not a widget probe") is None
    assert len(logged_errors) == 1 and "dock_demo.not_a_widget" in logged_errors[0]


def test_a_raising_build_does_not_break_a_new_window(qapp, main_window, demo_docks, logged_errors):
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    _contribute(id="dock_demo.broken", title="Broken probe", build=_raise)
    logged_errors.clear()
    previous = qapp.main_window
    second = SciQLopMainWindow()
    try:
        assert second.dock_manager.findDockWidget("Broken probe") is None
        assert len(logged_errors) == 1 and "dock_demo.broken" in logged_errors[0]
    finally:
        destroy_main_window(second)
        qapp.main_window = previous


def test_two_live_windows_keep_their_own_docks(qapp, main_window, qtbot, demo_docks):
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    previous = qapp.main_window
    second = SciQLopMainWindow()
    try:
        windows = (main_window, second)
        assert all(mw.dock_manager.findDockWidget("Products").widget() is mw.productTree for mw in windows)

        _contribute(**_label_dock("Shared probe"))
        assert all(mw.dock_manager.findDockWidget("Shared probe") is not None for mw in windows)

        DOCKS.remove_owner("dock_demo")
        qtbot.wait(50)
        assert all(mw.dock_manager.findDockWidget("Shared probe") is None for mw in windows)
    finally:
        destroy_main_window(second)
        qapp.main_window = previous
