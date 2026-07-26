"""Out-of-process data-source worker.

Single-threaded loop: install cloudpickled callables, coalesce requests
(keep only the latest per channel), compute, write results into a per-channel
ShmPool segment, reply with the handle. Segments are reclaimed on FREE.

Security note: the cloudpickle blob originates from the same SciQLop process
over a private pipe (single trust domain); see the design spec's pickle trust
boundary section. No untrusted pickle data is ever loaded here."""
from __future__ import annotations

import sys
import traceback
from typing import Dict, Tuple

import cloudpickle

from SciQLop.core import tracing
from . import protocol as P
from .protocol import pack_arrays, total_nbytes
from .reduction import reduce_result
from .shm_pool import ShmPool

_AUTHKEY_SIZE = 32  # os.urandom(32) in worker_handle.py -- always this size


def _stale_sweep(prefix: str = "sciqlop") -> None:
    """Best-effort removal of leaked segments from a previously hard-killed
    worker (same prefix, dead pid). Safe to skip if /dev/shm is unavailable."""
    import glob, os
    base = "/dev/shm"
    if not os.path.isdir(base):
        return
    for path in glob.glob(os.path.join(base, f"{prefix}_*")):
        try:
            from multiprocessing import shared_memory
            shm = shared_memory.SharedMemory(name=os.path.basename(path), track=False)
            try:
                shm.unlink()
            finally:
                shm.close()
        except Exception:
            pass


class _WorkerState:
    def __init__(self):
        self.callables: Dict[int, object] = {}
        self.arity: Dict[int, int] = {}
        self.pools: Dict[int, ShmPool] = {}

    def pool(self, channel_id: int) -> ShmPool:
        if channel_id not in self.pools:
            self.pools[channel_id] = ShmPool(name_prefix=f"sciqlop_{channel_id}")
        return self.pools[channel_id]

    def release(self, channel_id: int) -> None:
        self.callables.pop(channel_id, None)
        self.arity.pop(channel_id, None)
        pool = self.pools.pop(channel_id, None)
        if pool is not None:
            pool.unlink_all()


def _drain(conn, first):
    """Return messages = first + everything already queued, without blocking."""
    msgs = [first]
    while conn.poll(0):
        msgs.append(conn.recv())
    return msgs


def _coalesce(msgs, state, conn) -> Dict[int, tuple]:
    """Apply INSTALL/FREE/RELEASE immediately; keep only the latest REQUEST
    per channel. Returns {channel_id: (req_id, start, stop, knobs)}."""
    latest: Dict[int, tuple] = {}
    for m in msgs:
        tag = m[0]
        if tag == P.INSTALL:
            _, ch, blob, arity = m
            state.callables[ch] = cloudpickle.loads(blob)
            state.arity[ch] = arity
        elif tag == P.FREE:
            _, ch, name = m
            if ch in state.pools:
                state.pools[ch].mark_reusable(name)
        elif tag == P.REQUEST:
            _, ch, req, start, stop, knobs = m
            latest[ch] = (req, start, stop, knobs)
        elif tag == P.RELEASE:
            _, ch = m
            state.release(ch)
            latest.pop(ch, None)
    return latest


def _serve_request(conn, state, channel_id, req_id, start, stop, knobs) -> None:
    with tracing.zone("worker._serve_request", cat="remote", channel=channel_id, req=req_id):
        cb = state.callables.get(channel_id)
        if cb is None:
            return
        try:
            with tracing.zone("worker.callback", cat="remote"):
                result = cb(start, stop, **knobs)
        except Exception:
            conn.send((P.ERROR, channel_id, req_id, traceback.format_exc()))
            return
        if result is None:
            conn.send((P.EMPTY, channel_id, req_id))
            return
        arrays = reduce_result(result, state.arity[channel_id])
        seg = state.pool(channel_id).acquire(total_nbytes(arrays))
        layout = pack_arrays(seg.buf, arrays)
        conn.send((P.RESULT, channel_id, req_id, seg.name, layout, state.arity[channel_id]))


def serve(conn) -> None:
    state = _WorkerState()
    try:
        while True:
            try:
                first = conn.recv()
            except EOFError:
                break
            if first[0] == P.SHUTDOWN:
                break
            latest = _coalesce(_drain(conn, first), state, conn)
            for channel_id, (req_id, start, stop, knobs) in latest.items():
                _serve_request(conn, state, channel_id, req_id, start, stop, knobs)
    except (EOFError, ConnectionError):
        # The parent closed the pipe (normal SciQLop shutdown) while we were
        # mid-request; there is nothing left to reply to. Stop serving quietly
        # instead of letting a BrokenPipeError dump a traceback on every close.
        pass
    finally:
        for ch in list(state.pools):
            state.release(ch)


def _parse_startup_payload(raw: bytes) -> Tuple[bytes, str]:
    """The parent writes authkey (always exactly `_AUTHKEY_SIZE` bytes --
    os.urandom(32)) followed by an optional UTF-8 trace path (empty when
    no trace session is active) on our stdin, then closes it."""
    authkey, trace_path_bytes = raw[:_AUTHKEY_SIZE], raw[_AUTHKEY_SIZE:]
    return authkey, trace_path_bytes.decode("utf-8")


def _main() -> None:
    import multiprocessing.connection as mpc
    address = sys.argv[1]
    authkey, trace_path = _parse_startup_payload(sys.stdin.buffer.read())
    _stale_sweep()
    if trace_path:
        tracing.enable(trace_path)
    try:
        with mpc.Client(address, authkey=authkey) as conn:
            serve(conn)
    finally:
        if trace_path:
            tracing.flush()
            tracing.disable()


if __name__ == "__main__":
    _main()
