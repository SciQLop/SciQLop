"""Background work where only the answer to the last request matters: a search as one types, a
preview. One worker thread; an answer to an older request is dropped. The job gets plain data and
must not touch Qt objects of the GUI thread; its answer comes back on the GUI thread."""
from __future__ import annotations

import itertools
from typing import Any, Callable

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Answer(QObject):
    ready = Signal(int, object, object)  # request number, result, error text (None when it worked)


class _Job(QRunnable):
    def __init__(self, number: int, work: Callable[[], Any], answer: _Answer):
        super().__init__()
        self._number, self._work, self._answer = number, work, answer

    def run(self):
        try:
            self._answer.ready.emit(self._number, self._work(), None)
        except Exception as error:  # said to the caller, on the GUI thread
            self._answer.ready.emit(self._number, None, str(error))


class LatestOnly(QObject):
    done = Signal(object)   # the result of the last request
    failed = Signal(str)    # why the last request failed

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._numbers = itertools.count(1)
        self._last = 0
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        self._answer = _Answer(self)
        self._answer.ready.connect(self._on_ready)

    def submit(self, work: Callable[[], Any]) -> None:
        self._last = next(self._numbers)
        self._pool.start(_Job(self._last, work, self._answer))

    def _on_ready(self, number: int, result, error) -> None:
        if number != self._last:
            return
        self.failed.emit(error) if error is not None else self.done.emit(result)

    def stop(self) -> None:
        """Drops any answer still to come, then waits for the job in flight."""
        self._last = -1
        self._pool.waitForDone()
