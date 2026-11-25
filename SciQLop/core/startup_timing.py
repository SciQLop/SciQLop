"""Startup timings, printed to stderr (so into the session log) when SCIQLOP_STARTUP_TIMINGS is set:
how long each phase took, and each stall of the GUI thread over 100 ms after the window shows, with
where it was. Machines differ: this is what to ask for when startup feels slow on someone else's.

Without the variable, a phase costs one dictionary lookup and nothing is watched."""
from __future__ import annotations

import collections
import os
import sys
import threading
import time
import traceback
from contextlib import contextmanager

ENV = "SCIQLOP_STARTUP_TIMINGS"
STALL_S = 0.1
_START = time.perf_counter()


def enabled() -> bool:
    return bool(os.environ.get(ENV))


def say(message: str) -> None:
    if enabled():
        print(f"[startup] {message}", file=sys.stderr, flush=True)


def mark(name: str) -> None:
    say(f"{name} ({time.perf_counter() - _START:.2f}s from start)")


@contextmanager
def phase(name: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        now = time.perf_counter()
        say(f"{name}: {now - start:.2f}s ({now - _START:.2f}s from start)")


IN_QT = "in Qt (no Python running)"
_EVENT_LOOP = ("run_forever", "exec", "exec_")


def _where(thread_id: int) -> str:
    """The innermost frames of SciQLop or a library the thread is in; IN_QT when it is in the event
    loop itself: Qt's C++ (layout, painting, a web view) is blocking, not Python."""
    frame = sys._current_frames().get(thread_id)
    stack = traceback.extract_stack(frame) if frame is not None else []
    if not stack or stack[-1].name in _EVENT_LOOP:
        return IN_QT
    ours = [f for f in stack if "SciQLop" in f.filename or "site-packages" in f.filename] or stack
    return " <- ".join(f"{os.path.basename(f.filename)}:{f.lineno} {f.name}" for f in reversed(ours[-4:]))


class GuiWatch:
    """A 20 ms heartbeat on the GUI thread; a watcher thread notes where the GUI thread is while the
    heartbeat is late, and each late beat prints the stall and its most seen place."""

    def __init__(self, seconds: float):
        from PySide6.QtCore import QTimer
        self.stalls: list[float] = []
        self._gui = threading.get_ident()
        self._shown = self._last = time.perf_counter()
        self._samples: list[str] = []
        self._lock = threading.Lock()
        self._running = True
        self._timer = QTimer()
        self._timer.setInterval(20)
        self._timer.timeout.connect(self._beat)
        self._timer.start()
        QTimer.singleShot(int(seconds * 1000), self.stop)
        threading.Thread(target=self._sample, name="startup-gui-watch", daemon=True).start()

    def stop(self) -> None:
        self._running = False
        self._timer.stop()

    def _beat(self) -> None:
        now = time.perf_counter()
        gap, self._last = now - self._last, now
        with self._lock:
            samples, self._samples = self._samples, []
        if gap < STALL_S:
            return
        self.stalls.append(gap)
        where = collections.Counter(samples).most_common(1)
        place = where[0][0] if where else IN_QT
        say(f"GUI blocked {gap * 1000:.0f} ms, {now - self._shown:.2f}s after show: {place}")

    def _sample(self) -> None:
        while self._running:
            time.sleep(0.02)
            if time.perf_counter() - self._last > STALL_S:
                where = _where(self._gui)
                with self._lock:
                    self._samples.append(where)


def watch_gui(seconds: float = 30) -> GuiWatch | None:
    """Call on the GUI thread once the window shows."""
    return GuiWatch(seconds) if enabled() else None
