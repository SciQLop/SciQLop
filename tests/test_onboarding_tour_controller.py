from .fixtures import *
import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QPushButton


def _make_step(step_id, resolver, completion=None):
    from SciQLop.components.onboarding.backend.tour import TourStep
    return TourStep(step_id=step_id, title=f"{step_id} title", body=f"{step_id} body",
                    resolver=resolver, completion=completion)


def _make_tour(tour_id, steps):
    from SciQLop.components.onboarding.backend.tour import Tour
    return Tour(id=tour_id, title=tour_id, description="test tour", steps=steps)


def _side_tab(main_window):
    """A widget that is reliably visible in the session main window."""
    return main_window.dock_manager.findDockWidget("Products").sideTabWidget()


class _Emitter(QObject):
    fired = Signal(object)


def test_start_shows_coach_mark_for_first_step(main_window, qtbot):
    from SciQLop.components.onboarding.ui.tour_controller import TourController

    tour = _make_tour("t1", [_make_step("only", lambda mw, ctx: _side_tab(mw))])
    controller = TourController(main_window, tour)
    controller.start()
    try:
        qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=1000)
        assert controller._current_step().step_id == "only"
        assert controller._coach_mark.bubble._progress_label.text() == "1 / 1"
        assert controller._coach_mark.bubble._next_button.text() == "Done"
        assert not controller._coach_mark.bubble._back_button.isVisible()
    finally:
        controller.abort()


def test_next_advances_and_back_returns(main_window, qtbot):
    from SciQLop.components.onboarding.ui.tour_controller import TourController

    tour = _make_tour("t2", [
        _make_step("first", lambda mw, ctx: _side_tab(mw)),
        _make_step("second", lambda mw, ctx: _side_tab(mw)),
    ])
    controller = TourController(main_window, tour)
    controller.start()
    try:
        qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=1000)
        controller._coach_mark.next_clicked.emit()
        qtbot.waitUntil(lambda: controller._current_step().step_id == "second", timeout=1000)
        qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=1000)
        assert controller._coach_mark.bubble._progress_label.text() == "2 / 2"
        assert controller._coach_mark.bubble._back_button.isVisible()

        controller._coach_mark.back_clicked.emit()
        qtbot.waitUntil(lambda: controller._current_step().step_id == "first", timeout=1000)
        qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=1000)
    finally:
        controller.abort()


def test_a_second_next_before_the_deferred_entry_does_not_skip_a_step(main_window, qtbot):
    """Key repeat on Enter, or a completion firing twice, must move one
    step, not two."""
    from SciQLop.components.onboarding.ui.tour_controller import TourController

    tour = _make_tour("t_double", [
        _make_step("first", lambda mw, ctx: _side_tab(mw)),
        _make_step("second", lambda mw, ctx: _side_tab(mw)),
        _make_step("third", lambda mw, ctx: _side_tab(mw)),
    ])
    controller = TourController(main_window, tour)
    controller.start()
    try:
        qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=1000)
        controller._coach_mark.next_clicked.emit()
        controller._coach_mark.next_clicked.emit()
        qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=1000)
        assert controller._current_step().step_id == "second"
    finally:
        controller.abort()


def test_next_on_the_last_step_finishes_the_tour(main_window, qtbot):
    from SciQLop.components.onboarding.ui.tour_controller import TourController
    from SciQLop.components.onboarding.backend.settings import OnboardingSettings

    with OnboardingSettings() as s:
        s.completed_tours = {}
    tour = _make_tour("t_last", [_make_step("only", lambda mw, ctx: _side_tab(mw))])
    controller = TourController(main_window, tour)
    controller.start()
    qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=1000)

    controller._coach_mark.next_clicked.emit()

    qtbot.waitUntil(lambda: controller.is_finished, timeout=1000)
    assert OnboardingSettings().completed_tours.get("t_last") is True


def test_step_with_no_resolver_shows_a_centered_tip(main_window, qtbot):
    from SciQLop.components.onboarding.ui.tour_controller import TourController

    tour = _make_tour("t_intro", [_make_step("intro", None)])
    controller = TourController(main_window, tour)
    controller.start()
    try:
        qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=1000)
        assert controller._coach_mark._target is None
        assert controller._coach_mark._cutout_rect() is None
    finally:
        controller.abort()


def test_step_whose_target_is_missing_is_skipped_not_fatal(main_window, qtbot):
    from SciQLop.components.onboarding.ui.tour_controller import TourController

    tour = _make_tour("t_skip", [
        _make_step("missing", lambda mw, ctx: None),
        _make_step("hidden", lambda mw, ctx: mw.productTree),
        _make_step("shown", lambda mw, ctx: _side_tab(mw)),
    ])
    controller = TourController(main_window, tour)
    controller.start()
    try:
        qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=1000)
        assert controller._current_step().step_id == "shown"
        assert controller.is_finished is False
    finally:
        controller.abort()


def test_back_skips_over_unavailable_steps_too(main_window, qtbot):
    from SciQLop.components.onboarding.ui.tour_controller import TourController

    tour = _make_tour("t_back_skip", [
        _make_step("first", lambda mw, ctx: _side_tab(mw)),
        _make_step("missing", lambda mw, ctx: None),
        _make_step("third", lambda mw, ctx: _side_tab(mw)),
    ])
    controller = TourController(main_window, tour)
    controller.start()
    try:
        qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=1000)
        controller._coach_mark.next_clicked.emit()
        qtbot.waitUntil(lambda: controller._current_step().step_id == "third", timeout=1000)
        controller._coach_mark.back_clicked.emit()
        qtbot.waitUntil(lambda: controller._current_step().step_id == "first", timeout=1000)
        qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=1000)
    finally:
        controller.abort()


def test_tour_with_no_showable_step_finishes_cleanly(main_window, qtbot):
    from SciQLop.components.onboarding.ui.tour_controller import TourController
    from SciQLop.components.onboarding.backend.settings import OnboardingSettings

    with OnboardingSettings() as s:
        s.completed_tours = {}
    tour = _make_tour("t_none", [_make_step("missing", lambda mw, ctx: None)])
    controller = TourController(main_window, tour)
    controller.start()
    assert controller.is_finished is True
    assert OnboardingSettings().completed_tours.get("t_none") is True


def test_completion_signal_advances_and_stores_single_arg_in_context(main_window, qtbot):
    from SciQLop.components.onboarding.ui.tour_controller import TourController

    emitter = _Emitter()
    tour = _make_tour("t3", [
        _make_step("wait_for_it", lambda mw, ctx: _side_tab(mw),
                   completion=lambda mw, ctx: emitter.fired),
        _make_step("after", lambda mw, ctx: _side_tab(mw)),
    ])
    controller = TourController(main_window, tour)
    controller.start()
    try:
        qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=1000)
        assert controller._coach_mark.bubble._next_button.isVisible()
        emitter.fired.emit("payload")
        qtbot.waitUntil(lambda: controller._current_step().step_id == "after", timeout=1000)
        assert controller._context["wait_for_it"] == "payload"
    finally:
        controller.abort()


def test_completion_predicate_filters_signal_args(main_window, qtbot):
    from SciQLop.components.onboarding.ui.tour_controller import TourController

    emitter = _Emitter()
    tour = _make_tour("t4", [
        _make_step("wait_true", lambda mw, ctx: _side_tab(mw),
                   completion=lambda mw, ctx: (emitter.fired, lambda v: v)),
        _make_step("after", lambda mw, ctx: _side_tab(mw)),
    ])
    controller = TourController(main_window, tour)
    controller.start()
    try:
        qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=1000)
        emitter.fired.emit(False)
        qtbot.wait(100)
        assert controller._current_step().step_id == "wait_true"

        emitter.fired.emit(True)
        qtbot.waitUntil(lambda: controller._current_step().step_id == "after", timeout=1000)
    finally:
        controller.abort()


def test_advance_defers_next_step_entry_to_the_next_event_loop_turn(main_window, qtbot):
    """A completion can fire from inside a nested event loop (a native
    drag's QDrag::exec()); the next coach mark must not be shown from
    that call stack."""
    from SciQLop.components.onboarding.ui.tour_controller import TourController

    emitter = _Emitter()
    tour = _make_tour("t_defer", [
        _make_step("first", lambda mw, ctx: _side_tab(mw),
                   completion=lambda mw, ctx: emitter.fired),
        _make_step("second", lambda mw, ctx: _side_tab(mw)),
    ])
    controller = TourController(main_window, tour)
    controller.start()
    try:
        qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=1000)
        emitter.fired.emit(None)
        assert not controller._coach_mark.isVisible()
        qtbot.waitUntil(lambda: controller._current_step().step_id == "second", timeout=1000)
        qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=1000)
    finally:
        controller.abort()


def test_tuple_target_unpacks_widget_and_rect(main_window, qtbot):
    from PySide6.QtCore import QRect
    from SciQLop.components.onboarding.ui.tour_controller import TourController

    rect = QRect(1, 2, 3, 4)
    tour = _make_tour("t5", [_make_step("with_rect", lambda mw, ctx: (_side_tab(mw), rect))])
    controller = TourController(main_window, tour)
    controller.start()
    try:
        qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=1000)
        assert controller._coach_mark._target_local_rect == rect
    finally:
        controller.abort()


def test_later_step_resolver_reads_earlier_step_context(main_window, qtbot):
    from SciQLop.components.onboarding.ui.tour_controller import TourController

    emitter = _Emitter()

    def _second_resolver(mw, ctx):
        assert ctx["first"] == "stored"
        return _side_tab(mw)

    tour = _make_tour("t6", [
        _make_step("first", lambda mw, ctx: _side_tab(mw),
                   completion=lambda mw, ctx: (emitter.fired, lambda *a: True)),
        _make_step("second", _second_resolver),
    ])
    controller = TourController(main_window, tour)
    controller.start()
    try:
        qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=1000)
        emitter.fired.emit("stored")
        qtbot.waitUntil(lambda: controller._current_step().step_id == "second", timeout=1000)
    finally:
        controller.abort()


def test_skip_sets_completed_and_hides_overlay(main_window, qtbot):
    from SciQLop.components.onboarding.ui.tour_controller import TourController
    from SciQLop.components.onboarding.backend.settings import OnboardingSettings

    with OnboardingSettings() as s:
        s.completed_tours = {}

    tour = _make_tour("t8", [_make_step("only", lambda mw, ctx: _side_tab(mw))])
    controller = TourController(main_window, tour)
    controller.start()
    qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=1000)

    controller._coach_mark.skip_requested.emit()

    assert not controller._coach_mark.isVisible()
    assert not controller._coach_mark.bubble.isVisible()
    assert OnboardingSettings().completed_tours.get("t8") is True


def test_replaying_after_completion_does_not_double_fire_on_stale_connections(main_window, qtbot):
    """A finished controller must have disconnected its per-step
    completion, or a replay's state gets corrupted by the dead handler."""
    from SciQLop.components.onboarding.ui.tour_controller import TourController

    emitter = _Emitter()
    tour = _make_tour("t9", [
        _make_step("first", lambda mw, ctx: _side_tab(mw),
                   completion=lambda mw, ctx: emitter.fired),
        _make_step("second", lambda mw, ctx: _side_tab(mw)),
    ])

    first = TourController(main_window, tour)
    first.start()
    qtbot.waitUntil(lambda: first._coach_mark.isVisible(), timeout=1000)
    first.abort()
    assert first.is_finished is True

    second = TourController(main_window, tour)
    second.start()
    try:
        qtbot.waitUntil(lambda: second._coach_mark.isVisible(), timeout=1000)
        emitter.fired.emit(object())
        qtbot.waitUntil(lambda: second._current_step().step_id == "second", timeout=1000)
        assert second._step_index == 1
    finally:
        second.abort()


def test_finish_sets_is_finished_and_disposes_coach_mark_bubble_and_controller(main_window, qtbot):
    import shiboken6
    from SciQLop.components.onboarding.ui.tour_controller import TourController

    tour = _make_tour("t10", [_make_step("only", lambda mw, ctx: _side_tab(mw))])
    controller = TourController(main_window, tour)
    controller.start()
    qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=1000)

    coach_mark = controller._coach_mark
    bubble = coach_mark.bubble
    assert controller.is_finished is False

    controller.abort()

    assert controller.is_finished is True
    qtbot.waitUntil(lambda: not shiboken6.isValid(coach_mark), timeout=1000)
    qtbot.waitUntil(lambda: not shiboken6.isValid(bubble), timeout=1000)
    qtbot.waitUntil(lambda: not shiboken6.isValid(controller), timeout=1000)


def test_deferred_cleanup_tolerates_coach_mark_and_controller_already_destroyed(
        main_window, qtbot, monkeypatch):
    import shiboken6
    from SciQLop.components.onboarding.ui import tour_controller as tc_mod
    from SciQLop.components.onboarding.ui.tour_controller import TourController

    captured = {}
    monkeypatch.setattr(tc_mod.QTimer, "singleShot", lambda _delay, fn: captured.update(fn=fn))

    tour = _make_tour("t11", [_make_step("only", lambda mw, ctx: _side_tab(mw))])
    controller = TourController(main_window, tour)
    controller.start()
    qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=1000)

    coach_mark = controller._coach_mark
    controller.abort()
    assert "fn" in captured

    coach_mark.deleteLater()
    controller.deleteLater()
    qtbot.waitUntil(lambda: not shiboken6.isValid(coach_mark), timeout=1000)
    qtbot.waitUntil(lambda: not shiboken6.isValid(controller), timeout=1000)

    captured["fn"]()  # must not raise RuntimeError: Internal C++ object already deleted


def test_target_destroyed_mid_step_aborts_tour_without_crash(qapp, sciqlop_resources, qtbot):
    """Fires from inside the target's own destructor (see
    docs/qt-lifetime-patterns.md): aborting is the only safe reaction.
    Uses a disposable main window because a widget gets destroyed."""
    import shiboken6
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    from SciQLop.components.onboarding.ui.tour_controller import TourController
    from SciQLop.components.onboarding.backend.settings import OnboardingSettings

    with OnboardingSettings() as s:
        s.completed_tours = {}

    mw = SciQLopMainWindow()
    mw.show()
    try:
        target = QPushButton("doomed", mw)
        target.show()
        tour = _make_tour("t12", [_make_step("only", lambda mw_, ctx: target)])
        controller = TourController(mw, tour)
        controller.start()
        qtbot.waitUntil(lambda: controller._coach_mark.isVisible(), timeout=2000)

        target.deleteLater()
        qtbot.waitUntil(lambda: OnboardingSettings().completed_tours.get("t12") is True, timeout=2000)
        coach_mark = controller._coach_mark
        assert not shiboken6.isValid(coach_mark) or not coach_mark.isVisible()
    finally:
        mw.close()
