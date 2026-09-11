"""Main-side outbound queue: byte-identical framing to multiprocessing's
Connection, latest-REQUEST-per-channel coalescing, partial-write resume."""
import socket
from multiprocessing.connection import Connection


from SciQLop.components.plotting.backend.remote import protocol as P
from SciQLop.components.plotting.backend.remote.outbox import Outbox


def _recv_all(sock_fd, count):
    conn = Connection(sock_fd, writable=False)
    return [conn.recv() for _ in range(count)]


def test_frames_decode_with_connection_recv():
    a, b = socket.socketpair()
    box = Outbox()
    box.push((P.INSTALL, 1, b"x" * 20000, 2))   # > 16384: the split-header path
    box.push((P.FREE, 1, "seg"))
    while box:
        box.consume(a.send(box.head()))
    got = _recv_all(b.detach(), 2)
    a.close()
    assert got == [(P.INSTALL, 1, b"x" * 20000, 2), (P.FREE, 1, "seg")]


def test_request_coalesces_per_channel_keeping_order_of_other_messages():
    box = Outbox()
    box.push((P.REQUEST, 1, 1, 0.0, 1.0, {}))
    box.push((P.FREE, 1, "seg"))
    box.push((P.REQUEST, 2, 1, 0.0, 1.0, {}))
    box.push((P.REQUEST, 1, 2, 0.0, 2.0, {}))
    box.push((P.REQUEST, 1, 3, 0.0, 3.0, {}))
    assert box.messages() == [
        (P.FREE, 1, "seg"),
        (P.REQUEST, 2, 1, 0.0, 1.0, {}),
        (P.REQUEST, 1, 3, 0.0, 3.0, {}),
    ]


def test_partially_sent_head_is_never_replaced():
    box = Outbox()
    box.push((P.REQUEST, 1, 1, 0.0, 1.0, {}))
    full = len(box.head())
    box.consume(3)                                   # 3 bytes already on the wire
    box.push((P.REQUEST, 1, 2, 0.0, 2.0, {}))
    assert [m[2] for m in box.messages()] == [1, 2]  # head kept, new one queued
    assert len(box.head()) == full - 3


def test_consume_advances_across_frames():
    box = Outbox()
    box.push((P.FREE, 1, "a"))
    box.push((P.FREE, 1, "b"))
    first = box.head()
    box.consume(len(first) - 1)
    assert len(box.head()) == 1
    box.consume(1)
    assert box.messages() == [(P.FREE, 1, "b")]
    box.consume(len(box.head()))
    assert not box
