from __future__ import annotations
import uuid as _uuid
from datetime import datetime, timedelta, timezone

from PySide6.QtCore import QObject

from .provider import Capability, Catalog, CatalogEvent, CatalogProvider


class DummyProvider(CatalogProvider):
    """Full-capability in-memory provider for testing and as reference."""

    def __init__(self, num_catalogs: int = 1, events_per_catalog: int = 100,
                 paths: list[list[str]] | None = None,
                 parent: QObject | None = None):
        super().__init__(name="DummyProvider", parent=parent)
        self._catalogs: list[Catalog] = []
        base = datetime(2020, 1, 1, tzinfo=timezone.utc)
        for c in range(num_catalogs):
            path = paths[c] if paths and c < len(paths) else []
            cat = Catalog(
                uuid=str(_uuid.uuid4()),
                name=f"Catalog-{c}",
                provider=self,
                path=path,
            )
            self._catalogs.append(cat)
            events = []
            for i in range(events_per_catalog):
                events.append(CatalogEvent(
                    uuid=str(_uuid.uuid4()),
                    start=base + timedelta(days=i),
                    stop=base + timedelta(days=i, hours=1),
                    meta={"index": i, "catalog": c},
                ))
            self._set_events(cat, events)

    def catalogs(self) -> list[Catalog]:
        return list(self._catalogs)

    def capabilities(self, catalog: Catalog | None = None) -> set[str]:
        return {
            Capability.EDIT_EVENTS,
            Capability.CREATE_EVENTS,
            Capability.DELETE_EVENTS,
            Capability.CREATE_CATALOGS,
            Capability.DELETE_CATALOGS,
            Capability.EXPORT_EVENTS,
            Capability.IMPORT_EVENTS,
            Capability.SAVE,
            Capability.SAVE_CATALOG,
            Capability.RENAME_CATALOG,
        }

    def create_catalog(self, name: str) -> Catalog | None:
        cat = Catalog(
            uuid=str(_uuid.uuid4()),
            name=name,
            provider=self,
            path=[],
        )
        self._catalogs.append(cat)
        self._set_events(cat, [])
        self.catalog_added.emit(cat)
        return cat

    def rename_catalog(self, catalog: Catalog, new_name: str) -> None:
        catalog.name = new_name
        self.catalog_renamed.emit(catalog)

    def remove_catalog(self, catalog: Catalog) -> None:
        self._catalogs = [c for c in self._catalogs if c.uuid != catalog.uuid]
        super().remove_catalog(catalog)

    def import_events(self, catalog_name: str, events: list[CatalogEvent], path: list[str] | None = None) -> Catalog:
        cat = Catalog(
            uuid=str(_uuid.uuid4()),
            name=catalog_name,
            provider=self,
            path=path or [],
        )
        self._catalogs.append(cat)
        self._set_events(cat, events)
        self.catalog_added.emit(cat)
        return cat
