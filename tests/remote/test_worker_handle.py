import json
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import cloudpickle
import pytest
import SciQLop.components.plotting.backend.remote.worker_handle as worker_handle_module
from SciQLop.components.plotting.backend.remote.worker_handle import RemoteWorker
from SciQLop.core import tracing


class CollectingPipeline:
    def __init__(self):
        self.results = []
    def set_data(self, *views):
        self.results.append([np.array(v) for v in views])


def _sin_source(start, stop):
    x = np.linspace(start, stop, 16)
    return (x, np.sin(x))


def test_end_to_end_request_delivers_data(qtbot):
    worker = RemoteWorker(plugin_key="test_plugin")
    worker.start()
    try:
        pipe = CollectingPipeline()
        from SciQLop.components.plotting.backend.remote.channel import RemoteChannel
        ch = RemoteChannel(pipeline=pipe, channel_id=1, transport=worker)
        worker.register_channel(ch)
        worker.install(1, cloudpickle.dumps(_sin_source), arity=2)
        ch.on_data_requested_values(0.0, 6.28)
        qtbot.waitUntil(lambda: len(pipe.results) == 1, timeout=15000)
        x, y = pipe.results[0]
        assert x.shape == (16,)
        np.testing.assert_allclose(y, np.sin(x), atol=1e-6)
    finally:
        worker.shutdown()


def test_health_counters_emitted_around_request_response_cycle(qtbot, monkeypatch):
    calls = []
    monkeypatch.setattr(
        worker_handle_module.tracing, "counter",
        lambda name, value, cat=None: calls.append((name, value, cat)),
    )
    worker = RemoteWorker(plugin_key="test_plugin_counters")
    worker.start()
    try:
        assert ("remote.worker_alive", 1, "remote") in calls
        pipe = CollectingPipeline()
        from SciQLop.components.plotting.backend.remote.channel import RemoteChannel
        ch = RemoteChannel(pipeline=pipe, channel_id=1, transport=worker)
        worker.register_channel(ch)
        worker.install(1, cloudpickle.dumps(_sin_source), arity=2)

        calls.clear()
        ch.on_data_requested_values(0.0, 6.28)
        pending_after_send = [v for n, v, c in calls if n == "remote.pending_requests"]
        assert pending_after_send and pending_after_send[-1] == 1

        qtbot.waitUntil(lambda: len(pipe.results) == 1, timeout=15000)
        names = [c[0] for c in calls]
        assert "remote.last_latency_ms" in names
        pending_after_reply = [v for n, v, c in calls if n == "remote.pending_requests"]
        assert pending_after_reply[-1] == 0
    finally:
        worker.shutdown()
        assert ("remote.worker_alive", 0, "remote") in calls


def test_worker_can_import_callable_from_extra_plugins_folder(qtbot, tmp_path):
    # cloudpickle.dumps/loads here exercises the worker's real IPC path --
    # same single-trust-domain boundary documented in worker.py's module
    # docstring (blob originates from this same SciQLop process over a
    # private pipe, never from an untrusted source).
    #
    # Real bug report: a callable that lives in a SciQLop folder-plugin
    # (extra_plugins_folders / user plugins dir) is loaded via
    # loader.import_from_path(), which registers it into sys.modules
    # WITHOUT ever adding its directory to sys.path -- fine within the
    # main process, but the worker is spawned as a brand-new
    # `sys.executable -m ...` interpreter that never runs SciQLop's
    # plugin loader. Before the fix, cloudpickle.loads() on the worker
    # side raises ModuleNotFoundError trying to resolve the plugin
    # module, which is unhandled in worker.serve() and kills the whole
    # worker subprocess outright. Mirrors the real loader's folder-plugin
    # path exactly (loader.import_from_path) rather than assuming a
    # simplified import mechanism.
    plugin_folder = tmp_path / "extra_plugins"
    plugin_folder.mkdir()
    pkg_dir = plugin_folder / "fake_radio_plugin"
    pkg_dir.mkdir()
    (pkg_dir / "__init__.py").write_text(
        "def make_wave(start, stop):\n"
        "    import numpy as np\n"
        "    x = np.linspace(start, stop, 4)\n"
        "    return (x, x)\n"
    )

    from SciQLop.components.plugins.backend.loader.loader import import_from_path
    from SciQLop.components.plugins.backend.settings import SciQLopPluginsSettings
    module = import_from_path("fake_radio_plugin", str(pkg_dir / "__init__.py"))

    with SciQLopPluginsSettings() as settings:
        settings.extra_plugins_folders = [str(plugin_folder)]
    try:
        worker = RemoteWorker(plugin_key="test_plugin_folder_import")
        worker.start()
        try:
            pipe = CollectingPipeline()
            from SciQLop.components.plotting.backend.remote.channel import RemoteChannel
            ch = RemoteChannel(pipeline=pipe, channel_id=1, transport=worker)
            worker.register_channel(ch)
            worker.install(1, cloudpickle.dumps(module.make_wave), arity=2)
            ch.on_data_requested_values(0.0, 6.28)
            # worker._conn is reset to None by _on_worker_died() the moment
            # the subprocess dies, so this is race-safe (unlike polling
            # worker._proc, which _on_worker_died() may already have set to
            # None by the time we get here).
            qtbot.waitUntil(
                lambda: len(pipe.results) == 1 or worker._conn is None,
                timeout=5000)
            assert worker._conn is not None, (
                "worker subprocess crashed -- likely ModuleNotFoundError "
                "unpickling the INSTALL blob for a folder-plugin callable")
            x, y = pipe.results[0]
            assert x.shape == (4,)
        finally:
            worker.shutdown()
    finally:
        with SciQLopPluginsSettings() as settings:
            settings.extra_plugins_folders = []


def test_derive_worker_trace_path_empty_when_no_session_active(monkeypatch):
    monkeypatch.setattr(tracing, "current_path", lambda: None)
    worker = RemoteWorker(plugin_key="test_plugin")
    worker._proc = SimpleNamespace(pid=1234)
    assert worker._derive_worker_trace_path() == ""


def test_derive_worker_trace_path_includes_plugin_key_and_pid(monkeypatch, tmp_path):
    main_path = str(tmp_path / "session.json")
    monkeypatch.setattr(tracing, "current_path", lambda: main_path)
    worker = RemoteWorker(plugin_key="radio")
    worker._proc = SimpleNamespace(pid=1234)
    derived = worker._derive_worker_trace_path()
    assert derived == str(tmp_path / "session.worker-radio-1234.json")


def test_worker_subprocess_writes_its_own_trace_with_real_zones(qtbot, tmp_path):
    """Real end-to-end: enable a real trace session, spawn a real worker
    while it's active, make a real request, shut down -- the worker's
    OWN sibling trace file should exist and contain the zones from
    worker._serve_request, and merge_worker_traces should fold it back
    into the main trace."""
    main_path = str(tmp_path / "main.json")
    tracing.enable(main_path)
    try:
        worker = RemoteWorker(plugin_key="e2e_trace_test")
        worker.start()
        try:
            pipe = CollectingPipeline()
            from SciQLop.components.plotting.backend.remote.channel import RemoteChannel
            ch = RemoteChannel(pipeline=pipe, channel_id=1, transport=worker)
            worker.register_channel(ch)
            worker.install(1, cloudpickle.dumps(_sin_source), arity=2)
            ch.on_data_requested_values(0.0, 6.28)
            qtbot.waitUntil(lambda: len(pipe.results) == 1, timeout=15000)

            expected_worker_trace = Path(main_path).with_name(
                f"main.worker-e2e_trace_test-{worker._proc.pid}.json")
        finally:
            worker.shutdown()  # sends SHUTDOWN -> worker flushes+disables+exits

        deadline = time.monotonic() + 5
        while not expected_worker_trace.is_file() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert expected_worker_trace.is_file(), "worker never wrote its sibling trace"
        worker_events = json.loads(expected_worker_trace.read_text())["traceEvents"]
        worker_zone_names = {e.get("name") for e in worker_events}
        assert "worker._serve_request" in worker_zone_names
        assert "worker.callback" in worker_zone_names

        # flush() alone does not finalize valid JSON (the trailing `]}` is
        # only written on disable()) -- matches real usage, where the Stop
        # trace menu action already calls disable() before offering to open
        # the file, and merging would happen right after that.
        tracing.disable()
        merged = tracing.merge_worker_traces(main_path, [str(expected_worker_trace)])
        assert merged == 1
        main_events = json.loads(Path(main_path).read_text())["traceEvents"]
        assert "worker._serve_request" in {e.get("name") for e in main_events}
    finally:
        tracing.disable()


def _socketpair_with_tiny_buffers():
    """Main side gets a ~4 KiB send buffer and the peer a ~4 KiB receive
    buffer: the smallest the kernel allows, so a burst of small frames
    fills the pipe the way macOS's 8 KiB AF_UNIX default does."""
    import socket
    a, b = socket.socketpair()
    a.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
    b.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
    return a, b


@pytest.mark.parametrize("default_timeout", [None, 30.0],
                         ids=["no-default-timeout", "global-default-timeout"])
def test_send_request_never_blocks_gui_thread_when_worker_is_not_reading(qtbot, monkeypatch, default_timeout):
    """The worker only reads its pipe between callbacks. A pan storm while
    it's busy must not stall the GUI thread inside send_request (seen live
    on macOS: 15 s GUI freezes ending exactly when the worker replied).

    The second case mirrors a dependency calling socket.setdefaulttimeout()
    (drms does, via sunpy.net): a socket built from a file descriptor
    inherits that timeout, and in timeout mode CPython polls for writability
    *before* the send, so MSG_DONTWAIT alone no longer prevents the stall."""
    import socket
    import threading
    monkeypatch.setattr(socket, "getdefaulttimeout", lambda: default_timeout)
    monkeypatch.setattr(socket, "setdefaulttimeout", lambda t: None)
    original_ctor = socket.socket.__init__

    def ctor_with_default_timeout(self, *a, **kw):
        original_ctor(self, *a, **kw)
        if default_timeout is not None:
            self.settimeout(default_timeout)
    monkeypatch.setattr(socket.socket, "__init__", ctor_with_default_timeout)
    from multiprocessing.connection import Connection
    from SciQLop.components.plotting.backend.remote import protocol as P

    a, b = _socketpair_with_tiny_buffers()
    worker = RemoteWorker(plugin_key="busy_peer")
    conn = Connection(a.detach())
    worker._attach(conn)
    n_requests, channels = 5000, (1, 2, 3)
    b.setblocking(True)   # the patched ctor above put a timeout (=> O_NONBLOCK) on it too
    peer = Connection(b.detach(), writable=False)
    received = []

    def drain():
        while True:
            try:
                received.append(peer.recv())
            except EOFError:
                break

    # The storm runs on the GUI thread like the real slot. If it stalls, the
    # watchdog starts draining so the test fails instead of hanging.
    storm_done, blocked = threading.Event(), []

    def watchdog():
        if not storm_done.wait(3.0):
            blocked.append(True)
            drain()

    threading.Thread(target=watchdog, daemon=True).start()
    for i in range(n_requests):
        worker.send_request(channels[i % 3], i, 0.0, float(i), {})
    storm_done.set()
    assert not blocked, "send_request blocked on a full pipe"

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    qtbot.waitUntil(lambda: not worker._outbox, timeout=5000)
    worker._detach()      # closes both fds -> EOF for the reader
    reader.join(5.0)

    latest = {}
    for msg in received:
        assert msg[0] == P.REQUEST
        latest[msg[1]] = msg[2]
    expected_latest = {channels[i % 3]: i for i in range(n_requests)}
    assert latest == expected_latest
    assert len(received) < n_requests          # coalesced while the peer was stalled
