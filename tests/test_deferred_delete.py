import pytest
import shiboken6
from PySide6.QtWidgets import QWidget

from SciQLop.core.ui.deferred_delete import delete_when_idle


def test_widget_is_kept_while_busy_and_deleted_once_idle(qtbot):
    state = {"busy": True}
    w = QWidget()
    delete_when_idle(w, lambda _: state["busy"], poll_ms=10, max_wait_s=30)

    qtbot.wait(100)
    assert shiboken6.isValid(w)

    state["busy"] = False
    qtbot.waitUntil(lambda: not shiboken6.isValid(w), timeout=2000)


def test_widget_is_deleted_immediately_when_not_busy(qtbot):
    w = QWidget()
    delete_when_idle(w, lambda _: False, poll_ms=10, max_wait_s=30)

    qtbot.waitUntil(lambda: not shiboken6.isValid(w), timeout=2000)


def test_a_graph_stuck_busy_does_not_keep_the_widget_forever(qtbot):
    w = QWidget()
    delete_when_idle(w, lambda _: True, poll_ms=10, max_wait_s=0.2)

    qtbot.waitUntil(lambda: not shiboken6.isValid(w), timeout=3000)


@pytest.mark.parametrize("error", [RuntimeError("Internal C++ object already deleted"),
                                   AttributeError("bug in the probe")])
def test_a_probe_that_raises_counts_as_idle_instead_of_firing_again_and_again(qtbot, error):
    def failing_probe(_):
        raise error

    w = QWidget()
    delete_when_idle(w, failing_probe, poll_ms=10, max_wait_s=30)

    with qtbot.captureExceptions() as exceptions:
        qtbot.waitUntil(lambda: not shiboken6.isValid(w), timeout=2000)

    assert exceptions == []


def test_a_widget_deleted_by_someone_else_is_left_alone(qtbot):
    w = QWidget()
    delete_when_idle(w, lambda _: True, poll_ms=10, max_wait_s=30)

    with qtbot.captureExceptions() as exceptions:
        shiboken6.delete(w)
        qtbot.wait(100)

    assert exceptions == []
