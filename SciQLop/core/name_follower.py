"""Applies the contributions of an extension point to IPython shells, one holder per name.

Shared by sciqlop.magics and sciqlop.kernel_namespace. Contributions are items with an ``id`` and a ``name``.
Items of one name compete: a core-owned item wins, otherwise the first contributed does, and when the holder
is withdrawn the next one takes over.
"""
from __future__ import annotations

import weakref
from dataclasses import dataclass, field
from functools import partial
from typing import Callable, NamedTuple, Optional

from SciQLop.core.extensions import ExtensionPoint

CORE_OWNER = "sciqlop"


def _run_now(function: Callable, *args) -> None:
    function(*args)


class _Followed(NamedTuple):
    applied: dict      # item id -> the item last applied to the shell
    post: Callable     # post(function, *args) runs function where the shell may be touched


@dataclass
class Follower:
    """``apply(shell, item, replaced)`` and ``unapply(shell, item)`` write to a shell.

    ``replaced`` holds what the shell had applied for the name before this write: an empty tuple for a first
    write, otherwise the apply function must leave a value the user rebound since.
    ``slots(item)`` are what an item occupies within its name; items sharing a slot compete.
    """
    ep: ExtensionPoint
    log: object
    what: Callable[[object], str]
    slots: Callable[[object], tuple]
    apply: Callable
    unapply: Callable
    _shells: weakref.WeakKeyDictionary = field(default_factory=weakref.WeakKeyDictionary, init=False)
    _logged: dict = field(default_factory=dict, init=False)

    def __post_init__(self):
        self.ep.signals.added.connect(partial(Follower._on_added, self))
        self.ep.signals.removed.connect(partial(Follower._on_removed, self))

    def follow(self, shell, post: Optional[Callable] = None) -> None:
        """Apply every contribution to ``shell`` and keep following. Main thread; idempotent per shell."""
        if shell in self._shells:
            return
        self._shells[shell] = _Followed({}, post or _run_now)
        for name in dict.fromkeys(item.name for item in self.ep.list()):
            self._settle(shell, name, ())

    def unfollow(self, shell) -> None:
        """Stop applying contributions to ``shell``; what it already has stays."""
        self._shells.pop(shell, None)

    def _by_precedence(self, candidates: list) -> list:
        return sorted(candidates, key=lambda item: self.ep.owner_of(item.id) != CORE_OWNER)

    def _winners(self, name: str) -> list:
        taken: set = set()
        winners = []
        for item in self._by_precedence(self.ep.list(name=name)):
            if not taken & set(self.slots(item)):
                winners.append(item)
                taken |= set(self.slots(item))
        return winners

    def _apply(self, shell, item, replaced: tuple) -> None:
        followed = self._shells[shell]
        followed.post(self.apply, shell, item, replaced)
        followed.applied[item.id] = item

    def _unapply(self, shell, item) -> None:
        followed = self._shells[shell]
        followed.post(self.unapply, shell, item)
        followed.applied.pop(item.id, None)

    def _settle(self, shell, name: str, replaced: tuple) -> None:
        """Make ``shell`` match the holders of ``name``. ``replaced``: items just unapplied for that name."""
        winners = self._winners(name)
        applied = self._shells[shell].applied
        withdrawn = tuple(i for i in applied.values() if i.name == name and not any(i is w for w in winners))
        for item in withdrawn:
            self._unapply(shell, item)
        for item in winners:
            if applied.get(item.id) is not item:
                self._apply(shell, item, (*replaced, *withdrawn))

    def _report_clashes(self, name: str, reset_id: Optional[str] = None) -> None:
        """Decided once per contribution, whatever number of shells follow."""
        winners = self._winners(name)
        losers = [i for i in self.ep.list(name=name) if not any(i is w for w in winners)]
        logged = self._logged.get(name, set()) - {reset_id}
        for item in (i for i in losers if i.id not in logged):
            holder = next(w for w in winners if set(self.slots(w)) & set(self.slots(item)))
            self.log.error(f"{self.what(item)} from {item.id} ignored: already provided by {holder.id}")
        self._logged[name] = {i.id for i in losers}

    def _on_added(self, item) -> None:
        self._report_clashes(item.name, reset_id=item.id)
        for shell in list(self._shells):
            previous = self._shells[shell].applied.get(item.id)
            if previous is not None:
                self._unapply(shell, previous)
            renamed = previous is not None and previous.name != item.name
            if renamed:
                self._settle(shell, previous.name, (previous,))
            self._settle(shell, item.name, (previous,) if previous is not None and not renamed else ())

    def _on_removed(self, item) -> None:
        self._report_clashes(item.name)
        for shell in list(self._shells):
            applied = self._shells[shell].applied.get(item.id)
            if applied is not None:
                self._unapply(shell, applied)
            self._settle(shell, item.name, (applied,) if applied is not None else ())
