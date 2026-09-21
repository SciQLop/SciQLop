import time
from typing import Callable

import shiboken6
from PySide6.QtCore import QObject, QTimer

from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)

# Kept alive here: the timers have no parent because the widget they watch is parentless.
_pending: set[QTimer] = set()


def _still_busy(is_busy: Callable[[QObject], bool], widget: QObject) -> bool:
    try:
        return is_busy(widget)
    except Exception:
        # A raising probe would otherwise fire on every poll until the deadline
        log.warning("busy probe failed, not waiting for %r any longer", widget, exc_info=True)
        return False


def delete_when_idle(widget: QObject, is_busy: Callable[[QObject], bool],
                     poll_ms: int = 250, max_wait_s: float = 1800.0) -> None:
    """`widget.deleteLater()`, postponed while `is_busy(widget)` is true.

    Destroying a SciQLopPlots graph joins its data-provider thread on the GUI thread, so
    while a Python callback is still running (e.g. blocked in a long HTTP read) the whole
    application freezes until it returns. Keeping the already hidden widget alive until the
    fetch is over keeps the GUI responsive (GH #137).

    simplify: polls instead of following each graph's busy_changed. Gives up waiting after
    `max_wait_s`, so a graph stuck busy cannot keep a hidden widget alive forever, and pays
    the join then.
    """
    deadline = time.monotonic() + max_wait_s
    timer = QTimer()
    timer.setInterval(poll_ms)

    def check() -> None:
        if not shiboken6.isValid(widget):
            finish()
        elif time.monotonic() >= deadline or not _still_busy(is_busy, widget):
            widget.deleteLater()
            finish()

    def finish() -> None:
        timer.stop()
        _pending.discard(timer)
        timer.deleteLater()

    timer.timeout.connect(check)
    _pending.add(timer)
    timer.start()
