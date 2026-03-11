from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import uuid as _uuid

from PySide6.QtCore import QObject, QTimer

from SciQLop.components.catalogs import (
    Capability,
    Catalog,
    CatalogEvent,
    CatalogProvider,
)


class CocatEvent(CatalogEvent):
    """CatalogEvent wrapping a cocat Event with deferred writes."""

    def __init__(self, cocat_event, parent: QObject | None = None):
        self._cocat_event = cocat_event
        super().__init__(
            uuid=str(cocat_event.uuid),
            start=cocat_event.start,
            stop=cocat_event.stop,
            meta={},
            parent=parent,
        )
        self._deferred = QTimer(self)
        self._deferred.setSingleShot(True)
        self._deferred.setInterval(100)
        self._deferred.timeout.connect(self._apply)

    @property
    def start(self) -> datetime:
        return self._start

    @start.setter
    def start(self, value: datetime) -> None:
        if value != self._start:
            self._start = value
            self._deferred.start()
            self.range_changed.emit()

    @property
    def stop(self) -> datetime:
        return self._stop

    @stop.setter
    def stop(self, value: datetime) -> None:
        if value != self._stop:
            self._stop = value
            self._deferred.start()
            self.range_changed.emit()

    def _apply(self) -> None:
        self._cocat_event.range = (self._start, self._stop)


class CocatCatalogProvider(CatalogProvider):
    """CatalogProvider wrapping a cocat Room/DB."""

    def __init__(self, room, parent: QObject | None = None):
        self._room = room
        self._catalog_map: dict[str, Catalog] = {}
        super().__init__(name="CoCat", parent=parent)
        self._load_catalogs()

    def _load_catalogs(self) -> None:
        for cat_name in self._room.catalogues:
            cocat_cat = self._room.get_catalogue(cat_name)
            cat = Catalog(
                uuid=str(cocat_cat.uuid) if hasattr(cocat_cat, 'uuid') else cat_name,
                name=cat_name,
                provider=self,
                path=[],
            )
            self._catalog_map[cat.uuid] = cat
            events = []
            for cocat_event in cocat_cat.events:
                events.append(CocatEvent(cocat_event, parent=self))
            self._set_events(cat, events)
            self.catalog_added.emit(cat)

    def catalogs(self) -> list[Catalog]:
        return list(self._catalog_map.values())

    def create_catalog(self, name: str) -> Catalog | None:
        cocat_cat = self._room.db.create_catalogue(name=name, author="SciQLop")
        cat = Catalog(
            uuid=str(cocat_cat.uuid),
            name=name,
            provider=self,
            path=[],
        )
        self._catalog_map[cat.uuid] = cat
        self._set_events(cat, [])
        self.catalog_added.emit(cat)
        return cat

    def rename_catalog(self, catalog: Catalog, new_name: str) -> None:
        cocat_cat = self._room.get_catalogue(catalog.uuid)
        cocat_cat.name = new_name
        catalog.name = new_name
        self.catalog_renamed.emit(catalog)

    def remove_catalog(self, catalog: Catalog) -> None:
        cocat_cat = self._room.get_catalogue(catalog.uuid)
        try:
            cocat_cat.delete()
        except ExceptionGroup:
            pass  # cocat observer bug: KeyError on _catalogue_change_callbacks cleanup
        self._catalog_map.pop(catalog.uuid, None)
        super().remove_catalog(catalog)

    def capabilities(self, catalog: Catalog | None = None) -> set[str]:
        return {
            Capability.EDIT_EVENTS,
            Capability.CREATE_EVENTS,
            Capability.DELETE_EVENTS,
            Capability.CREATE_CATALOGS,
            Capability.DELETE_CATALOGS,
            Capability.RENAME_CATALOG,
        }
