"""ACP usage reporting: `UsageUpdate` → `UsageSnapshot`.

An ACP turn ends with a session/update carrying the context window used, its
size and the turn cost. It is not part of the transcript, so the backend keeps
the last one aside and serves it through the optional
`UsageReportingBackend.usage_snapshot`, which the chat dock's info strip polls.
"""
import asyncio

import pytest

pytestmark = pytest.mark.skipif(
    pytest.importorskip("acp") is None, reason="agent-client-protocol not installed"
)

from SciQLop.components.agents.acp.backend import AcpAgentBackend


def _backend():
    backend = AcpAgentBackend.__new__(AcpAgentBackend)
    backend._usage = None
    backend._model = "opencode-go/glm-5.2"
    backend._slash_commands = []
    backend._updates = None
    return backend


def _usage_update(used=14499, size=1_000_000, amount=0.25, currency="USD"):
    from acp.schema import Cost, UsageUpdate
    return UsageUpdate(used=used, size=size, session_update="usage_update",
                       cost=Cost(amount=amount, currency=currency))


def test_usage_update_is_not_forwarded_to_the_transcript():
    # It is metadata, not content: leaking it into the turn queue would make
    # the stream translator emit an empty block at the end of every turn.
    backend = _backend()
    queue = asyncio.Queue()
    backend._updates = queue
    backend._on_update(_usage_update())
    assert queue.empty()


def test_usage_snapshot_reports_context_and_cost():
    backend = _backend()
    backend._on_update(_usage_update())
    snap = asyncio.run(backend.usage_snapshot())
    assert snap.context_tokens == 14499
    assert snap.context_max == 1_000_000
    assert snap.cost.amount == 0.25
    assert snap.cost.unit == "USD"
    assert snap.model == "opencode-go/glm-5.2"


def test_usage_snapshot_is_none_before_any_turn():
    assert asyncio.run(_backend().usage_snapshot()) is None


def test_latest_usage_update_wins():
    backend = _backend()
    backend._on_update(_usage_update(used=100))
    backend._on_update(_usage_update(used=250))
    assert asyncio.run(backend.usage_snapshot()).context_tokens == 250


def test_usage_snapshot_survives_a_cost_less_update():
    # `cost` is optional in the schema; a free model may report none at all.
    from acp.schema import UsageUpdate
    backend = _backend()
    backend._on_update(UsageUpdate(used=10, size=200, session_update="usage_update"))
    snap = asyncio.run(backend.usage_snapshot())
    assert snap.context_tokens == 10 and snap.cost is None
