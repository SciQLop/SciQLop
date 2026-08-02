"""Usage refresh must never disturb a turn, and never pile up concurrent calls."""
import asyncio


class _Backend:
    def __init__(self, snapshot=None, error=None, delay=0.0):
        self._snapshot = snapshot
        self._error = error
        self._delay = delay
        self.calls = 0

    async def usage_snapshot(self):
        self.calls += 1
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._error is not None:
            raise self._error
        return self._snapshot


def _refresher(backend, applied):
    from SciQLop.components.agents.chat.usage_refresh import UsageRefresher

    return UsageRefresher(lambda: backend, applied.append)


def test_refresh_applies_the_snapshot():
    from SciQLop.components.agents.backend import TokenCounts, UsageSnapshot

    snapshot = UsageSnapshot(tokens=TokenCounts(input=10))
    backend, applied = _Backend(snapshot=snapshot), []
    asyncio.run(_refresher(backend, applied).refresh())
    assert applied == [snapshot]


def test_backend_without_the_hook_applies_none():
    class Bare:
        pass

    applied = []
    asyncio.run(_refresher(Bare(), applied).refresh())
    assert applied == [None]


def test_missing_backend_applies_none():
    from SciQLop.components.agents.chat.usage_refresh import UsageRefresher

    applied = []
    asyncio.run(UsageRefresher(lambda: None, applied.append).refresh())
    assert applied == [None]


def test_a_raising_backend_is_swallowed_and_applies_none():
    backend, applied = _Backend(error=RuntimeError("CLI gone")), []
    asyncio.run(_refresher(backend, applied).refresh())      # must not raise
    assert applied == [None]


def test_a_burst_of_refreshes_collapses_to_a_lead_plus_one_re_run():
    """Bursts must not fan out into one fetch per call, but the last caller's
    answer still has to land — so a burst costs exactly two fetches: the one
    that was running, and a single trailing re-run covering all the rest."""
    from SciQLop.components.agents.backend import UsageSnapshot

    backend = _Backend(snapshot=UsageSnapshot(model="m"), delay=0.05)
    applied = []
    refresher = _refresher(backend, applied)

    async def run():
        await asyncio.gather(*(refresher.refresh() for _ in range(4)))

    asyncio.run(run())
    assert backend.calls == 2
    assert len(applied) == 2


def test_a_snapshot_is_dropped_when_the_backend_changed_mid_flight():
    """A snapshot describes one backend's session. If the user switches while it
    is in flight, showing it would attribute A's usage to B."""
    from SciQLop.components.agents.backend import UsageSnapshot
    from SciQLop.components.agents.chat.usage_refresh import UsageRefresher

    old = _Backend(snapshot=UsageSnapshot(model="old"), delay=0.05)
    new = _Backend(snapshot=UsageSnapshot(model="new"))
    current, applied = [old], []
    refresher = UsageRefresher(lambda: current[0], applied.append)

    async def run():
        task = asyncio.ensure_future(refresher.refresh())
        await asyncio.sleep(0.01)
        current[0] = new           # user switches backend mid-fetch
        await task

    asyncio.run(run())
    assert old.calls == 1
    assert applied == []


def test_in_flight_clears_after_completion():
    from SciQLop.components.agents.backend import UsageSnapshot

    backend, applied = _Backend(snapshot=UsageSnapshot(model="m")), []
    refresher = _refresher(backend, applied)
    asyncio.run(refresher.refresh())
    assert refresher.in_flight is False
    asyncio.run(refresher.refresh())
    assert backend.calls == 2


def test_a_request_arriving_mid_flight_re_runs_rather_than_being_dropped():
    """Switching session re-reads usage, and switching again before the first
    read lands used to drop the second — so the strip kept the session the user
    had already left, or stayed blank. Coalesce to a trailing re-run instead."""
    from SciQLop.components.agents.backend import UsageSnapshot

    backend = _Backend(snapshot=UsageSnapshot(model="first"), delay=0.05)
    applied = []
    refresher = _refresher(backend, applied)

    async def run():
        first = asyncio.ensure_future(refresher.refresh())
        await asyncio.sleep(0.01)                 # first is now in flight
        backend._snapshot = UsageSnapshot(model="second")
        await refresher.refresh()                 # arrives mid-flight
        await first

    asyncio.run(run())
    assert backend.calls == 2                     # the late request still ran
    assert applied[-1].model == "second"          # and its answer is what shows
    assert refresher.in_flight is False


def test_several_requests_mid_flight_collapse_to_one_re_run():
    from SciQLop.components.agents.backend import UsageSnapshot

    backend = _Backend(snapshot=UsageSnapshot(model="m"), delay=0.05)
    applied = []
    refresher = _refresher(backend, applied)

    async def run():
        first = asyncio.ensure_future(refresher.refresh())
        await asyncio.sleep(0.01)
        await asyncio.gather(*(refresher.refresh() for _ in range(5)))
        await first

    asyncio.run(run())
    assert backend.calls == 2       # one trailing re-run, not five
