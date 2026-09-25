"""Coloured out-of-process VPs that return the wrong thing must say so, not die or go quiet."""
import numpy as np

from SciQLop.user_api.data_types import Colored


class _Conn:
    def __init__(self):
        self.sent = []

    def send(self, msg):
        self.sent.append(msg)


def test_a_bad_colour_is_reported_and_does_not_kill_the_worker():
    from SciQLop.components.plotting.backend.remote import protocol as P
    from SciQLop.components.plotting.backend.remote.worker import _WorkerState, _serve_request
    state = _WorkerState()
    t = np.linspace(0.0, 1.0, 4)
    state.callables[1] = lambda start, stop: Colored((t, np.zeros((4, 3))), color=np.zeros(3))
    state.arity[1] = 2
    conn = _Conn()
    _serve_request(conn, state, 1, 7, 0.0, 1.0, {})
    assert [m[0] for m in conn.sent] == [P.ERROR]
    assert "colour" in conn.sent[0][3]


class _Pipeline:
    def __init__(self):
        self.calls = []

    def set_data(self, *views):
        self.calls.append(("set_data", len(views)))

    def set_data_colored(self, data, color):
        self.calls.append(("set_data_colored", len(data)))


class _Log:
    def __init__(self):
        self.errors = []

    def error(self, msg, *args, **kwargs):
        self.errors.append(msg % args if args else msg)

    def __getattr__(self, name):
        return lambda *a, **k: None


def _channel(monkeypatch, colored):
    from SciQLop.components.plotting.backend.remote import channel as ch
    log = _Log()
    monkeypatch.setattr(ch, "log", log)
    pipeline = _Pipeline()
    return ch.RemoteChannel(pipeline=pipeline, channel_id=3, transport=None, colored=colored,
                            name="plugin/traj"), pipeline, log.errors


def _views(n):
    return [np.arange(4.0) for _ in range(n)]


def test_plain_channel_given_a_colour_says_so(monkeypatch):
    channel, pipeline, errors = _channel(monkeypatch, colored=False)
    channel._deliver(_views(3), arity=2)
    assert pipeline.calls == []
    assert any("plugin/traj" in e and "colored=True" in e for e in errors)


def test_coloured_channel_given_plain_data_says_so(monkeypatch):
    channel, pipeline, errors = _channel(monkeypatch, colored=True)
    channel._deliver(_views(2), arity=2)
    assert pipeline.calls == []
    assert any("plugin/traj" in e and "Colored" in e for e in errors)


def test_matching_batches_are_delivered(monkeypatch):
    channel, pipeline, errors = _channel(monkeypatch, colored=True)
    channel._deliver(_views(3), arity=2)
    plain, plain_pipeline, _ = _channel(monkeypatch, colored=False)
    plain._deliver(_views(2), arity=2)
    assert pipeline.calls == [("set_data_colored", 2)]
    assert plain_pipeline.calls == [("set_data", 2)]
    assert errors == []
