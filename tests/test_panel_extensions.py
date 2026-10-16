"""Panel extensions attach to every open and future panel of some kinds, and clean up (plan 2g, task 3)."""
import pytest
from PySide6.QtWidgets import QLabel

from SciQLop.core.extensions import owned_by
from SciQLop.core.panel_extensions import PANEL_EXTENSIONS, PanelExtension
from SciQLop.core.panel_kinds import PANEL_KINDS, PanelKind
from SciQLop.core.plot_kinds import TIME_PANEL

from .fixtures import *  # noqa: F401,F403

LABEL = "px_demo.label"


@pytest.fixture
def px_demo(main_window, qtbot):
    before = set(main_window.panels())
    with owned_by("px_demo"):
        PANEL_KINDS.contribute(PanelKind(LABEL, "Label", create=lambda name, config: QLabel(name)))
    yield
    PANEL_EXTENSIONS.remove_owner("px_demo")
    PANEL_KINDS.remove_owner("px_demo")
    for panel in [p for p in main_window.panels() if p not in before]:
        main_window.remove_panel(panel)
    qtbot.waitUntil(lambda: set(main_window.panels()) <= before)


@pytest.fixture
def events():
    return []


def _recorder(ext_id, events):
    def attach(panel):
        name = panel.objectName()
        events.append(("attach", ext_id, name))
        return lambda: events.append(("clean", ext_id, name))
    return attach


def _extend(ext_id, attach, kinds=(), replace=False):
    with owned_by("px_demo"):
        return PANEL_EXTENSIONS.contribute(PanelExtension(ext_id, attach, kinds), replace=replace)


def _mine(events):
    return [e for e in events if "px_" in e[2]]


def _boom(*_):
    raise RuntimeError("boom")


@pytest.fixture
def logged_errors(monkeypatch):
    import SciQLop.core.ui.panel_extensions_follower as follower
    errors = []
    monkeypatch.setattr(follower.log, "error", lambda msg, *a, **k: errors.append(msg))
    return errors


def test_attaches_to_open_and_future_panels(main_window, px_demo, events):
    main_window.open_panel(TIME_PANEL, name="px_first")
    _extend("px_demo.ext", _recorder("px_demo.ext", events), kinds=(TIME_PANEL,))
    assert _mine(events) == [("attach", "px_demo.ext", "px_first")]
    main_window.open_panel(TIME_PANEL, name="px_second")
    assert _mine(events) == [("attach", "px_demo.ext", "px_first"), ("attach", "px_demo.ext", "px_second")]


def test_kinds_filter(main_window, px_demo, events):
    _extend("px_demo.ext", _recorder("px_demo.ext", events), kinds=(LABEL,))
    main_window.open_panel(TIME_PANEL, name="px_time")
    main_window.open_panel(LABEL, name="px_label")
    assert _mine(events) == [("attach", "px_demo.ext", "px_label")]


def test_no_kinds_means_every_kind(main_window, px_demo, events):
    _extend("px_demo.ext", _recorder("px_demo.ext", events))
    main_window.open_panel(TIME_PANEL, name="px_time")
    main_window.open_panel(LABEL, name="px_label")
    assert _mine(events) == [("attach", "px_demo.ext", "px_time"), ("attach", "px_demo.ext", "px_label")]


def _by_remove_panel(mw, panel):
    mw.remove_panel(panel)


def _by_dock_x(mw, panel):
    mw._dock_of(panel).requestCloseDockWidget()


def _by_floating_dock_x(mw, panel):
    dw = mw._dock_of(panel)
    dw.setFloating()
    dw.requestCloseDockWidget()


def _by_force_close(mw, panel):
    mw._dock_of(panel).closeDockWidget()


@pytest.mark.parametrize("close", [_by_remove_panel, _by_dock_x, _by_floating_dock_x, _by_force_close])
def test_cleanup_on_close(main_window, px_demo, events, qtbot, close):
    _extend("px_demo.ext", _recorder("px_demo.ext", events), kinds=(LABEL,))
    panel = main_window.open_panel(LABEL, name="px_closed")
    close(main_window, panel)
    qtbot.waitUntil(lambda: panel not in main_window.panels())
    qtbot.waitUntil(lambda: _mine(events)[-1:] == [("clean", "px_demo.ext", "px_closed")])
    assert _mine(events) == [("attach", "px_demo.ext", "px_closed"), ("clean", "px_demo.ext", "px_closed")]
    assert main_window._panel_extensions._cleanups == {}


def test_panel_closing_twice_cleans_once(main_window, px_demo, events):
    _extend("px_demo.ext", _recorder("px_demo.ext", events), kinds=(LABEL,))
    panel = main_window.open_panel(LABEL, name="px_twice")
    main_window._panel_extensions.panel_closing(panel)
    main_window._panel_extensions.panel_closing(panel)
    assert _mine(events).count(("clean", "px_demo.ext", "px_twice")) == 1


def test_cleanup_on_withdrawal(main_window, px_demo, events):
    _extend("px_demo.ext", _recorder("px_demo.ext", events), kinds=(LABEL, TIME_PANEL))
    a = main_window.open_panel(LABEL, name="px_a")
    b = main_window.open_panel(TIME_PANEL, name="px_b")
    PANEL_EXTENSIONS.remove_owner("px_demo")
    cleaned = sorted(e for e in _mine(events) if e[0] == "clean")
    assert cleaned == [("clean", "px_demo.ext", "px_a"), ("clean", "px_demo.ext", "px_b")]
    assert {a, b} <= set(main_window.panels())


def test_replace_cleans_then_attaches(main_window, px_demo, events):
    main_window.open_panel(LABEL, name="px_replaced")
    _extend("px_demo.ext", _recorder("old", events), kinds=(LABEL,))
    _extend("px_demo.ext", _recorder("new", events), kinds=(LABEL,), replace=True)
    assert _mine(events) == [("attach", "old", "px_replaced"), ("clean", "old", "px_replaced"),
                             ("attach", "new", "px_replaced")]


def test_attach_raising_is_contained(main_window, px_demo, events, logged_errors, qtbot):
    _extend("px_demo.broken", _boom, kinds=(LABEL,))
    _extend("px_demo.ext", _recorder("px_demo.ext", events), kinds=(LABEL,))
    panel = main_window.open_panel(LABEL, name="px_raising")
    assert panel in main_window.panels()
    assert len(logged_errors) == 1 and "px_demo.broken" in logged_errors[0] and "px_raising" in logged_errors[0]
    main_window.remove_panel(panel)
    qtbot.waitUntil(lambda: panel not in main_window.panels())
    assert _mine(events) == [("attach", "px_demo.ext", "px_raising"), ("clean", "px_demo.ext", "px_raising")]


def test_cleanup_raising_is_contained(main_window, px_demo, events, logged_errors, qtbot):
    _extend("px_demo.broken", lambda panel: _boom, kinds=(LABEL,))
    _extend("px_demo.ext", _recorder("px_demo.ext", events), kinds=(LABEL,))
    panel = main_window.open_panel(LABEL, name="px_clean_raising")
    main_window.remove_panel(panel)
    qtbot.waitUntil(lambda: panel not in main_window.panels())
    assert len(logged_errors) == 1 and "px_demo.broken" in logged_errors[0]
    assert ("clean", "px_demo.ext", "px_clean_raising") in _mine(events)
    assert main_window._panel_extensions._cleanups == {}


def test_vp_debug_panel_attaches_on_open_and_cleans_on_force_close(main_window, px_demo, events, qtbot):
    from SciQLop.user_api.virtual_products.debug import _create_debug_panel
    _extend("px_demo.ext", _recorder("px_demo.ext", events), kinds=(TIME_PANEL,))
    panel = _create_debug_panel("px_debug")
    assert _mine(events) == [("attach", "px_demo.ext", panel.name)]
    main_window.dock_manager.findDockWidget(panel.name).closeDockWidget()
    qtbot.waitUntil(lambda: _mine(events)[-1:] == [("clean", "px_demo.ext", "VP Debug: px_debug")])
    assert main_window._panel_extensions._cleanups == {}


def test_a_cleanup_closing_another_panel(main_window, px_demo, events, qtbot):
    first = main_window.open_panel(LABEL, name="px_r1")
    other = main_window.open_panel(LABEL, name="px_r2")

    def attach(panel):
        name = panel.objectName()
        events.append(("attach", "px_demo.ext", name))

        def cleanup():
            events.append(("clean", "px_demo.ext", name))
            if panel is first:
                main_window.remove_panel(other)
        return cleanup

    _extend("px_demo.ext", attach, kinds=(LABEL,))
    PANEL_EXTENSIONS.remove("px_demo.ext")
    assert _mine(events).count(("clean", "px_demo.ext", "px_r2")) == 1
    qtbot.waitUntil(lambda: other not in main_window.panels())
    assert main_window._panel_extensions._cleanups == {}


def test_an_attach_closing_its_own_panel_is_cleaned_at_once(main_window, px_demo, events, qtbot):
    def closes_its_panel(panel):
        name = panel.objectName()
        events.append(("attach", "closer", name))
        main_window.remove_panel(panel)
        return lambda: events.append(("clean", "closer", name))

    _extend("px_demo.closer", closes_its_panel, kinds=(LABEL,))
    _extend("px_demo.ext", _recorder("px_demo.ext", events), kinds=(LABEL,))
    panel = main_window.open_panel(LABEL, name="px_self_closing")
    qtbot.waitUntil(lambda: panel not in main_window.panels())
    assert _mine(events) == [("attach", "closer", "px_self_closing"), ("clean", "closer", "px_self_closing")]
    assert main_window._panel_extensions._cleanups == {}


def test_a_cleanup_withdrawing_another_extension(main_window, px_demo, events, qtbot):
    def attach_a(panel):
        return lambda: (events.append(("clean", "a", panel.objectName())), PANEL_EXTENSIONS.remove("px_demo.b"))

    _extend("px_demo.a", attach_a, kinds=(LABEL,))
    _extend("px_demo.b", _recorder("b", events), kinds=(LABEL,))
    panel = main_window.open_panel(LABEL, name="px_withdraws")
    main_window.remove_panel(panel)
    qtbot.waitUntil(lambda: panel not in main_window.panels())
    cleaned = [e for e in _mine(events) if e[0] == "clean"]
    assert cleaned == [("clean", "a", "px_withdraws"), ("clean", "b", "px_withdraws")]


def test_two_windows(qapp, main_window, px_demo, events):
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    previous = qapp.main_window
    second = SciQLopMainWindow()
    second_follower = second._panel_extensions
    try:
        main_window.open_panel(TIME_PANEL, name="px_in_first")
        second.open_panel(TIME_PANEL, name="px_in_second")
        _extend("px_demo.ext", _recorder("px_demo.ext", events), kinds=(TIME_PANEL,))
        assert sorted(_mine(events)) == [("attach", "px_demo.ext", "px_in_first"),
                                         ("attach", "px_demo.ext", "px_in_second")]
    finally:
        destroy_main_window(second)
        qapp.main_window = previous
    _extend("px_demo.other", _recorder("px_demo.other", events), kinds=(TIME_PANEL,))
    assert _mine(events)[-1] == ("attach", "px_demo.other", "px_in_first")
    assert ("attach", "px_demo.other", "px_in_second") not in _mine(events)
    assert len(second_follower._cleanups) == 0, "a destroyed window's follower lets go of its panels"
