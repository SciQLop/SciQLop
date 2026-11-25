"""Background work where only the answer to the last request matters: a search as one types, a
preview. Jobs run on a small shared pool; an answer to an older request is dropped. The job gets plain data and
must not touch Qt objects of the GUI thread; its answer comes back on the GUI thread."""
from __future__ import annotations

import itertools
import weakref
from typing import Any, Callable

import shiboken6
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Answers(QObject):
    """Lives for the session on the GUI thread: answers reach it queued, and it hands each to the
    LatestOnly that asked, if that one is still there."""
    ready = Signal(int, object, object)  # request number, result, error text (None when it worked)

    def __init__(self):
        super().__init__()
        self._asking: dict[int, weakref.ref] = {}
        self.ready.connect(self._deliver)

    def expect(self, number: int, asking: "LatestOnly") -> None:
        self._asking[number] = weakref.ref(asking)

    def _deliver(self, number: int, result, error) -> None:
        asking = self._asking.pop(number, lambda: None)()
        if asking is not None and shiboken6.isValid(asking):
            asking._on_ready(number, result, error)


_shared: tuple[QThreadPool, _Answers] | None = None


def _pool_and_answers() -> tuple[QThreadPool, _Answers]:
    """One pool and one answer emitter for every LatestOnly, kept for the session: a job still
    running when its LatestOnly goes emits on an object that is still there, and nobody waits for it."""
    global _shared
    if _shared is None:
        pool = QThreadPool()
        pool.setMaxThreadCount(2)
        _shared = pool, _Answers()
    return _shared


_numbers = itertools.count(1)  # unique across LatestOnly instances: they share _Answers


class _Job(QRunnable):
    def __init__(self, number: int, work: Callable[[], Any], answers: _Answers):
        super().__init__()
        self._number, self._work, self._answers = number, work, answers

    def run(self):
        try:
            self._answers.ready.emit(self._number, self._work(), None)
        except Exception as error:  # said to the caller, on the GUI thread
            self._answers.ready.emit(self._number, None, str(error))


class LatestOnly(QObject):
    done = Signal(object)   # the result of the last request
    failed = Signal(str)    # why the last request failed

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._last = 0

    def submit(self, work: Callable[[], Any]) -> None:
        pool, answers = _pool_and_answers()
        self._last = next(_numbers)
        answers.expect(self._last, self)
        pool.start(_Job(self._last, work, answers))

    def _on_ready(self, number: int, result, error) -> None:
        if number != self._last:
            return
        self.failed.emit(error) if error is not None else self.done.emit(result)

    def stop(self) -> None:
        """Drops any answer still to come; the job in flight ends on its own, unheard."""
        self._last = -1
