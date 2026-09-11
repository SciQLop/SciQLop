"""Length-prefixed pickle frames, byte-identical to
``multiprocessing.connection.Connection`` (see ``_send_bytes``/``_recv_bytes`` in
https://github.com/python/cpython/blob/main/Lib/multiprocessing/connection.py),
so one end can use a plain ``Connection`` while the other reads and writes a
non-blocking socket incrementally.

Pickle is the existing wire format of this private, authkey-protected pipe
between SciQLop and the worker it spawned (single trust domain, see the
security note in worker.py); no untrusted data is ever decoded here.
"""
from __future__ import annotations

import pickle
import struct
from typing import Iterator

_HEADER = struct.Struct("!i")
_LONG_HEADER = struct.Struct("!Q")


def frame(msg) -> bytes:
    payload = pickle.dumps(msg)
    n = len(payload)
    if n > 0x7fffffff:
        return _HEADER.pack(-1) + _LONG_HEADER.pack(n) + payload
    return _HEADER.pack(n) + payload


class FrameDecoder:
    """Feed arbitrary byte chunks, iterate complete messages."""

    def __init__(self):
        self._buf = bytearray()

    def feed(self, data: bytes) -> Iterator[object]:
        self._buf += data
        while True:
            msg = self._pop_frame()
            if msg is None:
                return
            yield msg

    def _pop_frame(self):
        if len(self._buf) < _HEADER.size:
            return None
        (n,) = _HEADER.unpack_from(self._buf)
        start = _HEADER.size
        if n == -1:
            if len(self._buf) < start + _LONG_HEADER.size:
                return None
            (n,) = _LONG_HEADER.unpack_from(self._buf, start)
            start += _LONG_HEADER.size
        end = start + n
        if len(self._buf) < end:
            return None
        payload = bytes(self._buf[start:end])
        del self._buf[:end]
        return pickle.loads(payload)
