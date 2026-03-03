from __future__ import annotations
import bisect
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QIcon


class CatalogEvent(QObject):
    """Minimal event: uuid + time interval + optional metadata."""
    range_changed = Signal()

    def __init__(self, uuid: str, start: datetime, stop: datetime,
                 meta: dict[str, Any] | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._uuid = uuid
        self._start = start
        self._stop = stop
        self._meta = meta or {}

    @property
    def uuid(self) -> str:
        return self._uuid

    @property
    def start(self) -> datetime:
        return self._start

    @start.setter
    def start(self, value: datetime) -> None:
        if value != self._start:
            self._start = value
            self.range_changed.emit()

    @property
    def stop(self) -> datetime:
        return self._stop

    @stop.setter
    def stop(self, value: datetime) -> None:
        if value != self._stop:
            self._stop = value
            self.range_changed.emit()

    @property
    def meta(self) -> dict[str, Any]:
        return self._meta


class Capability(str, Enum):
    EDIT_EVENTS = "edit_events"
    CREATE_EVENTS = "create_events"
    DELETE_EVENTS = "delete_events"
    CREATE_CATALOGS = "create_catalogs"
    DELETE_CATALOGS = "delete_catalogs"
    EXPORT_EVENTS = "export_events"
    IMPORT_EVENTS = "import_events"
    IMPORT_FILES = "import_files"


@dataclass
class Catalog:
    uuid: str
    name: str
    provider: CatalogProvider | None = None


@dataclass
class ProviderAction:
    name: str
    callback: Callable[[Catalog], None]
    icon: QIcon | None = None


class CatalogProvider(QObject):
    """Abstract base class for catalog data providers."""

    catalog_added = Signal(object)
    catalog_removed = Signal(object)
    events_changed = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, name: str, parent: QObject | None = None):
        super().__init__(parent)
        self._name = name
        self._events: dict[str, list[CatalogEvent]] = {}

    @property
    def name(self) -> str:
        return self._name

    def catalogs(self) -> list[Catalog]:
        raise NotImplementedError

    def events(self, catalog: Catalog, start: datetime | None = None,
               stop: datetime | None = None) -> list[CatalogEvent]:
        event_list = self._events.get(catalog.uuid, [])
        if start is None and stop is None:
            return list(event_list)
        key = lambda e: e.start
        lo = 0 if start is None else bisect.bisect_left(event_list, start, key=key)
        hi = len(event_list) if stop is None else bisect.bisect_right(event_list, stop, key=key)
        return event_list[lo:hi]

    def capabilities(self, catalog: Catalog | None = None) -> set[str]:
        return set()

    def actions(self, catalog: Catalog | None = None) -> list[ProviderAction]:
        return []

    def _set_events(self, catalog: Catalog, events: list[CatalogEvent]) -> None:
        self._events[catalog.uuid] = sorted(events, key=lambda e: e.start)

    def _add_event(self, catalog: Catalog, event: CatalogEvent) -> None:
        if catalog.uuid not in self._events:
            self._events[catalog.uuid] = []
        bisect.insort(self._events[catalog.uuid], event, key=lambda e: e.start)
        self.events_changed.emit(catalog)

    def _remove_event(self, catalog: Catalog, event: CatalogEvent) -> None:
        event_list = self._events.get(catalog.uuid, [])
        try:
            event_list.remove(event)
        except ValueError:
            pass
        self.events_changed.emit(catalog)
