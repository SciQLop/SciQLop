"""Run Python's cyclic garbage collector on the GUI thread only.

CPython collects on whichever thread trips the allocation threshold. Worker
threads that run Python (tscat driver, kernel, data-provider callbacks) then
finalize Python-owned QObjects that live on the GUI thread; Qt destroys them
from the wrong thread ("QBasicTimer::stop: Failed. Possibly trying to stop
from a different thread") and a later timer tick dereferences freed memory.
Known PyQt/PySide hazard and standard remedy:
https://github.com/napari/napari/issues/1029

Automatic collection is disabled and a GUI-thread timer re-applies CPython's
own per-generation thresholds, so the cadence is unchanged -- only the thread
is pinned.
"""
from __future__ import annotations

import gc

from PySide6.QtCore import QObject, QTimer


class MainThreadGarbageCollector(QObject):
    def __init__(self, interval_ms: int = 250, parent: QObject | None = None):
        super().__init__(parent)
        self._thresholds = gc.get_threshold()
        self._timer = QTimer(self)
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self.collect_if_due)

    def start(self) -> None:
        gc.disable()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        gc.enable()

    def collect_if_due(self) -> None:
        due = [
            generation
            for generation, (count, threshold) in enumerate(zip(gc.get_count(), self._thresholds))
            if threshold and count >= threshold
        ]
        if due:
            gc.collect(max(due))


_collector: MainThreadGarbageCollector | None = None


def install(parent: QObject) -> MainThreadGarbageCollector:
    """Pin cyclic GC to the calling (GUI) thread for the process lifetime."""
    global _collector
    if _collector is None:
        _collector = MainThreadGarbageCollector(parent=parent)
        _collector.start()
    return _collector
