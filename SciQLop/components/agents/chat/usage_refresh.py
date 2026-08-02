"""Coordinates session-usage refreshes for the chat dock.

Separate from the widget so the two rules that matter — a usage failure never
surfaces as a chat error, and overlapping requests collapse to one — are
testable without a Qt dock.
"""
from __future__ import annotations

from typing import Callable, Optional

from ..backend import UsageSnapshot

GetBackend = Callable[[], Optional[object]]
ApplySnapshot = Callable[[Optional[UsageSnapshot]], None]


class UsageRefresher:
    def __init__(self, get_backend: GetBackend, apply_snapshot: ApplySnapshot):
        self._get_backend = get_backend
        self._apply = apply_snapshot
        self._in_flight = False
        self._pending = False

    @property
    def in_flight(self) -> bool:
        return self._in_flight

    async def refresh(self) -> None:
        """Fetch and apply. Never raises: a backend that cannot report usage
        must not turn into a chat error.

        A snapshot describes one backend's session, so it is dropped if the user
        switched backend while it was in flight — applying it would attribute
        the old session's usage to the newly selected one.
        """
        if self._in_flight:
            # Coalesce rather than drop: a request that arrives mid-flight is
            # asking about newer state than the one running, so discarding it
            # leaves the strip describing a session the user already left.
            self._pending = True
            return
        self._in_flight = True
        try:
            while True:
                self._pending = False
                backend = self._get_backend()
                snapshot = await self._fetch(backend)
                if backend is self._get_backend():
                    self._apply(snapshot)
                if not self._pending:
                    return
        finally:
            self._in_flight = False
            self._pending = False

    async def _fetch(self, backend) -> Optional[UsageSnapshot]:
        hook = getattr(backend, "usage_snapshot", None)
        if hook is None:
            return None
        try:
            return await hook()
        except Exception:
            return None
