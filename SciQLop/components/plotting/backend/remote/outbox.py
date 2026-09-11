"""Main-side outbound queue for the worker pipe.

The worker only reads its pipe between callbacks, so a pan storm while it
is busy fills the kernel socket buffer (8 KiB by default for AF_UNIX on
macOS) and a plain blocking ``Connection.send`` then stalls the GUI thread
until the callback returns. This queue keeps unsent frames in user space
instead, and keeps only the latest unsent REQUEST per channel -- the worker
drops older ones anyway (see ``worker._coalesce``) -- so memory stays bounded.

Frames are byte-identical to ``multiprocessing.connection.Connection.send``
(https://github.com/python/cpython/blob/main/Lib/multiprocessing/connection.py,
``_send_bytes``), so the worker keeps using plain ``conn.recv()``.
"""
from __future__ import annotations

import itertools
import pickle
import struct
from collections import deque
from typing import Deque, List, Optional, Tuple

from . import protocol as P

_Entry = Tuple[Optional[tuple], object, bytes]   # (coalesce key, message, frame)


def frame(msg) -> bytes:
    payload = pickle.dumps(msg)
    n = len(payload)
    if n > 0x7fffffff:
        return struct.pack("!i", -1) + struct.pack("!Q", n) + payload
    return struct.pack("!i", n) + payload


def _coalesce_key(msg) -> Optional[tuple]:
    return (P.REQUEST, msg[1]) if msg[0] == P.REQUEST else None


class Outbox:
    def __init__(self):
        self._frames: Deque[_Entry] = deque()
        self._head_sent = 0

    def __len__(self) -> int:
        return len(self._frames)

    def push(self, msg) -> None:
        key = _coalesce_key(msg)
        if key is not None:
            self._drop_unsent(key)
        self._frames.append((key, msg, frame(msg)))

    def head(self) -> memoryview:
        """Bytes of the oldest frame still to be written."""
        return memoryview(self._frames[0][2])[self._head_sent:]

    def consume(self, nbytes: int) -> None:
        """Account for *nbytes* written from head(), possibly spanning frames."""
        while nbytes:
            remaining = len(self._frames[0][2]) - self._head_sent
            if nbytes < remaining:
                self._head_sent += nbytes
                return
            nbytes -= remaining
            self._frames.popleft()
            self._head_sent = 0

    def messages(self) -> List[object]:
        return [msg for _, msg, _ in self._frames]

    def clear(self) -> None:
        self._frames.clear()
        self._head_sent = 0

    def _drop_unsent(self, key) -> None:
        # A partially written head frame is already on the wire and must
        # complete; only fully unsent frames are replaceable.
        keep = 1 if self._head_sent else 0
        head = list(itertools.islice(self._frames, keep))
        rest = [e for e in itertools.islice(self._frames, keep, None) if e[0] != key]
        self._frames = deque(head + rest)
