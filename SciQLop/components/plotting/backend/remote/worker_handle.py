"""Main-side handle on one worker subprocess.

Spawns the worker, owns the duplex Connection, and pumps replies onto the main
thread via a QSocketNotifier on the connection's fd. Implements the transport
interface (send_request/send_free/release) that RemoteChannel calls."""
from __future__ import annotations

import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
from multiprocessing.connection import Listener
from pathlib import Path
from typing import Dict, Optional, Tuple

from PySide6.QtCore import QObject, QSocketNotifier

from SciQLop.core import tracing
from SciQLop.components.plugins.backend.loader.loader import plugins_folders
from . import protocol as P

log = logging.getLogger(__name__)


class RemoteWorker(QObject):
    def __init__(self, plugin_key: str, parent: QObject | None = None):
        super().__init__(parent)
        self.plugin_key = plugin_key
        self._proc: subprocess.Popen | None = None
        self._conn = None
        self._notifier: QSocketNotifier | None = None
        self._channels: Dict[int, object] = {}
        self._accept_timeout = 15.0   # seconds to wait for the worker to connect
        # One in-flight request per channel -- matches worker.py's own
        # coalescing (only the latest REQUEST per channel is ever served),
        # so a newer send_request for a channel simply replaces its entry.
        self._pending: Dict[int, Tuple[int, float]] = {}  # channel_id -> (req_id, sent_at)

    def _worker_env(self) -> Dict[str, str]:
        # A folder-plugin (extra_plugins_folders / the user plugins dir) is
        # loaded in THIS process via loader.import_from_path(), which
        # registers it into sys.modules without ever adding its directory
        # to sys.path -- fine here, but the worker below is a brand-new
        # `sys.executable -m ...` interpreter that never runs SciQLop's own
        # plugin loader. A callable from such a plugin cloudpickles fine
        # (by module-name reference) but the worker can't resolve the
        # import on the other end. Put those folders on the worker's
        # PYTHONPATH so a plain `import <plugin>` there works the same way
        # it would for any normal on-disk package. Skip the bundled plugins
        # folder (index 0): those already resolve as SciQLop.plugins.<name>
        # submodules, which the worker's own SciQLop install already sees.
        env = os.environ.copy()
        extra = list(plugins_folders()[1:])
        existing = env.get("PYTHONPATH")
        if existing:
            extra.append(existing)
        if extra:
            env["PYTHONPATH"] = os.pathsep.join(extra)
        return env

    # --- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        if self._proc is not None:
            return
        authkey = os.urandom(32)
        address = os.path.join(tempfile.gettempdir(), f"sciqlop-remote-{os.getpid()}-{id(self)}")
        listener = Listener(address, authkey=authkey)
        self._proc = subprocess.Popen(
            [sys.executable, "-m",
             "SciQLop.components.plotting.backend.remote.worker", address],
            stdin=subprocess.PIPE,
            env=self._worker_env(),
        )
        trace_path = self._derive_worker_trace_path()
        self._proc.stdin.write(authkey + trace_path.encode("utf-8"))
        self._proc.stdin.close()
        self._conn = self._accept_or_timeout(listener)
        self._notifier = QSocketNotifier(self._conn.fileno(), QSocketNotifier.Type.Read)
        self._notifier.activated.connect(self._on_readable)
        tracing.counter("remote.worker_alive", 1, cat="remote")

    def _derive_worker_trace_path(self) -> str:
        """When a trace session is active, tell the worker (via stdin,
        alongside the authkey -- see worker._parse_startup_payload) to
        record its own sibling trace, merged back in on Stop via
        tracing.merge_worker_traces(). Known v1 limitation: only workers
        SPAWNED while a session is active get one -- an already-running
        worker (registry.py caches across Start/Stop cycles) won't
        retroactively start tracing."""
        main_path = tracing.current_path()
        if not main_path or self._proc is None:
            return ""
        p = Path(main_path)
        suffix = p.suffix or ".json"
        stem = p.name[: -len(suffix)] if suffix and p.name.endswith(suffix) else p.stem
        return str(p.with_name(f"{stem}.worker-{self.plugin_key}-{self._proc.pid}{suffix}"))

    def _accept_or_timeout(self, listener):
        """Accept the worker's connection without blocking the UI forever: if
        the worker fails to connect within the timeout, kill it and raise
        (the registry respawns lazily on the next request)."""
        result = {}

        def _accept():
            try:
                result["conn"] = listener.accept()
            except Exception:   # listener.close() below lands here, unblocking accept()
                pass

        t = threading.Thread(target=_accept, daemon=True)
        t.start()
        t.join(self._accept_timeout)
        if "conn" not in result:
            self._proc.kill()
            listener.close()    # unblocks the still-waiting accept() in the thread
            self._proc, self._conn = None, None
            raise RuntimeError(
                f"remote worker for {self.plugin_key!r} did not connect within "
                f"{self._accept_timeout:.0f}s")
        listener.close()
        return result["conn"]

    def shutdown(self) -> None:
        try:
            if self._conn is not None:
                self._conn.send((P.SHUTDOWN,))
        except Exception:
            pass
        if self._notifier is not None:
            self._notifier.setEnabled(False)
        if self._proc is not None:
            try:
                self._proc.wait(timeout=5)
            except Exception:
                self._proc.kill()
        self._proc, self._conn, self._notifier = None, None, None
        self._pending.clear()
        tracing.counter("remote.worker_alive", 0, cat="remote")

    # --- channels -----------------------------------------------------------
    def register_channel(self, channel) -> None:
        self._channels[channel.channel_id] = channel

    def install(self, channel_id: int, blob: bytes, arity: int) -> None:
        with tracing.zone("RemoteWorker.install", cat="remote", channel=channel_id):
            self._conn.send((P.INSTALL, channel_id, blob, arity))

    # --- transport interface (called by RemoteChannel) ----------------------
    def send_request(self, channel_id: int, req_id: int, start: float, stop: float, knobs: dict) -> None:
        with tracing.zone("RemoteWorker.send_request", cat="remote",
                          channel=channel_id, req=req_id):
            self._pending[channel_id] = (req_id, time.monotonic())
            tracing.counter("remote.pending_requests", len(self._pending), cat="remote")
            self._send((P.REQUEST, channel_id, req_id, start, stop, knobs))

    def send_free(self, channel_id: int, name: str) -> None:
        self._send((P.FREE, channel_id, name))

    def release(self, channel_id: int) -> None:
        self._channels.pop(channel_id, None)
        self._pending.pop(channel_id, None)
        self._send((P.RELEASE, channel_id))

    def _send(self, msg) -> None:
        """Best-effort send. A dead worker (conn closed) degrades quietly so a
        late data_requested/FREE can't raise out of a Qt slot."""
        if self._conn is None:
            return
        try:
            self._conn.send(msg)
        except (EOFError, OSError):
            self._on_worker_died()

    # --- reply pump ---------------------------------------------------------
    def _on_readable(self) -> None:
        with tracing.zone("RemoteWorker._on_readable", cat="remote"):
            try:
                while self._conn is not None and self._conn.poll(0):
                    self._dispatch(self._conn.recv())
            except (EOFError, OSError):
                self._on_worker_died()

    def _dispatch(self, msg) -> None:
        tag = msg[0]
        with tracing.zone("RemoteWorker._dispatch", cat="remote", tag=tag):
            if tag == P.RESULT:
                _, ch, req, name, layout, arity = msg
                self._settle(ch, req)
                c = self._channels.get(ch)
                if c is not None:
                    c.on_result(req, name, layout, arity)
            elif tag == P.EMPTY:
                _, ch, req = msg
                self._settle(ch, req)
                c = self._channels.get(ch)
                if c is not None:
                    c.on_empty(req)
            elif tag == P.ERROR:
                _, ch, req, tb = msg
                self._settle(ch, req)
                c = self._channels.get(ch)
                if c is not None:
                    c.on_error(req, tb)

    def _settle(self, channel_id: int, req_id: int) -> None:
        """Pop the matching pending entry (a stale req_id -- already
        superseded by a newer send_request for the same channel -- is left
        alone, it's not the request this reply is settling) and publish the
        updated health counters."""
        pending = self._pending.get(channel_id)
        if pending is None or pending[0] != req_id:
            return
        _, sent_at = self._pending.pop(channel_id)
        tracing.counter("remote.last_latency_ms", (time.monotonic() - sent_at) * 1000, cat="remote")
        tracing.counter("remote.pending_requests", len(self._pending), cat="remote")

    def _on_worker_died(self) -> None:
        log.warning("remote worker for %s died", self.plugin_key)
        if self._notifier is not None:
            self._notifier.setEnabled(False)
        self._proc, self._conn, self._notifier = None, None, None
        self._pending.clear()
        tracing.counter("remote.worker_alive", 0, cat="remote")
