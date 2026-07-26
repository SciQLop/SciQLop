import numpy as np
from multiprocessing import shared_memory
from SciQLop.components.plotting.backend.remote.protocol import pack_arrays, total_nbytes
import SciQLop.components.plotting.backend.remote.channel as channel_module
from SciQLop.components.plotting.backend.remote.channel import RemoteChannel


class FakePipeline:
    """Mimics SciQLopColorMap's real retention: holds the CURRENT views
    (like its _dataHolder member) until the next set_data() call replaces
    them, so a superseded segment's views become collectible right at
    supersession -- unless something is ALSO separately retaining them
    (retain_extra), mimicking an in-flight async resample job's own
    shared_ptr copy, which keeps its buffer alive independently of whatever
    the "current" generation has since become."""
    def __init__(self, retain_extra=False):
        self.calls = []
        self._current = None
        self.retain_extra = retain_extra
        self._extra_retained = []

    def set_data(self, *views):
        # Record shapes only (not the arrays themselves) -- self.calls is for
        # test introspection and must not itself become an unbounded, ever-
        # growing extra reference that defeats what this fake exists to test.
        self.calls.append(tuple(v.shape for v in views))
        self._current = views  # replaces (and releases) whatever was current
        if self.retain_extra:
            self._extra_retained.append(views)

    def release_oldest_extra(self):
        self._extra_retained.pop(0)


class FakeTransport:
    def __init__(self):
        self.requests = []
        self.frees = []
    def send_request(self, channel_id, req_id, start, stop, knobs):
        self.requests.append((channel_id, req_id, start, stop, knobs))
    def send_free(self, channel_id, name):
        self.frees.append((channel_id, name))
    def release(self, channel_id):
        pass


def _make_segment(arrays):
    nbytes = total_nbytes(arrays)
    shm = shared_memory.SharedMemory(create=True, size=nbytes, track=False)
    layout = pack_arrays(shm.buf, arrays)
    return shm.name, layout, shm  # keep shm alive in caller


def test_data_requested_assigns_monotonic_req_ids():
    t = FakeTransport()
    ch = RemoteChannel(pipeline=FakePipeline(), channel_id=5, transport=t)
    ch.on_data_requested_values(0.0, 1.0)
    ch.on_data_requested_values(1.0, 2.0)
    assert [r[1] for r in t.requests] == [1, 2]


def test_current_result_sets_data_and_frees_previous_on_supersede():
    pipe, t = FakePipeline(), FakeTransport()
    ch = RemoteChannel(pipeline=pipe, channel_id=5, transport=t)
    ch.on_data_requested_values(0.0, 1.0)  # req 1 -> latest
    n1, l1, s1 = _make_segment([np.array([0.0, 1.0]), np.array([1.0])])
    n2, l2, s2 = _make_segment([np.array([1.0, 2.0]), np.array([2.0])])
    ch.on_result(1, n1, l1, 1)
    assert t.frees == []                    # nothing to supersede yet
    ch.on_data_requested_values(1.0, 2.0)  # req 2 -> latest
    ch.on_result(2, n2, l2, 2)
    assert (5, n1) in t.frees               # first segment released
    assert len(pipe.calls) == 2
    s1.unlink(); s2.unlink()


def test_previous_segment_not_released_while_still_referenced(monkeypatch):
    # SciQLopPlots' async resample pipeline (NeoQCP's QCPAsyncPipeline, used
    # by colormaps and line graphs alike) does not finish reading a buffer
    # synchronously inside set_data() -- set_data() only queues a background
    # job and returns immediately, and the buffer stays readable
    # synchronously afterward too (e.g. crosshair/tooltip hover). There is no
    # Qt signal that reliably reports "every reader is done" -- verified
    # empirically that QCPAsyncPipeline's busy()/busy_changed() can go idle
    # while a same-generation continuation job is still being dispatched, so
    # gating on it still let a real SIGSEGV through (reproduced twice with
    # SciQLopColorMapRemote on rapidly-updating I-LOFAR radio spectrogram
    # data, once against busy()-gated code). The only reliable signal is the
    # buffer's own Python refcount, since SciQLopColorMap's C++ shared_ptr
    # chain already correctly keeps a view's Py_buffer export alive for
    # exactly as long as any C++ reference -- including an in-flight
    # resample job's own copy -- needs it.
    closed_names = []
    orig_close = shared_memory.SharedMemory.close

    def spy_close(self):
        closed_names.append(self.name)
        orig_close(self)

    monkeypatch.setattr(shared_memory.SharedMemory, "close", spy_close)

    pipe, t = FakePipeline(retain_extra=True), FakeTransport()
    ch = RemoteChannel(pipeline=pipe, channel_id=5, transport=t)
    ch.on_data_requested_values(0.0, 1.0)  # req 1 -> latest
    n1, l1, s1 = _make_segment([np.array([0.0, 1.0]), np.array([1.0])])
    ch.on_result(1, n1, l1, 1)  # pipe retains these views -- simulates an in-flight C++ reader

    ch.on_data_requested_values(1.0, 2.0)  # req 2 -> latest
    n2, l2, s2 = _make_segment([np.array([1.0, 2.0]), np.array([2.0])])
    ch.on_result(2, n2, l2, 1)
    assert n1 not in closed_names, "must not unmap segment 1 while still referenced"
    assert (5, n1) not in t.frees

    pipe.release_oldest_extra()  # simulates the in-flight reader finally dropping its reference
    assert n1 in closed_names
    assert (5, n1) in t.frees
    s1.unlink()
    s2.unlink()


def test_duplicate_result_for_held_segment_is_not_freed():
    # A re-delivered RESULT naming the segment we currently hold must not be
    # FREEd back to the worker — it is still the live buffer SciQLopPlots reads.
    pipe, t = FakePipeline(), FakeTransport()
    ch = RemoteChannel(pipeline=pipe, channel_id=5, transport=t)
    ch.on_data_requested_values(0.0, 1.0)   # req 1 -> latest
    n1, l1, s1 = _make_segment([np.array([0.0]), np.array([1.0])])
    ch.on_result(1, n1, l1, 2)              # accept, held = n1
    ch.on_result(1, n1, l1, 2)              # duplicate, same segment, req_id == latest
    assert (5, n1) not in t.frees           # the held/live segment must NOT be freed
    s1.unlink()


def test_stale_result_is_dropped_and_immediately_freed():
    pipe, t = FakePipeline(), FakeTransport()
    ch = RemoteChannel(pipeline=pipe, channel_id=5, transport=t)
    ch.on_data_requested_values(0.0, 1.0)  # req 1
    ch.on_data_requested_values(1.0, 2.0)  # req 2 -> latest
    n1, l1, s1 = _make_segment([np.array([0.0]), np.array([1.0])])
    ch.on_result(1, n1, l1, 2)              # stale (1 < 2)
    assert pipe.calls == []                 # never set_data
    assert (5, n1) in t.frees               # freed immediately
    s1.unlink()


def test_set_knobs_is_included_in_next_request():
    t = FakeTransport()
    ch = RemoteChannel(pipeline=FakePipeline(), channel_id=5, transport=t)
    ch.set_knobs({"gain": 2.0})
    ch.on_data_requested_values(0.0, 1.0)
    assert t.requests[-1] == (5, 1, 0.0, 1.0, {"gain": 2.0})


def test_default_knobs_is_empty_dict():
    t = FakeTransport()
    ch = RemoteChannel(pipeline=FakePipeline(), channel_id=5, transport=t)
    ch.on_data_requested_values(0.0, 1.0)
    assert t.requests[-1] == (5, 1, 0.0, 1.0, {})


class _FakeAsyncTracer:
    def __init__(self, monkeypatch):
        self.begins = []
        self.ends = []
        self._next_handle = 0
        monkeypatch.setattr(channel_module.tracing, "async_begin", self._begin)
        monkeypatch.setattr(channel_module.tracing, "async_end", self._end)

    def _begin(self, name, cat=""):
        self._next_handle += 1
        self.begins.append((self._next_handle, name, cat))
        return self._next_handle

    def _end(self, handle):
        self.ends.append(handle)


def test_async_span_opens_on_request_and_closes_on_result(monkeypatch):
    tracer = _FakeAsyncTracer(monkeypatch)
    pipe, t = FakePipeline(), FakeTransport()
    ch = RemoteChannel(pipeline=pipe, channel_id=5, transport=t)
    ch.on_data_requested_values(0.0, 1.0)
    assert len(tracer.begins) == 1
    assert tracer.ends == []
    n1, l1, s1 = _make_segment([np.array([0.0]), np.array([1.0])])
    ch.on_result(1, n1, l1, 2)
    assert tracer.ends == [tracer.begins[0][0]]
    s1.unlink()


def test_async_span_closes_on_empty(monkeypatch):
    tracer = _FakeAsyncTracer(monkeypatch)
    ch = RemoteChannel(pipeline=FakePipeline(), channel_id=5, transport=FakeTransport())
    ch.on_data_requested_values(0.0, 1.0)
    ch.on_empty(1)
    assert tracer.ends == [tracer.begins[0][0]]


def test_async_span_closes_on_error(monkeypatch):
    tracer = _FakeAsyncTracer(monkeypatch)
    ch = RemoteChannel(pipeline=FakePipeline(), channel_id=5, transport=FakeTransport())
    ch.on_data_requested_values(0.0, 1.0)
    ch.on_error(1, "boom")
    assert tracer.ends == [tracer.begins[0][0]]


def test_superseding_request_closes_previous_async_span(monkeypatch):
    tracer = _FakeAsyncTracer(monkeypatch)
    ch = RemoteChannel(pipeline=FakePipeline(), channel_id=5, transport=FakeTransport())
    ch.on_data_requested_values(0.0, 1.0)   # req 1, never resolved
    ch.on_data_requested_values(1.0, 2.0)   # supersedes req 1
    assert len(tracer.begins) == 2
    assert tracer.ends == [tracer.begins[0][0]]   # req 1's span closed, req 2's still open
    ch.on_empty(2)
    assert tracer.ends == [tracer.begins[0][0], tracer.begins[1][0]]
