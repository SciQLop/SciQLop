"""Runtime tracer for SciQLop. Re-exports `SciQLop.core.tracing`.

Open generated traces in https://ui.perfetto.dev/

Quick start (from the embedded Jupyter console)
-----------------------------------------------
>>> from SciQLop.user_api import tracing
>>> with tracing.session("/tmp/slow_pan.json"):
...     panel.time_range = TimeRange(t0, t1)   # reproduce the slow path
>>> # open /tmp/slow_pan.json in https://ui.perfetto.dev/

Or set the env var SCIQLOP_TRACE=/tmp/trace.json before launching SciQLop —
that auto-enables tracing on process start (handled by the SciQLopPlots side).
"""
from SciQLop.core.tracing import (  # noqa: F401
    enable, disable, flush, is_enabled, set_thread_name,
    counter, async_begin, async_end,
    zone, session, traced,
)

__all__ = [
    "enable", "disable", "flush", "is_enabled", "set_thread_name",
    "counter", "async_begin", "async_end",
    "zone", "session", "traced",
]
