from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import QObject, QThread, QTimer, Slot

from SciQLop.components.catalogs import (
    Capability,
    Catalog,
    CatalogEvent,
    CatalogProvider,
)

from tscat_gui.tscat_driver.model import tscat_model
from tscat_gui.tscat_driver.actions import SetAttributeAction
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
        if self._pending_start is not None:
            tscat_model.do(SetAttributeAction(
                user_callback=None, uuids=[self._uuid],
                name="start", values=[self._pending_start],
            ))
            self._pending_start = None
        if self._pending_stop is not None:
            tscat_model.do(SetAttributeAction(
                user_callback=None, uuids=[self._uuid],
                name="stop", values=[self._pending_stop],
            ))
            self._pending_stop = None


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
        self._root_model = tscat_model.tscat_root()
        super().__init__(name="TSCat Local", parent=parent)
        tscat_model.action_done.connect(self._on_action_done)
        self._root_model.rowsInserted.connect(self._on_root_rows_changed)
        self._root_model.rowsRemoved.connect(self._on_root_rows_changed)
        self._root_model.modelReset.connect(self._on_root_rows_changed)

    def catalogs(self) -> list[Catalog]:
        if self._catalog_cache is not None:
            return list(self._catalog_cache)
        self._catalog_cache = []
        self._known_uuids = set()
        for cat_node in self._root_model.catalogue_nodes(in_trash=False):
            entity = cat_node.node
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
            self._load_events(catalog)
        return super().events(catalog, start, stop)

    def capabilities(self, catalog: Catalog | None = None) -> set[str]:
        return {
            Capability.EDIT_EVENTS,
            Capability.CREATE_EVENTS,
            Capability.DELETE_EVENTS,
            Capability.CREATE_CATALOGS,
        }

    def _load_events(self, catalog: Catalog) -> None:
        from SciQLop.core.sciqlop_application import sciqlop_app
        catalog_model = tscat_model.catalog(catalog.uuid)
        # tscat catalog models load events asynchronously;
        # busy-wait until rowCount becomes non-zero (matches LightweightManager approach)
        for _ in range(5000):
            if catalog_model.rowCount() == 0:
                sciqlop_app().processEvents()
                QThread.sleep(1)
            else:
                break
        events: list[CatalogEvent] = []
        for row in range(catalog_model.rowCount()):
            idx = catalog_model.index(row, 0)
            entity = idx.data(EntityRole)
            if entity is not None:
                events.append(TscatEvent(entity, parent=self))
        self._set_events(catalog, events)

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
        self._catalog_cache = None
        for catalog in self.catalogs():
            if catalog.uuid in self._events:
                del self._events[catalog.uuid]
                self.events_changed.emit(catalog)
