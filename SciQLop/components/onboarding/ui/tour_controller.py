import shiboken6
from PySide6.QtCore import QObject, QTimer

from SciQLop.components.onboarding.backend.tour import Tour, TourStep
from SciQLop.components.onboarding.backend.registry import get_tour
from SciQLop.components.onboarding.backend.settings import OnboardingSettings
from SciQLop.components.onboarding.ui.coach_mark import CoachMark
from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)


def _log_safely(message: str, level: str = "info") -> None:
    # The logger's own Qt signal can already be gone when this fires from
    # an application shutdown cascade; a log call must never crash the app.
    try:
        getattr(log, level)(message)
    except RuntimeError:
        pass


def _normalize_completion(result):
    """A completion returns a bare Signal, a (Signal, predicate) pair, or
    None; give the controller one shape to connect."""
    if result is None:
        return None
    if isinstance(result, tuple):
        return result
    return result, (lambda *args: True)


def _store_completion_args(context: dict, step_id: str, args: tuple) -> None:
    if len(args) == 0:
        context[step_id] = True
    elif len(args) == 1:
        context[step_id] = args[0]
    else:
        context[step_id] = args


def _split_target(target):
    if isinstance(target, tuple):
        return target
    return target, None


def _is_showable(widget) -> bool:
    return widget is not None and shiboken6.isValid(widget) and widget.isVisible()


class TourController(QObject):
    """Walks a Tour against a live main window, one CoachMark step at a
    time. A step advances on its completion signal or on Next, Back
    re-enters the previous step, and a step whose target is missing or
    hidden is skipped instead of ending the tour. Only Skip or Escape end it.

    Each step's completion connection is torn down when the step is left:
    the main window outlives any tour run, so a stale handler would keep
    firing into a finished controller on a later replay."""

    def __init__(self, main_window, tour: Tour):
        super().__init__(main_window)
        self._main_window = main_window
        self._tour = tour
        self._coach_mark = CoachMark(main_window)
        self._coach_mark.next_clicked.connect(self._advance)
        self._coach_mark.back_clicked.connect(self._go_back)
        self._coach_mark.skip_requested.connect(self.abort)
        self._step_index = 0
        self._context: dict = {}
        self._active_signal = None
        self._active_slot = None
        self._finished = False
        self._moving = False

    @property
    def is_finished(self) -> bool:
        return self._finished

    def _current_step(self) -> TourStep:
        return self._tour.steps[self._step_index]

    def start(self) -> None:
        self._step_index = 0
        self._enter_step(+1)

    def abort(self) -> None:
        self._disconnect_active_completion()
        self._finish()

    def _finish(self) -> None:
        if self._finished:
            return
        self._finished = True
        self._detach_coach_mark_signals()
        self._coach_mark.hide()
        with OnboardingSettings() as s:
            s.completed_tours[self._tour.id] = True
        self._dispose()

    def _dispose(self) -> None:
        coach_mark = self._coach_mark

        def _cleanup():
            if shiboken6.isValid(coach_mark):
                coach_mark.dispose()
                coach_mark.deleteLater()
            if shiboken6.isValid(self):
                self.deleteLater()

        QTimer.singleShot(0, _cleanup)

    def _detach_coach_mark_signals(self) -> None:
        for signal, slot in (
                (self._coach_mark.next_clicked, self._advance),
                (self._coach_mark.back_clicked, self._go_back),
                (self._coach_mark.skip_requested, self.abort)):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass

    def _enter_step(self, direction: int) -> None:
        """Show the step at _step_index, walking in `direction` past any
        step whose target can't be shown right now."""
        self._moving = False
        if self._finished:
            return
        steps = self._tour.steps
        while 0 <= self._step_index < len(steps):
            step = steps[self._step_index]
            target = step.resolver(self._main_window, self._context) if step.resolver else None
            widget, rect = _split_target(target)
            if step.resolver is None or _is_showable(widget):
                self._show_step(step, widget, rect)
                return
            _log_safely(f"Onboarding step {step.step_id!r}: target not available, skipping",
                        level="warning")
            self._step_index += direction
        if self._step_index < 0:
            self._step_index = 0
            self._enter_step(+1)
        else:
            self._finish()

    def _show_step(self, step: TourStep, widget, rect) -> None:
        index, count = self._step_index, len(self._tour.steps)
        self._coach_mark.show_step(
            widget, step.title, step.body, rect=rect,
            progress=f"{index + 1} / {count}",
            can_go_back=index > 0,
            next_label="Done" if index == count - 1 else "Next")
        self._connect_completion(step)

    def _connect_completion(self, step: TourStep) -> None:
        self._disconnect_active_completion()
        raw = step.completion(self._main_window, self._context) if step.completion else None
        normalized = _normalize_completion(raw)
        if normalized is None:
            return
        signal, predicate = normalized

        def _slot(*args):
            if predicate(*args):
                _store_completion_args(self._context, step.step_id, args)
                self._advance()

        self._active_signal, self._active_slot = signal, _slot
        signal.connect(_slot)

    def _disconnect_active_completion(self) -> None:
        if self._active_signal is not None and self._active_slot is not None:
            try:
                self._active_signal.disconnect(self._active_slot)
            except (RuntimeError, TypeError):
                pass
        self._active_signal = None
        self._active_slot = None

    def _leave_step(self) -> None:
        self._disconnect_active_completion()
        self._coach_mark.hide()

    def _advance(self) -> None:
        self._move(+1)

    def _go_back(self) -> None:
        self._move(-1)

    def _move(self, direction: int) -> None:
        # One transition at a time: a repeated Enter or a completion firing
        # twice must not move the index again before the deferred entry
        # ran. The deferral itself matters because a completion can fire
        # from inside a nested event loop (a native drag's QDrag::exec()).
        if self._moving:
            return
        self._moving = True
        self._leave_step()
        self._step_index += direction
        QTimer.singleShot(0, lambda: self._enter_step(direction))


def run_tour(main_window, tour_id: str) -> TourController | None:
    tour = get_tour(tour_id)
    if tour is None:
        _log_safely(f"Onboarding: unknown tour {tour_id!r}, not starting", level="warning")
        return None
    controller = TourController(main_window, tour)
    controller.start()
    return controller
