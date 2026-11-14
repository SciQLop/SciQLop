"""Public catalogues. Each one is a project of one catalogue that every signed-in account reads and
the server keeps up to date (curators, or a relay from DONKI, AMDA, ...). All of them are listed
under "Public catalogues", read-only; one is downloaded the first time it is opened, then followed
live: kept in sync, and joined again at the next start."""
from __future__ import annotations

import asyncio
from pathlib import Path

import cocat_rs

from SciQLop.components.catalogs import Catalog
from SciQLop.components.sciqlop_logging import getLogger

from .sharing_dialog import describe

log = getLogger(__name__)

KEPT = ("id", "name", "folder", "description", "relay", "count")
PUBLIC = "public"  # the folder listing them; project ids are uuids or "public.<key>", never this
PUBLIC_FOLDER = "Public catalogues"
VIEW_PREFIX = "public/"  # a listed catalogue's uuid in SciQLop, before its own is known


def folder_path(folder: str | None) -> list[str]:
    """The server writes a folder as "Literature/Earth": one tree level per part."""
    return [part for part in (folder or "").split("/") if part]


def as_info(row: dict):
    return cocat_rs.ProjectInfo(row["id"], row["name"], "viewer")


class Following:
    """Mixed into the provider: its rooms, infos and remembered state are used as they are."""

    async def _public_rows(self) -> list[dict]:
        """The server's list, plus the followed ones it no longer lists (their room says if they are
        gone); only the followed ones while the server cannot be reached."""
        followed = self._remembered.followed
        if self._offline:
            return followed
        try:
            listed = await self._session.call(cocat_rs.raw.public_catalogues) or []
        except Exception as error:
            log.warning("Cannot list the public catalogues: %s", describe(error))
            return followed
        ids = {row["id"] for row in listed}
        return [*listed, *(row for row in followed if row["id"] not in ids)]

    # ---- the listed views ----

    def show_public(self, rows: list[dict]) -> None:
        self._hide_public()
        if rows:
            self.folder_added.emit([PUBLIC])
        for row in rows:
            self._wrap_public(row)

    def _hide_public(self) -> None:
        for uuid in list(self._public_views):
            if (catalog := self._catalogs.get(uuid)) is not None:
                self._forget_catalog(catalog)
        if self._public_views:
            self.folder_removed.emit([PUBLIC])
        self._public_views = {}
        self._public_loading = set()

    def _wrap_public(self, row: dict) -> None:
        catalog = Catalog(uuid=VIEW_PREFIX + row["id"], name=row["name"], provider=self,
                          path=[PUBLIC, *folder_path(row.get("folder"))])
        self._public_views[catalog.uuid] = row
        self._catalogs[catalog.uuid] = catalog
        source = self._public_source(catalog)
        self._set_events(catalog, self._readable_members(catalog, source) if source is not None else [])
        self.catalog_added.emit(catalog)

    def _public_room_id(self, catalog: Catalog) -> str | None:
        row = self._public_views.get(catalog.uuid)
        return row["id"] if row is not None else None

    def _public_source(self, catalog: Catalog):
        room = self._rooms.get(self._public_room_id(catalog))
        catalogues = room.catalogues() if room is not None else []
        return catalogues[0] if catalogues else None

    def _public_views_of(self, room_id: str) -> list[Catalog]:
        return [self._catalogs[uuid] for uuid, row in self._public_views.items()
                if row["id"] == room_id and uuid in self._catalogs]

    def public_may_have_changed(self, room_id: str) -> None:
        """After remote changes or a sync: the catalogue may just have arrived."""
        synced = self.room_status(room_id) == "synced"
        for catalog in self._public_views_of(room_id):
            if self._public_source(catalog) is not None:
                self.reload_catalog(catalog)
            if synced:
                self._loaded(catalog)

    # ---- loading on first open ----

    def events(self, catalog: Catalog, start=None, stop=None):
        row = self._public_views.get(catalog.uuid)
        if row is not None and row["id"] not in self._rooms and self._online():
            self._start_loading(catalog, row)
        return super().events(catalog, start, stop)

    def is_loading(self, catalog: Catalog) -> bool:
        return catalog.uuid in self._public_loading

    def _start_loading(self, catalog: Catalog, row: dict) -> None:
        if catalog.uuid in self._public_loading:
            return
        self._public_loading.add(catalog.uuid)
        self.loading_started.emit(catalog)
        asyncio.ensure_future(self._load(catalog, row))

    async def _load(self, catalog: Catalog, row: dict) -> None:
        await self.follow(row)
        if row["id"] not in self._rooms:  # joining failed, and said why
            self._loaded(catalog)

    def _loaded(self, catalog: Catalog) -> None:
        if catalog.uuid in self._public_loading:
            self._public_loading.discard(catalog.uuid)
            self.loading_finished.emit(catalog)

    # ---- following ----

    def _followed_row(self, room_id: str) -> dict | None:
        return next((row for row in self._remembered.followed if row["id"] == room_id), None)

    async def follow(self, row: dict) -> None:
        if self._followed_row(row["id"]) is None:
            self._remembered.followed = [*self._remembered.followed, {key: row.get(key) for key in KEPT}]
        self._public_ids.add(row["id"])
        self._room_infos[row["id"]] = as_info(row)
        await self.join_room(row["id"])
        self.public_may_have_changed(row["id"])
        self.status_changed.emit()

    def unfollow(self, room_id: str) -> None:
        """Listed again afresh: a view left selected would be re-read, and so downloaded again."""
        self.leave_room(room_id)
        self._forget_followed(room_id)
        for path in Path(self._cache_dir).glob(f"{room_id}.*"):
            path.unlink()
        for catalog in self._public_views_of(room_id):
            row = self._drop_view(catalog)
            self._wrap_public(row)
        self.status_changed.emit()

    def _drop_view(self, catalog: Catalog) -> dict:
        self._loaded(catalog)
        self._forget_catalog(catalog)
        return self._public_views.pop(catalog.uuid)

    def _forget_followed(self, room_id: str) -> None:
        self._remembered.followed = [row for row in self._remembered.followed if row["id"] != room_id]
        self._public_ids.discard(room_id)
        self._room_infos.pop(room_id, None)

    def lose_public(self, room_id: str) -> None:
        """No longer public: nothing left to follow, nor to list."""
        self.unfollow(room_id)
        for catalog in self._public_views_of(room_id):
            self._drop_view(catalog)
