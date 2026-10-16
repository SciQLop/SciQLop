"""Panels are contributions to sciqlop.panel_kinds; open_panel docks any kind (plan 2g, task 1)."""
import pytest
import shiboken6
from PySide6.QtWidgets import QLabel

from SciQLop.core.extensions import owned_by
from SciQLop.core.panel_kinds import PANEL_KINDS, PanelKind, panel_kind_of
from SciQLop.core.plot_kinds import TIME_PANEL

from .fixtures import *  # noqa: F401,F403


def _label(name, config):
    return QLabel(config.get("text", ""))


def _contribute(kind_id="pk_demo.label", create=_label, **fields):
    with owned_by("pk_demo"):
        return PANEL_KINDS.contribute(PanelKind(kind_id, "Label", create=create, **fields))


@pytest.fixture
def demo_kinds(main_window, qtbot):
    before = set(main_window.panels())
    yield
    PANEL_KINDS.remove_owner("pk_demo")
    for panel in [p for p in main_window.panels() if p not in before]:
        main_window.remove_panel(panel)
    qtbot.waitUntil(lambda: set(main_window.panels()) <= before)


def _docks_titled(mw, title):
    return [dw for dw in mw.dock_manager.dockWidgetsMap().values()
            if shiboken6.isValid(dw) and dw.windowTitle() == title]


def test_empty_id_or_label_is_refused():
    with pytest.raises(ValueError):
        PanelKind("", "Label", create=_label)
    with pytest.raises(ValueError):
        PanelKind("pk_demo.x", "", create=_label)


def test_the_time_panel_is_a_core_kind(main_window, demo_kinds):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    assert TIME_PANEL in PANEL_KINDS
    assert PANEL_KINDS.owner_of(TIME_PANEL) == "sciqlop"
    panel = main_window.new_plot_panel()
    assert isinstance(panel, TimeSyncPanel)
    assert panel_kind_of(panel) == TIME_PANEL
    assert panel.name.startswith("Panel")
    assert panel.name in main_window.plot_panels()


def test_open_panel_docks_a_plugin_widget(main_window, demo_kinds, qtbot):
    _contribute()
    added = []
    main_window.panel_added.connect(added.append)
    try:
        w = main_window.open_panel("pk_demo.label", text="hi")
    finally:
        main_window.panel_added.disconnect(added.append)
    assert w.text() == "hi"
    assert panel_kind_of(w) == "pk_demo.label"
    assert w in main_window.panels()
    assert w.objectName() not in main_window.plot_panels()
    assert w.objectName().startswith("Label")
    assert _docks_titled(main_window, w.objectName())
    assert added == [w]


def test_untagged_widget_has_no_kind(qapp):
    assert panel_kind_of(QLabel()) is None


def test_names_are_unique(main_window, demo_kinds):
    _contribute()
    a = main_window.open_panel("pk_demo.label", name="X")
    b = main_window.open_panel("pk_demo.label", name="X")
    assert a.objectName() == "X"
    assert b.objectName() != a.objectName()
    assert {a, b} <= set(main_window.panels())


def test_remove_panel_closes_any_kind(main_window, demo_kinds, qtbot):
    _contribute()
    w = main_window.open_panel("pk_demo.label", name="pk_demo_removed")
    main_window.remove_panel(w)
    qtbot.waitUntil(lambda: w not in main_window.panels())
    again = main_window.open_panel("pk_demo.label", name="pk_demo_removed")
    assert again.objectName() == "pk_demo_removed"


def test_remove_panel_by_name(main_window, demo_kinds, qtbot):
    _contribute()
    w = main_window.open_panel("pk_demo.label", name="pk_demo_by_name")
    main_window.remove_panel("pk_demo_by_name")
    qtbot.waitUntil(lambda: w not in main_window.panels())


def _docked(dw):
    return dw


def _floating(dw):
    dw.setFloating()


@pytest.mark.parametrize("place", [_docked, _floating])
def test_closing_by_the_dock_x(main_window, demo_kinds, qtbot, place):
    _contribute()
    w = main_window.open_panel("pk_demo.label", name=f"pk_demo_x_{place.__name__}")
    dw = main_window._dock_of(w)
    place(dw)
    dw.requestCloseDockWidget()
    qtbot.waitUntil(lambda: w not in main_window.panels())
    assert not _docks_titled(main_window, f"pk_demo_x_{place.__name__}")


def test_create_raising_is_logged_and_raised(main_window, demo_kinds, monkeypatch):
    import SciQLop.core.ui.mainwindow as mainwindow

    def _boom(name, config):
        raise RuntimeError("boom")

    errors = []
    monkeypatch.setattr(mainwindow.log, "error", lambda msg, *a, **k: errors.append(msg))
    _contribute("pk_demo.broken", create=_boom)
    docks_before = len(main_window.dock_manager.dockWidgetsMap())
    with pytest.raises(RuntimeError, match="boom"):
        main_window.open_panel("pk_demo.broken", name="pk_demo_broken")
    assert len(errors) == 1 and "pk_demo.broken" in errors[0]
    assert len(main_window.dock_manager.dockWidgetsMap()) == docks_before
    _contribute()
    assert main_window.open_panel("pk_demo.label", name="pk_demo_broken").objectName() == "pk_demo_broken"


def test_create_returning_a_non_widget_is_logged_and_refused(main_window, demo_kinds, monkeypatch):
    import SciQLop.core.ui.mainwindow as mainwindow
    errors = []
    monkeypatch.setattr(mainwindow.log, "error", lambda msg, *a, **k: errors.append(msg))
    _contribute("pk_demo.not_a_widget", create=lambda name, config: "not a widget")
    with pytest.raises(TypeError):
        main_window.open_panel("pk_demo.not_a_widget", name="pk_demo_nw")
    assert len(errors) == 1 and "pk_demo.not_a_widget" in errors[0]
    _contribute()
    assert main_window.open_panel("pk_demo.label", name="pk_demo_nw").objectName() == "pk_demo_nw"


def test_a_failed_docking_frees_the_name(main_window, demo_kinds, monkeypatch):
    import SciQLop.core.ui.mainwindow as mainwindow

    def _refuse(*args):
        raise RuntimeError("no dock")

    _contribute()
    monkeypatch.setattr(mainwindow, "dock_panel", _refuse)
    with pytest.raises(RuntimeError, match="no dock"):
        main_window.open_panel("pk_demo.label", name="pk_demo_undocked")
    monkeypatch.undo()
    assert main_window.open_panel("pk_demo.label", name="pk_demo_undocked").objectName() == "pk_demo_undocked"


def test_a_plugin_kind_icon_shows_on_its_dock_tab(main_window, demo_kinds):
    from PySide6.QtWidgets import QApplication
    assert PANEL_KINDS.get(TIME_PANEL).icon is None
    _contribute(icon="add_graph")
    w = main_window.open_panel("pk_demo.label")
    icon = main_window._dock_of(w).icon()
    assert not icon.isNull()
    assert icon.cacheKey() == w.windowIcon().cacheKey()
    assert icon.cacheKey() != QApplication.windowIcon().cacheKey()


def test_unknown_kind(main_window):
    with pytest.raises(LookupError, match=TIME_PANEL):
        main_window.open_panel("nope.kind")
