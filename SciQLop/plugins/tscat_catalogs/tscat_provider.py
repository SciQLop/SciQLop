from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import QObject, QTimer, Slot
from SciQLop.components.catalogs import (
    Capability,
    Catalog,
    CatalogEvent,
    CatalogProvider,
)

from tscat_gui.tscat_driver.model import tscat_model
from tscat_gui.tscat_driver.actions import SetAttributeAction, CreateEntityAction, RemoveEntitiesAction, AddEventsToCatalogueAction
import tscat
from tscat_gui.model_base.constants import EntityRole


class TscatEvent(CatalogEvent):
    """CatalogEvent wrapping a tscat entity with deferred attribute updates."""

    def __init__(self, entity, parent: QObject | None = None):
        self._entity = entity
        meta = _extract_meta(entity)
        super().__init__(
            uuid=entity.uuid,
            start=entity.start,
            stop=entity.stop,
            meta=meta,
            parent=parent,
        )
        self._deferred_apply = QTimer(self)
        self._deferred_apply.setSingleShot(True)
        self._deferred_apply.timeout.connect(self._apply_changes)
        self._pending_start: datetime | None = None
        self._pending_stop: datetime | None = None

    @property
    def start(self) -> datetime:
        return self._start

    @start.setter
    def start(self, value: datetime) -> None:
        if value != self._start:
            self._start = value
            self._pending_start = value
            self._deferred_apply.start(10)
            self.range_changed.emit()

    @property
    def stop(self) -> datetime:
        return self._stop

    @stop.setter
    def stop(self, value: datetime) -> None:
        if value != self._stop:
            self._stop = value
            self._pending_stop = value
            self._deferred_apply.start(10)
            self.range_changed.emit()

    @Slot()
    def _apply_changes(self) -> None:
        if self._pending_start is None and self._pending_stop is None:
            return
        self._pending_start = self._pending_stop = None
        if self._start > self._stop:
            return
        tscat_model.do(SetAttributeAction(
            user_callback=None, uuids=[self._uuid],
            name="start", values=[self._start],
        ))
        tscat_model.do(SetAttributeAction(
            user_callback=None, uuids=[self._uuid],
            name="stop", values=[self._stop],
        ))


def _extract_meta(entity) -> dict[str, Any]:
    meta: dict[str, Any] = {}
    if hasattr(entity, "author"):
        meta["author"] = entity.author
    if hasattr(entity, "tags"):
        meta["tags"] = entity.tags
    if hasattr(entity, "rating"):
        meta["rating"] = entity.rating
    if hasattr(entity, "variable_attributes"):
        meta.update(entity.variable_attributes())
    return meta


class TscatCatalogProvider(CatalogProvider):
    """CatalogProvider that exposes tscat catalogs via the unified API."""

    def __init__(self, parent: QObject | None = None):
        self._catalog_cache: list[Catalog] | None = None
        self._known_uuids: set[str] = set()
        self._loading_uuids: set[str] = set()
        self._stale_events: dict[str, list[CatalogEvent]] = {}
        self._pending_paths: dict[str, list[str]] = {}
        self._root_model = tscat_model.tscat_root()
        super().__init__(name="My Catalogs", parent=parent)
        tscat_model.action_done.connect(self._on_action_done)
        self._root_model.rowsInserted.connect(self._on_root_rows_changed)
        self._root_model.rowsRemoved.connect(self._on_root_rows_changed)
        self._root_model.modelReset.connect(self._on_root_rows_changed)

    def node_icon(self, node_type, path=None):
        from SciQLop.components.catalogs.backend.provider import NodeType
        if node_type == NodeType.PROVIDER:
            from SciQLop.components.theming import get_icon
            return get_icon("folder_open")
        return None

    def catalogs(self) -> list[Catalog]:
        if self._catalog_cache is not None:
            return list(self._catalog_cache)
        self._catalog_cache = []
        self._known_uuids = set()
        for cat_node in self._root_model.catalogue_nodes(in_trash=False):
            entity = cat_node.node
            path = self._pending_paths.get(entity.uuid)
            if path is None:
                path = getattr(entity, "path__", None)
                if not isinstance(path, list) or not all(isinstance(s, str) for s in path):
                    path = []
            name = getattr(entity, "name", entity.uuid)
            cat = Catalog(
                uuid=entity.uuid,
                name=name,
                provider=self,
                path=path,
            )
            self._catalog_cache.append(cat)
            self._known_uuids.add(entity.uuid)
        return list(self._catalog_cache)

    def events(self, catalog: Catalog, start: datetime | None = None,
               stop: datetime | None = None) -> list[CatalogEvent]:
        if catalog.uuid not in self._events:
            self._load_events(catalog, emit=False)
        return super().events(catalog, start, stop)

    def capabilities(self, catalog: Catalog | None = None) -> set[str]:
        return {
            Capability.EDIT_EVENTS,
            Capability.CREATE_EVENTS,
            Capability.DELETE_EVENTS,
            Capability.CREATE_CATALOGS,
            Capability.DELETE_CATALOGS,
            Capability.SAVE,
        }

    def create_catalog(self, name: str, path: list[str] | None = None) -> Catalog:
        import uuid as _uuid
        self._ensure_clean_session()
        catalog_uuid = str(_uuid.uuid4())
        effective_path = path or []

        # Store path before the action so _on_root_rows_changed → catalogs()
        # picks it up (path__ isn't persisted on the entity yet at that point).
        if effective_path:
            self._pending_paths[catalog_uuid] = effective_path

        def _persist_path(action):
            if effective_path:
                tscat_model.do(SetAttributeAction(
                    user_callback=None,
                    uuids=[catalog_uuid],
                    name="path__",
                    values=[effective_path],
                ))

        # _on_root_rows_changed fires synchronously during do() and emits
        # catalog_added with the correct path (via _pending_paths).
        tscat_model.do(CreateEntityAction(
            user_callback=_persist_path if effective_path else None,
            cls=tscat._Catalogue,
            args=dict(name=name, author="SciQLop", uuid=catalog_uuid),
        ))

        # Return the catalog from cache (built by signal handlers during do()).
        cat = next((c for c in (self._catalog_cache or []) if c.uuid == catalog_uuid), None)
        if cat is None:
            cat = Catalog(uuid=catalog_uuid, name=name, provider=self, path=effective_path)
        self._set_events(cat, [])
        self.mark_dirty(cat)
        return cat

    def remove_catalog(self, catalog: Catalog) -> None:
        tscat_model.do(RemoveEntitiesAction(
            user_callback=None,
            uuids=[catalog.uuid],
            permanently=False,
        ))
        if self._catalog_cache is not None:
            self._catalog_cache = [c for c in self._catalog_cache if c.uuid != catalog.uuid]
            self._known_uuids.discard(catalog.uuid)
        super().remove_catalog(catalog)

    @staticmethod
    def _ensure_clean_session():
        """Rollback any pending transaction left by a prior failed flush."""
        from tscat.base import backend as _tscat_backend
        session = _tscat_backend().session
        if not session.is_active:
            session.rollback()

    def _do_save(self) -> None:
        import tscat
        self._ensure_clean_session()
        tscat.save()

    def add_event(self, catalog: Catalog, event: CatalogEvent) -> None:
        self._ensure_clean_session()

        def _link_to_catalog(action):
            tscat_model.do(AddEventsToCatalogueAction(
                user_callback=None,
                uuids=[action.entity.uuid],
                catalogue_uuid=catalog.uuid,
            ))

        tscat_model.do(CreateEntityAction(
            user_callback=_link_to_catalog,
            cls=tscat._Event,
            args=dict(start=event.start, stop=event.stop, author="SciQLop",
                      uuid=event.uuid),
        ))
        self.mark_dirty(catalog)

    def remove_event(self, catalog: Catalog, event: CatalogEvent) -> None:
        tscat_model.do(RemoveEntitiesAction(
            user_callback=None,
            uuids=[event.uuid],
            permanently=False,
        ))
        super().remove_event(catalog, event)

    def _load_events(self, catalog: Catalog, emit: bool = True) -> None:
        catalog_model = tscat_model.catalog(catalog.uuid)
        if catalog_model.rowCount() > 0:
            self._read_events_from_model(catalog, catalog_model, emit=emit)
        else:
            # tscat loads events asynchronously via GetCatalogueAction;
            # the CatalogModel emits modelReset (not rowsInserted) when done.
            # Poll with a non-blocking QTimer instead of busy-waiting.
            if catalog.uuid not in self._loading_uuids:
                self._loading_uuids.add(catalog.uuid)
                self._deferred_load(catalog, catalog_model, retries=50)

    def _deferred_load(self, catalog: Catalog, catalog_model, retries: int) -> None:
        if catalog_model.rowCount() > 0:
            self._loading_uuids.discard(catalog.uuid)
            self._read_events_from_model(catalog, catalog_model)
        elif retries > 0:
            QTimer.singleShot(100, lambda: self._deferred_load(catalog, catalog_model, retries - 1))
        else:
            self._loading_uuids.discard(catalog.uuid)
            self.error_occurred.emit(f"Timeout loading events for {catalog.name}")
            self._set_events(catalog, [])
            self.events_changed.emit(catalog)

    def _read_events_from_model(self, catalog: Catalog, catalog_model, emit: bool = True) -> None:
        old_by_uuid = {e.uuid: e for e in self._stale_events.pop(catalog.uuid, [])}
        events: list[CatalogEvent] = []
        for row in range(catalog_model.rowCount()):
            idx = catalog_model.index(row, 0)
            entity = idx.data(EntityRole)
            if entity is not None:
                existing = old_by_uuid.get(entity.uuid)
                if existing is not None:
                    existing._entity = entity
                    events.append(existing)
                else:
                    events.append(TscatEvent(entity, parent=self))
        self._set_events(catalog, events)
        if emit:
            self.events_changed.emit(catalog)

    @Slot()
    def _on_root_rows_changed(self, *args) -> None:
        old_uuids = set(self._known_uuids)
        old_catalogs = {c.uuid: c for c in (self._catalog_cache or [])}
        self._catalog_cache = None
        new_catalogs = self.catalogs()
        new_uuids = self._known_uuids

        for cat in new_catalogs:
            if cat.uuid not in old_uuids:
                self.catalog_added.emit(cat)

        removed_uuids = old_uuids - new_uuids
        for uuid in removed_uuids:
            removed_cat = old_catalogs.get(uuid)
            if removed_cat is not None:
                self.catalog_removed.emit(removed_cat)
                # Clean up cached events for removed catalog
                self._events.pop(uuid, None)

    @Slot()
    def _on_action_done(self, action) -> None:
        # SetAttributeAction only updates existing event fields (start/stop);
        # the TscatEvent objects already reflect those changes locally.
        if isinstance(action, SetAttributeAction):
            return
        self._catalog_cache = None
        for catalog in self.catalogs():
            if catalog.uuid in self._events:
                self._stale_events[catalog.uuid] = self._events.pop(catalog.uuid)
                self.events_changed.emit(catalog)
