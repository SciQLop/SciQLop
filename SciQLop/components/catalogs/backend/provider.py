from __future__ import annotations
import bisect
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from speasy.core import make_utc_datetime
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
        self._start = make_utc_datetime(start)
        self._stop = make_utc_datetime(stop)
        self._meta = meta or {}

    @property
    def uuid(self) -> str:
        return self._uuid

    @property
    def start(self) -> datetime:
        return self._start

    @start.setter
    def start(self, value: datetime) -> None:
        value = make_utc_datetime(value)
        if value != self._start:
            self._start = value
            self.range_changed.emit()

    @property
    def stop(self) -> datetime:
        return self._stop

    @stop.setter
    def stop(self, value: datetime) -> None:
        value = make_utc_datetime(value)
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
    SAVE = "save"
    SAVE_CATALOG = "save_catalog"
    RENAME_CATALOG = "rename_catalog"


@dataclass
class Catalog:
    uuid: str
    name: str
    provider: CatalogProvider | None = None
    path: list[str] = field(default_factory=list)


@dataclass
class ProviderAction:
    name: str
    callback: Callable[[Catalog], None]
    icon: QIcon | None = None


class CatalogProvider(QObject):
    """Abstract base class for catalog data providers."""

    catalog_added = Signal(object)
    catalog_removed = Signal(object)
    catalog_renamed = Signal(object)
    events_changed = Signal(object)
    error_occurred = Signal(str)
    dirty_changed = Signal(object, bool)  # (catalog, is_dirty)
    folder_added = Signal(list)    # path segments for an explicit folder
    folder_removed = Signal(list)  # path segments for an explicit folder

    def __init__(self, name: str, parent: QObject | None = None):
        super().__init__(parent)
        self._name = name
        self._events: dict[str, list[CatalogEvent]] = {}
        self._dirty_catalogs: set[str] = set()
        self._range_connections: dict[str, list[tuple]] = {}
        from .registry import CatalogRegistry
        CatalogRegistry.instance().register(self)

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

    def folder_actions(self, path: list[str]) -> list[ProviderAction]:
        """Actions available on an explicit folder node (e.g. room join/leave)."""
        return []

    def folder_display_name(self, path: list[str]) -> str | None:
        """Custom display name for an explicit folder. Return None to use the default."""
        return None

    def _disconnect_range_connections(self, catalog_uuid: str) -> None:
        for event, slot in self._range_connections.get(catalog_uuid, []):
            try:
                event.range_changed.disconnect(slot)
            except RuntimeError:
                pass
        self._range_connections[catalog_uuid] = []

    def _set_events(self, catalog: Catalog, events: list[CatalogEvent]) -> None:
        self._disconnect_range_connections(catalog.uuid)
        self._events[catalog.uuid] = sorted(events, key=lambda e: e.start)
        connections = []
        for event in events:
            slot = lambda ev=event, cat=catalog: self._on_event_range_changed(ev, cat)
            event.range_changed.connect(slot)
            connections.append((event, slot))
        self._range_connections[catalog.uuid] = connections

    def _add_event(self, catalog: Catalog, event: CatalogEvent) -> None:
        if catalog.uuid not in self._events:
            self._events[catalog.uuid] = []
        bisect.insort(self._events[catalog.uuid], event, key=lambda e: e.start)
        slot = lambda ev=event, cat=catalog: self._on_event_range_changed(ev, cat)
        event.range_changed.connect(slot)
        if catalog.uuid not in self._range_connections:
            self._range_connections[catalog.uuid] = []
        self._range_connections[catalog.uuid].append((event, slot))
        self.events_changed.emit(catalog)

    def _remove_event(self, catalog: Catalog, event: CatalogEvent) -> None:
        event_list = self._events.get(catalog.uuid, [])
        try:
            event_list.remove(event)
        except ValueError:
            pass
        conns = self._range_connections.get(catalog.uuid, [])
        for i, (ev, slot) in enumerate(conns):
            if ev is event:
                try:
                    event.range_changed.disconnect(slot)
                except RuntimeError:
                    pass
                conns.pop(i)
                break
        self.events_changed.emit(catalog)

    def add_event(self, catalog: Catalog, event: CatalogEvent) -> None:
        """Public API: add an event to a catalog. Override for backend persistence."""
        self._add_event(catalog, event)
        self.mark_dirty(catalog)

    def remove_event(self, catalog: Catalog, event: CatalogEvent) -> None:
        """Public API: remove an event from a catalog. Override for backend persistence."""
        self._remove_event(catalog, event)
        self.mark_dirty(catalog)

    def create_catalog(self, name: str) -> Catalog | None:
        """Public API: create a new catalog. Override for backend persistence."""
        return None

    def rename_catalog(self, catalog: Catalog, new_name: str) -> None:
        """Public API: rename a catalog. Override for backend persistence."""
        pass

    def remove_catalog(self, catalog: Catalog) -> None:
        """Public API: remove a catalog. Override for backend persistence."""
        self._disconnect_range_connections(catalog.uuid)
        self._range_connections.pop(catalog.uuid, None)
        self._events.pop(catalog.uuid, None)
        self._dirty_catalogs.discard(catalog.uuid)
        self.catalog_removed.emit(catalog)

    def _on_event_range_changed(self, event: CatalogEvent, catalog: Catalog) -> None:
        if event in self._events.get(catalog.uuid, []):
            self.mark_dirty(catalog)

    def mark_dirty(self, catalog: Catalog) -> None:
        if catalog.uuid not in self._dirty_catalogs:
            self._dirty_catalogs.add(catalog.uuid)
            self.dirty_changed.emit(catalog, True)

    def is_dirty(self, catalog: Catalog | None = None) -> bool:
        if catalog is None:
            return len(self._dirty_catalogs) > 0
        return catalog.uuid in self._dirty_catalogs

    def save(self) -> None:
        self._do_save()
        dirty_uuids = set(self._dirty_catalogs)
        self._dirty_catalogs.clear()
        for cat in self.catalogs():
            if cat.uuid in dirty_uuids:
                self.dirty_changed.emit(cat, False)

    def save_catalog(self, catalog: Catalog) -> None:
        self._do_save_catalog(catalog)
        if catalog.uuid in self._dirty_catalogs:
            self._dirty_catalogs.discard(catalog.uuid)
            self.dirty_changed.emit(catalog, False)

    def _do_save(self) -> None:
        pass

    def _do_save_catalog(self, catalog: Catalog) -> None:
        pass
