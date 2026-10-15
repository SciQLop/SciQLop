"""Extension points: typed, owner-tagged registries that the core and plugins contribute to.

Design: docs/superpowers/specs/2026-10-14-plugin-extension-points-design.md §4.
"""
# Postponed annotations: the `list` method below shadows the builtin inside the class body,
# so `-> list[str]` must not be evaluated eagerly (Python 3.13 does evaluate it).
from __future__ import annotations

import contextlib
import contextvars
from operator import attrgetter
from typing import Callable, Generic, Iterator, TypeVar

from PySide6.QtCore import QObject, Signal

T = TypeVar("T")

USER = "user"
_current_owner = contextvars.ContextVar("sciqlop_extension_owner", default=USER)
_EXTENSION_POINTS: dict = {}


class NotRegistered(LookupError):
    pass


class DuplicateContribution(ValueError):
    pass


class WrongThread(RuntimeError):
    pass


def current_owner() -> str:
    return _current_owner.get()


@contextlib.contextmanager
def owned_by(owner: str) -> Iterator[None]:
    token = _current_owner.set(owner)
    try:
        yield
    finally:
        _current_owner.reset(token)


def _require_main_thread(action: str) -> None:
    from PySide6.QtCore import QCoreApplication, QThread
    app = QCoreApplication.instance()
    if app is not None and QThread.currentThread() != app.thread():
        raise WrongThread(f"{action} must run on the main thread")


class _Signals(QObject):
    added = Signal(object)
    removed = Signal(object)


class ExtensionPoint(Generic[T]):
    """A registry of contributions of one type, each recorded with the plugin that made it.

    Contributing over an existing key (same owner, or `replace=True`) emits `added` with the new item and
    no `removed`: listeners treat `added` as add-or-update.
    """

    def __init__(self, id: str, contribution_type: type, what: str | None = None,
                 key: Callable[[T], str] = attrgetter("id"), doc: str = "", owner: str = "sciqlop"):
        self.id, self.contribution_type, self.doc, self.owner = id, contribution_type, doc, owner
        self._what = what or id
        self._key = key
        self._items: dict[str, T] = {}
        self._owners: dict[str, str] = {}
        self.signals = _Signals()

    def contribute(self, item: T, owner: str | None = None, replace: bool = False) -> T:
        _require_main_thread(f"contributing to {self.id}")
        if not isinstance(item, self.contribution_type):
            raise TypeError(f"{self.id} takes {self.contribution_type.__name__}, got {type(item).__name__}")
        key, owner = self._key(item), owner or current_owner()
        previous = self._owners.get(key) if key in self._items else None
        if previous not in (None, owner) and not replace:
            raise DuplicateContribution(f"{self._what} {key!r} is already registered by {previous}")
        self._items[key] = item
        self._owners[key] = owner
        self.signals.added.emit(item)
        return item

    def get(self, key: str) -> T:
        if key not in self._items:
            raise NotRegistered(f"no {self._what} named {key!r}; available: {', '.join(sorted(self._items))}")
        return self._items[key]

    def __contains__(self, key: str) -> bool:
        return key in self._items

    def remove(self, key: str) -> T:
        _require_main_thread(f"removing from {self.id}")
        item = self.get(key)
        del self._items[key]
        self._owners.pop(key, None)
        self.signals.removed.emit(item)
        return item

    def keys(self) -> list[str]:
        """A snapshot of the keys, safe to call from any thread: one C-level copy under the GIL."""
        return list(self._items)

    def list(self, **filters) -> list[T]:
        return [i for i in self._items.values() if all(getattr(i, k, None) == v for k, v in filters.items())]

    def owner_of(self, key: str) -> str:
        self.get(key)
        return self._owners[key]

    def contributed_by(self, owner: str) -> list[str]:
        return sorted(k for k in self._items if self._owners.get(k) == owner)

    def remove_owner(self, owner: str) -> list[T]:
        _require_main_thread(f"removing contributions from {self.id}")
        removed = [self._items.pop(k) for k in self.contributed_by(owner)]
        for item in removed:
            self._owners.pop(self._key(item), None)
            self.signals.removed.emit(item)
        return removed


def contribute_taking_over(ep: ExtensionPoint, item: T, log) -> T:
    """Contribute `item` for the current owner, replacing whatever holds its key; a takeover from another
    owner is logged, not refused, so a re-run notebook cell or plugin can redeclare what it made before."""
    owner, key = current_owner(), ep._key(item)
    previous = ep._owners.get(key) if key in ep else None
    if previous not in (None, owner):
        log.warning(f"{ep._what} {key!r} of {previous} is replaced by one from {owner}")
    return ep.contribute(item, owner=owner, replace=True)


def declare(ep: ExtensionPoint) -> ExtensionPoint:
    if ep.id in _EXTENSION_POINTS:
        raise DuplicateContribution(f"extension point {ep.id!r} is already declared by {_EXTENSION_POINTS[ep.id].owner}")
    _EXTENSION_POINTS[ep.id] = ep
    return ep


def get(ep_id: str) -> ExtensionPoint:
    if ep_id not in _EXTENSION_POINTS:
        raise NotRegistered(f"no extension point named {ep_id!r}; available: {', '.join(sorted(_EXTENSION_POINTS))}")
    return _EXTENSION_POINTS[ep_id]


def all_extension_points() -> list[ExtensionPoint]:
    return list(_EXTENSION_POINTS.values())
