"""Per-graph main-side state machine driving one SciQLopPlots remote channel.

Owns req_id assignment, stale-reply dropping, and the consumer-side segment
lifetime: a superseded segment's local mmap is closed and FREEd back to the
worker only once every numpy view SciQLopPlots was handed for it is truly
gone -- Python refcount reaching zero, including any C++-side Py_buffer
export. SciQLopPlots' plottables (colormaps, line graphs) resample new data
on a background thread; set_data() only queues that job and returns once
it's merely scheduled, not once it has run, and the buffer stays readable
synchronously afterward too (e.g. crosshair/tooltip hover reads a colormap's
raw data source directly, at any later time, not just during the resample
job). There is no Qt signal that reliably reports "every reader is done" --
QCPAsyncPipeline's busy()/busy_changed() can go idle while a same-generation
continuation job is still being dispatched (verified: watching it still let
a background job read a segment this class had already closed). The
underlying C++ shared_ptr chain (SciQLopColorMap's _dataHolder) already
correctly keeps a view's Py_buffer export alive for exactly as long as any
C++ reference -- including an in-flight resample job's own copy -- needs
it; weakref.finalize on the views handed into set_data() rides that same
guarantee instead of re-deriving it. The views themselves pin the mapping
(protocol.unpack_arrays builds them with np.frombuffer), so an early
SharedMemory.close() raises BufferError instead of unmapping memory a
reader still uses -- which used to be an immediate SIGSEGV."""
from __future__ import annotations

import logging
import weakref
from multiprocessing import shared_memory
from typing import Optional

from PySide6.QtCore import QTimer

from SciQLop.core import tracing
from .protocol import unpack_arrays

log = logging.getLogger(__name__)


def _close_once_unpinned(shm: shared_memory.SharedMemory) -> None:
    try:
        shm.close()
    except BufferError:
        # The last view is mid-deallocation: numpy runs weakref callbacks before
        # it drops the buffer export that pins the mapping. Close right after.
        QTimer.singleShot(0, shm.close)


def _last_line(tb: str) -> str:
    """The exception line of a formatted traceback, e.g. 'ValueError: bad input'."""
    return tb.strip().splitlines()[-1] if tb.strip() else "remote data source error"


class RemoteChannel:
    def __init__(self, pipeline, channel_id: int, transport, colored: bool = False,
                 name: str = "", error_reporter=None):
        self._pipeline = pipeline
        self.error_reporter = error_reporter  # shows errors on the plot; see _PlotErrorReporter
        self._colored = colored
        self._name = name or f"channel {channel_id}"
        self.channel_id = channel_id
        self._transport = transport
        self._latest_req_id = 0
        self._held: Optional[shared_memory.SharedMemory] = None
        self._held_name: Optional[str] = None
        self._knobs: dict = {}
        self._async_handle: Optional[int] = None  # spans request -> reply

    # --- outgoing -----------------------------------------------------------
    def set_knobs(self, knobs: dict) -> None:
        self._knobs = dict(knobs)

    def on_data_requested_values(self, start: float, stop: float) -> None:
        if self._async_handle is not None:
            # Superseded before it ever got a reply -- close its span so it
            # doesn't stay open forever (worker.py only ever replies to the
            # latest request per channel; this one never will get one).
            tracing.async_end(self._async_handle)
        self._latest_req_id += 1
        self._async_handle = tracing.async_begin(
            f"remote.request[channel={self.channel_id}]", cat="remote")
        self._transport.send_request(self.channel_id, self._latest_req_id, start, stop, self._knobs)

    def on_data_requested(self, rng) -> None:
        self.on_data_requested_values(rng.start(), rng.stop())

    # --- incoming -----------------------------------------------------------
    def on_result(self, req_id: int, shm_name: str, layout, arity: int) -> None:
        if req_id < self._latest_req_id:
            self._transport.send_free(self.channel_id, shm_name)   # stale: drop + free
            return
        self._close_async_span(req_id)
        if shm_name == self._held_name:
            # Re-delivered RESULT naming the segment we already hold: a second
            # independent mmap of it would release (and FREE) on its own
            # schedule, possibly before the original mapping's in-flight
            # reader is done with it. Nothing to do -- we're already using it.
            return
        shm = shared_memory.SharedMemory(name=shm_name, create=False, track=False)
        views = unpack_arrays(shm.buf, layout)
        delivered = self._deliver(views, arity)
        self._register_release(shm, shm_name, views)
        if delivered:
            # A rejected segment is freed as soon as its views die (right
            # after this returns); holding it would drop the worker's next
            # result that reuses it as a "re-delivery".
            self._held, self._held_name = shm, shm_name

    def _deliver(self, views, arity: int) -> bool:
        if self._colored and len(views) == arity + 1:
            self._pipeline.set_data_colored(list(views[:-1]), views[-1])
            self._clear_error()
            return True
        if not self._colored and len(views) == arity:
            self._pipeline.set_data(*views)
            self._clear_error()
            return True
        if self._colored:
            self._report_error("declared colored=True but did not return Colored(...)")
        else:
            self._report_error("returned Colored(...) but was not declared with colored=True")
        self._pipeline.request_done()
        return False

    def on_empty(self, req_id: int) -> None:
        self._close_async_span(req_id)
        if req_id == self._latest_req_id:  # a stale reply must not end the newer request
            self._clear_error()
            self._pipeline.request_done()

    def on_error(self, req_id: int, tb: str) -> None:
        self._close_async_span(req_id)
        log.error("remote data source error (channel %s):\n%s", self.channel_id, tb)
        if req_id == self._latest_req_id:
            if self.error_reporter is not None:
                self.error_reporter.report(_last_line(tb))
            self._pipeline.request_done()

    def _report_error(self, message: str) -> None:
        log.error("%s: %s", self._name, message)
        if self.error_reporter is not None:
            self.error_reporter.report(message)

    def _clear_error(self) -> None:
        if self.error_reporter is not None:
            self.error_reporter.clear()

    def _close_async_span(self, req_id: int) -> None:
        if req_id == self._latest_req_id and self._async_handle is not None:
            tracing.async_end(self._async_handle)
            self._async_handle = None

    # --- lifetime -----------------------------------------------------------
    def _register_release(self, shm, name, views) -> None:
        # Fires once ALL views into this segment are gone -- Python-side and,
        # via SciQLopColorMap's _dataHolder chain, C++-side (any in-flight
        # resample job holds its own reference until its transform() call
        # returns). Whichever thread drops the last one, SciQLopPyBuffer's
        # own release path defers a non-GIL-thread drop onto the main
        # thread's next GIL acquisition, so this callback always actually
        # runs there -- safe to touch the Qt transport from it.
        remaining = [len(views)]

        def _on_view_released():
            remaining[0] -= 1
            if remaining[0] == 0:
                self._transport.send_free(self.channel_id, name)
                _close_once_unpinned(shm)

        for v in views:
            weakref.finalize(v, _on_view_released)

    def dispose(self) -> None:
        # The held segment is left to its _register_release finalizer: the
        # graph's destroyed signal fires while its plot's resample job may
        # still be reading the segment, and unmapping it then is a SIGSEGV.
        self._transport.release(self.channel_id)
        self._held, self._held_name = None, None
