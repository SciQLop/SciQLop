"""Each open project's "All events", as the CoCat web app has it: every event of the project not in
the trash. A view, read like a smart catalogue (once opened, in the background, then by difference
after edits) through a stand-in for a cocat-rs catalogue whose rule is "all"; nothing to rename,
delete or edit, and no search of its own."""
from __future__ import annotations

from SciQLop.components.catalogs import Catalog

ALL_EVENTS = "All events"
ALL_EVENTS_PREFIX = "all-events:"
ALL_RULE = {"all": True}


class _AllEventsSource:
    """What the reads ask of a cocat-rs catalogue, for every event of the project."""
    rule = ALL_RULE
    searches_public = False
    columns: list[str] = []

    def __init__(self, room, uuid: str):
        self._room, self.uuid = room, uuid

    def event_arrays(self, attributes: bool = False) -> dict:
        arrays = self._room.preview(ALL_RULE, attributes=attributes)
        arrays.pop("count", None)
        return arrays


class ShowingAllEvents:
    """Mixed into the provider: its catalogues and reads are used as they are."""

    def _show_all_events(self, room_id: str) -> None:
        uuid = ALL_EVENTS_PREFIX + room_id
        if uuid in self._catalogs:
            return
        catalog = Catalog(uuid=uuid, name=ALL_EVENTS, provider=self, path=[room_id])
        self._catalogs[uuid] = catalog
        self._smart.add(uuid)
        self._unread.add(uuid)  # read once opened
        self._set_events(catalog, [])
        self.catalog_added.emit(catalog)

    @staticmethod
    def _is_all_events(catalog: Catalog) -> bool:
        return catalog.uuid.startswith(ALL_EVENTS_PREFIX)

    def _all_events_source(self, catalog: Catalog):
        room = self._rooms.get(catalog.path[0]) if catalog.path else None
        return _AllEventsSource(room, catalog.uuid) if room is not None else None
