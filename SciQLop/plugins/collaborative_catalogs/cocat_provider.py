from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional
import uuid as _uuid

from PySide6.QtCore import QObject, QTimer
from PySide6.QtGui import QIcon

from SciQLop.components.catalogs import (
    Capability,
    Catalog,
    CatalogEvent,
    CatalogProvider,
    ProviderAction,
)
from SciQLop.components.theming import register_icon
from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)

__here__ = os.path.dirname(__file__)
register_icon("link", lambda: QIcon(os.path.join(__here__, "..", "..", "resources", "icons", "link.png")))
register_icon("link_off", lambda: QIcon(os.path.join(__here__, "..", "..", "resources", "icons", "link_off.png")))


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
    """Multi-room CoCat provider. Always registered; rooms are joined on demand."""

    def __init__(self, url: str = "https://sciqlop.lpp.polytechnique.fr/cocat/",
                 parent: QObject | None = None):
        self._url = url
        self._catalog_map: dict[str, Catalog] = {}
        self._rooms: dict[str, object] = {}       # room_id → Room (joined)
        self._available_rooms: list[str] = []      # room_ids from server
        self._default_room_id: str | None = None
        self._connected = False
        self._client_for_listing = None
        super().__init__(name="Shared", parent=parent)

    def node_icon(self, node_type, path=None):
        from SciQLop.components.catalogs.backend.provider import NodeType
        if node_type == NodeType.PROVIDER:
            from SciQLop.components.theming import get_icon
            return get_icon("link" if self._connected else "link_off")
        return None

    @property
    def connected(self) -> bool:
        return self._connected

    def connect_to_server(self) -> bool:
        """Login and list available rooms. Returns True on success."""
        from .client import Client
        client = Client(url=self._url, parent=self)
        if not client.login():
            return False
        self._client_for_listing = client
        self._default_room_id = client.room_id
        rooms = client.list_rooms() or []
        self._connected = True
        self.status_changed.emit()
        self._available_rooms = rooms
        # Emit default room first
        if self._default_room_id and self._default_room_id in rooms:
            rooms = [self._default_room_id] + [r for r in rooms if r != self._default_room_id]
            self._available_rooms = rooms
        for room_id in rooms:
            self.folder_added.emit([room_id])
        log.info("CoCat connected: %d rooms available", len(rooms))
        return True

    def disconnect_from_server(self) -> None:
        """Leave all rooms and clear state (sync — does not close WebSockets)."""
        for room_id in list(self._rooms.keys()):
            self._detach_room_catalogs(room_id)
        self._rooms.clear()
        for room_id in list(self._available_rooms):
            self.folder_removed.emit([room_id])
        self._available_rooms.clear()
        self._default_room_id = None
        self._connected = False
        self._client_for_listing = None
        self.status_changed.emit()

    async def async_close(self) -> None:
        """Async shutdown: properly close all room WebSocket connections."""
        for room_id in list(self._rooms.keys()):
            room = self._rooms.pop(room_id, None)
            if room is not None:
                await room.close()
        self._connected = False

    async def join_room(self, room_id: str) -> None:
        """Join a room and load its catalogs."""
        if room_id in self._rooms:
            return
        from .room import Room
        room = Room(url=self._url, room_id=room_id, parent=self)
        if not await room.join():
            self.error_occurred.emit(f"Failed to join room '{room_id}'")
            return
        self._rooms[room_id] = room
        self._load_room_catalogs(room_id, room)
        log.info("Joined room '%s', loaded %d catalogs", room_id,
                 sum(1 for c in self._catalog_map.values() if c.path == [room_id]))

    def _detach_room_catalogs(self, room_id: str) -> None:
        """Remove catalogs from a room (sync, no WebSocket close)."""
        catalogs_to_remove = [c for c in self._catalog_map.values() if c.path == [room_id]]
        for cat in catalogs_to_remove:
            self._catalog_map.pop(cat.uuid, None)
            super().remove_catalog(cat)

    def _leave_room(self, room_id: str) -> None:
        """Leave a room: detach catalogs and schedule async WebSocket close."""
        self._detach_room_catalogs(room_id)
        room = self._rooms.pop(room_id, None)
        if room is not None:
            import asyncio
            asyncio.ensure_future(room.close())

    def _load_room_catalogs(self, room_id: str, room) -> None:
        for cat_name in room.catalogues:
            cocat_cat = room.get_catalogue(cat_name)
            cat = Catalog(
                uuid=str(cocat_cat.uuid) if hasattr(cocat_cat, 'uuid') else cat_name,
                name=cat_name,
                provider=self,
                path=[room_id],
            )
            self._catalog_map[cat.uuid] = cat
            events = [CocatEvent(ev, parent=self) for ev in cocat_cat.events]
            self._set_events(cat, events)
            self.catalog_added.emit(cat)

    def _room_for_catalog(self, catalog: Catalog):
        """Get the Room instance for a catalog's room."""
        if catalog.path:
            return self._rooms.get(catalog.path[0])
        return None

    def _cocat_catalogue(self, catalog: Catalog):
        """Get the cocat Catalogue object for a Catalog."""
        room = self._room_for_catalog(catalog)
        if room is None:
            return None
        return room.get_catalogue(catalog.uuid)

    # ---- CatalogProvider interface ----

    def catalogs(self) -> list[Catalog]:
        return list(self._catalog_map.values())

    def add_event(self, catalog: Catalog, event: CatalogEvent) -> None:
        cocat_cat = self._cocat_catalogue(catalog)
        if cocat_cat is None:
            return
        room = self._room_for_catalog(catalog)
        cocat_event = room.db.create_event(
            start=event.start, stop=event.stop, author="SciQLop",
            uuid=event.uuid,
        )
        cocat_cat.add_events([cocat_event])
        wrapped = CocatEvent(cocat_event, parent=self)
        self._add_event(catalog, wrapped)

    def remove_event(self, catalog: Catalog, event: CatalogEvent) -> None:
        cocat_cat = self._cocat_catalogue(catalog)
        if cocat_cat is None:
            return
        self._remove_event(catalog, event)
        if isinstance(event, CocatEvent):
            cocat_cat.remove_events([event._cocat_event])
            event._cocat_event.delete()
        else:
            try:
                room = self._room_for_catalog(catalog)
                cocat_event = room.db.get_event(event.uuid)
                cocat_cat.remove_events([cocat_event])
                cocat_event.delete()
            except Exception:
                log.warning("Could not remove event %s from cocat backend", event.uuid)

    def create_catalog(self, name: str, path: list[str] | None = None) -> Catalog:
        room_id = path[0] if path else self._default_room_id
        if room_id not in self._rooms:
            if path:
                raise KeyError(f"Room '{room_id}' is not joined")
            room_id = next(iter(self._rooms), None)
        if room_id is None:
            raise RuntimeError("No rooms joined")
        room = self._rooms[room_id]
        cocat_cat = room.db.create_catalogue(name=name, author="SciQLop")
        cat = Catalog(
            uuid=str(cocat_cat.uuid),
            name=name,
            provider=self,
            path=[room_id],
        )
        self._catalog_map[cat.uuid] = cat
        self._set_events(cat, [])
        self.catalog_added.emit(cat)
        return cat

    def rename_catalog(self, catalog: Catalog, new_name: str) -> None:
        room = self._room_for_catalog(catalog)
        if room is None:
            return
        cocat_cat = room.get_catalogue(catalog.uuid)
        cocat_cat.name = new_name
        catalog.name = new_name
        self.catalog_renamed.emit(catalog)

    def remove_catalog(self, catalog: Catalog) -> None:
        room = self._room_for_catalog(catalog)
        if room is None:
            return
        cocat_cat = room.get_catalogue(catalog.uuid)
        try:
            cocat_cat.delete()
        except ExceptionGroup:
            pass  # cocat observer bug: KeyError on _catalogue_change_callbacks cleanup
        self._catalog_map.pop(catalog.uuid, None)
        super().remove_catalog(catalog)

    def capabilities(self, catalog: Catalog | None = None) -> set[str]:
        if not self._rooms:
            return set()
        return {
            Capability.EDIT_EVENTS,
            Capability.CREATE_EVENTS,
            Capability.DELETE_EVENTS,
            Capability.CREATE_CATALOGS,
            Capability.DELETE_CATALOGS,
            Capability.RENAME_CATALOG,
        }

    def actions(self, catalog: Catalog | None = None) -> list[ProviderAction]:
        if catalog is not None:
            return []
        if not self._connected:
            return [ProviderAction(name="Connect", callback=lambda _: self.connect_to_server())]
        return [ProviderAction(name="Disconnect", callback=lambda _: self.disconnect_from_server())]

    def folder_actions(self, path: list[str]) -> list[ProviderAction]:
        if len(path) != 1:
            return []
        room_id = path[0]
        if room_id in self._rooms:
            return [ProviderAction(name="Leave", callback=lambda p: self._leave_room(p[0]))]
        return [ProviderAction(name="Join", callback=self._join_room_from_action)]

    def _join_room_from_action(self, path: list[str]) -> None:
        from qasync import asyncSlot
        import asyncio
        asyncio.ensure_future(self.join_room(path[0]))

    def folder_display_name(self, path: list[str]) -> str | None:
        if len(path) == 1 and path[0] == self._default_room_id:
            return f"{path[0]} (default)"
        return None
