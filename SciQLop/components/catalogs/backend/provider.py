from __future__ import annotations
import bisect
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from speasy.core import make_utc_datetime
from typing import Any, Callable
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QIcon


_SENTINEL = object()


class CatalogEvent(QObject):
    """Minimal event: uuid + time interval + optional metadata."""
    range_changed = Signal()
    meta_changed = Signal(str)  # key

    def __init__(self, uuid: str, start: datetime, stop: datetime,
                 meta: dict[str, Any] | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._uuid = uuid
        self._start = make_utc_datetime(start)
        self._stop = make_utc_datetime(stop)
        self._meta = dict(meta or {})

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

    def set_meta(self, key: str, value: Any) -> None:
        """Update one metadata key in place, emitting meta_changed if it changed."""
        if self._meta.get(key, _SENTINEL) == value:
            return
        self._meta[key] = value
        self.meta_changed.emit(key)

    def remove_meta(self, key: str) -> None:
        if key in self._meta:
            del self._meta[key]
            self.meta_changed.emit(key)


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
    MOVE_CATALOG = "move_catalog"


class NodeType(str, Enum):
    PROVIDER = "provider"
    FOLDER = "folder"
    CATALOG = "catalog"


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
    catalog_moved = Signal(object)
    events_changed = Signal(object)
    error_occurred = Signal(str)
    dirty_changed = Signal(object, bool)  # (catalog, is_dirty)
    event_meta_changed = Signal(object, object, str)  # (catalog, event, key)
    loading_started = Signal(object)   # catalog
    loading_finished = Signal(object)  # catalog
    folder_added = Signal(list)    # path segments for an explicit folder
    folder_removed = Signal(list)  # path segments for an explicit folder
    status_changed = Signal()      # provider-level state changed (e.g. connection)
    attribute_spec_changed = Signal(object, str)  # (catalog, key)

    def __init__(self, name: str, parent: QObject | None = None):
        super().__init__(parent)
        self._name = name
        self._events: dict[str, list[CatalogEvent]] = {}
        self._dirty_catalogs: set[str] = set()
        self._provider_dirty: bool = False
        self._needs_sort: set[str] = set()
        self._range_connections: dict[str, list[tuple]] = {}
        self._attribute_specs: dict[str, dict[str, "KnobSpec"]] = {}  # catalog_uuid → {key: spec}
        from .registry import CatalogRegistry
        CatalogRegistry.instance().register(self)

    @property
    def name(self) -> str:
        return self._name

    def catalogs(self) -> list[Catalog]:
        raise NotImplementedError

    def events(self, catalog: Catalog, start: datetime | None = None,
               stop: datetime | None = None) -> list[CatalogEvent]:
        self._ensure_sorted(catalog.uuid)
        event_list = self._events.get(catalog.uuid, [])
        if start is None and stop is None:
            return list(event_list)
        key = lambda e: e.start
        lo = 0 if start is None else bisect.bisect_left(event_list, start, key=key)
        hi = len(event_list) if stop is None else bisect.bisect_right(event_list, stop, key=key)
        return event_list[lo:hi]

    def _ensure_sorted(self, catalog_uuid: str) -> None:
        if catalog_uuid not in self._needs_sort:
            return
        event_list = self._events.get(catalog_uuid)
        if event_list is not None:
            event_list.sort(key=lambda e: e.start)
        self._needs_sort.discard(catalog_uuid)

    def capabilities(self, catalog: Catalog | None = None) -> set[str]:
        return set()

    def attribute_spec(self, catalog: Catalog, key: str):
        """Return the typed spec (`KnobSpec`) for an event metadata attribute,
        or ``None`` if the provider has no schema for *key* (free-form).

        Resolution order:
          1. User-declared specs (set via :meth:`set_attribute_spec`).
          2. Built-in defaults from :meth:`_default_attribute_spec` (e.g. rating,
             author, tags) shared across all providers.
          3. Subclass-specific overrides (when subclasses provide their own).

        Subclasses overriding this method SHOULD call
        ``super().attribute_spec(...)`` first and only fall back to their
        built-ins when it returns ``None``.

        Used by the editor delegate to pick a constrained widget (range-bound
        spinbox, combo, …) instead of inferring the type from current values.
        """
        if catalog is not None:
            user_spec = self._attribute_specs.get(catalog.uuid, {}).get(key)
            if user_spec is not None:
                return user_spec
        return self._default_attribute_spec(key)

    @staticmethod
    def _default_attribute_spec(key: str):
        """Built-in spec defaults shared across providers."""
        from SciQLop.core.knobs import IntKnob, StringKnob, StringListKnob
        if key == "rating":
            return IntKnob(name=key, min=1, max=5, default=3,
                           description="Event rating (1-5)")
        if key == "author":
            return StringKnob(name=key, default="",
                              description="Event author")
        if key == "tags":
            return StringListKnob(name=key, default=(),
                                  description="Free-form tags")
        return None

    def set_attribute_spec(self, catalog: Catalog, key: str, spec) -> None:
        """Declare a user-defined schema for an event metadata attribute.

        Stored in-memory by default; subclasses override
        :meth:`_persist_attribute_spec` to push to backend persistence.
        Emits ``attribute_spec_changed`` after a successful update.
        """
        self._attribute_specs.setdefault(catalog.uuid, {})[key] = spec
        self._persist_attribute_spec(catalog, key, spec)
        self.attribute_spec_changed.emit(catalog, key)

    def remove_attribute_spec(self, catalog: Catalog, key: str) -> None:
        """Drop a user-declared schema. Emits ``attribute_spec_changed``."""
        catalog_specs = self._attribute_specs.get(catalog.uuid, {})
        if key not in catalog_specs:
            return
        del catalog_specs[key]
        self._persist_attribute_spec_removal(catalog, key)
        self.attribute_spec_changed.emit(catalog, key)

    def _persist_attribute_spec(self, catalog: Catalog, key: str, spec) -> None:
        """Subclass hook: push the schema to backend persistence (e.g. catalog
        attribute, CRDT map). Default is no-op (in-memory only)."""
        pass

    def _persist_attribute_spec_removal(self, catalog: Catalog, key: str) -> None:
        """Subclass hook: drop the schema from backend persistence."""
        pass

    def actions(self, catalog: Catalog | None = None) -> list[ProviderAction]:
        return []

    def folder_actions(self, path: list[str]) -> list[ProviderAction]:
        """Actions available on an explicit folder node (e.g. room join/leave)."""
        return []

    def handle_event_drop(
        self,
        target_catalog: Catalog,
        events: list[CatalogEvent],
        action: str = "link",
        source_catalog: Catalog | None = None,
    ) -> None:
        """Receive an event drop on a catalog of this provider.

        action ∈ {"link", "move", "duplicate"}:
        - "link":      add the same UUID to target (no-op for events already there)
        - "move":      add to target then remove from source
        - "duplicate": insert a fresh UUID copy into target
        """
        if not events:
            return
        caps = self.capabilities()
        if Capability.CREATE_EVENTS not in caps and action != "link":
            raise PermissionError(f"{self.name} does not allow CREATE_EVENTS")
        existing_uuids = {e.uuid for e in self._events.get(target_catalog.uuid, [])}
        for ev in events:
            if action == "duplicate":
                self.add_event(target_catalog, self._copy_event(ev))
            elif action == "link" and ev.uuid in existing_uuids:
                continue  # already in target — no-op per docstring
            else:
                self.add_event(target_catalog, ev)
        if action == "move" and source_catalog is not None:
            for ev in events:
                self.remove_event(source_catalog, ev)

    @staticmethod
    def _copy_event(ev: CatalogEvent) -> CatalogEvent:
        import uuid as _uuid
        return CatalogEvent(
            uuid=str(_uuid.uuid4()),
            start=ev.start, stop=ev.stop,
            meta=dict(ev.meta),
        )

    def folder_display_name(self, path: list[str]) -> str | None:
        """Custom display name for an explicit folder. Return None to use the default."""
        return None

    def node_icon(self, node_type: NodeType, path: list[str] | None = None) -> QIcon | None:
        """Return a custom icon for a node type, or None for default."""
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
        self._ensure_sorted(catalog.uuid)
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

    def set_event_meta(self, catalog: Catalog, event: CatalogEvent, key: str, value: Any) -> None:
        """Public API: set one metadata key on an event. Override for backend persistence."""
        if event.meta.get(key, _SENTINEL) == value:
            return
        event.set_meta(key, value)
        self.event_meta_changed.emit(catalog, event, key)
        self.mark_dirty(catalog)

    def remove_event_meta(self, catalog: Catalog, event: CatalogEvent, key: str) -> None:
        """Public API: remove one metadata key from an event. Override for backend persistence."""
        if key not in event.meta:
            return
        event.remove_meta(key)
        self.event_meta_changed.emit(catalog, event, key)
        self.mark_dirty(catalog)

    def set_events_meta(self, catalog: Catalog, events: list[CatalogEvent],
                        key: str, value: Any) -> None:
        """Public API: bulk variant. Default delegates to ``set_event_meta`` per
        event so subclass overrides of ``set_event_meta`` apply automatically.
        Override directly when the backend supports a real batch primitive.
        """
        for event in events:
            self.set_event_meta(catalog, event, key, value)

    def create_catalog(self, name: str, path: list[str] | None = None) -> Catalog:
        """Public API: create a new catalog. Override for backend persistence."""
        raise NotImplementedError

    def rename_catalog(self, catalog: Catalog, new_name: str) -> None:
        """Public API: rename a catalog. Override for backend persistence."""
        pass

    def move_catalog(self, catalog: Catalog, new_path: list[str]) -> None:
        """Public API: relocate a catalog under *new_path*, preserving its uuid.

        Default updates ``catalog.path`` in memory and emits ``catalog_moved``.
        Subclasses with persistent backends must override to also persist the
        new path.
        """
        if list(catalog.path) == list(new_path):
            return
        catalog.path = list(new_path)
        self.catalog_moved.emit(catalog)
        self.mark_dirty(catalog)

    def remove_catalog(self, catalog: Catalog) -> None:
        """Public API: remove a catalog. Override for backend persistence."""
        self._disconnect_range_connections(catalog.uuid)
        self._range_connections.pop(catalog.uuid, None)
        self._events.pop(catalog.uuid, None)
        self._dirty_catalogs.discard(catalog.uuid)
        self._needs_sort.discard(catalog.uuid)
        self.catalog_removed.emit(catalog)
        self.mark_provider_dirty()

    def _on_event_range_changed(self, event: CatalogEvent, catalog: Catalog) -> None:
        event_list = self._events.get(catalog.uuid, [])
        if event in event_list:
            self._needs_sort.add(catalog.uuid)
            self.mark_dirty(catalog)

    def mark_dirty(self, catalog: Catalog) -> None:
        if catalog.uuid not in self._dirty_catalogs:
            self._dirty_catalogs.add(catalog.uuid)
            self.dirty_changed.emit(catalog, True)

    def mark_provider_dirty(self) -> None:
        """Flag the provider as having pending changes that aren't tied to a
        single surviving catalog (e.g. a catalog deletion). The `*` indicator
        on the provider node tracks this in addition to per-catalog dirty.
        """
        if not self._provider_dirty:
            self._provider_dirty = True
            self.dirty_changed.emit(None, True)

    def is_dirty(self, catalog: Catalog | None = None) -> bool:
        if catalog is None:
            return self._provider_dirty or len(self._dirty_catalogs) > 0
        return catalog.uuid in self._dirty_catalogs

    def save(self) -> None:
        self._do_save()
        dirty_uuids = set(self._dirty_catalogs)
        self._dirty_catalogs.clear()
        was_provider_dirty = self._provider_dirty
        self._provider_dirty = False
        for cat in self.catalogs():
            if cat.uuid in dirty_uuids:
                self.dirty_changed.emit(cat, False)
        if was_provider_dirty:
            self.dirty_changed.emit(None, False)

    def save_catalog(self, catalog: Catalog) -> None:
        self._do_save_catalog(catalog)
        if catalog.uuid in self._dirty_catalogs:
            self._dirty_catalogs.discard(catalog.uuid)
            self.dirty_changed.emit(catalog, False)

    def _do_save(self) -> None:
        pass

    def _do_save_catalog(self, catalog: Catalog) -> None:
        pass
