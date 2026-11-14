"""Links: bookmarks in My catalogues to catalogues of other projects. cocat-rs keeps them in the
personal project; SciQLop shows each one under "Linked", read-only, with the original catalogue's
events. They are the same event objects as under the original project, so edits made there show at
once; what the catalogue holds is re-read with the smart catalogues."""
from __future__ import annotations

import cocat_rs

from SciQLop.components.catalogs import Catalog

from . import tips

from .sharing_dialog import describe

LINKED = "Linked"
VIEW_PREFIX = "link/"  # a link's own uuid in SciQLop: the original keeps its uuid under its project


class Linking:
    """Mixed into the provider: its rooms, catalogues and wrappers are used as they are."""

    def _links_home(self) -> str | None:
        """My catalogues, when joined: where links live."""
        info = self._room_infos.get(self._default_room_id)
        return info.id if info is not None and info.personal and info.id in self._rooms else None

    def show_links(self) -> None:
        for uuid in list(self._links):
            if (catalog := self._catalogs.get(uuid)) is not None:
                self._forget_catalog(catalog)
        self._links = {}
        home = self._links_home()
        if home is None:
            return
        for link in self._rooms[home].links():
            self._wrap_link(home, link)

    def links_may_have_changed(self, room_id: str) -> None:
        """After remote changes: My catalogues may hold new links (no cocat-rs call reports them), and
        a link's catalogue may just have arrived."""
        home = self._links_home()
        if room_id == home and {link["id"] for link in self._rooms[home].links()} != \
                {link["id"] for link in self._links.values()}:
            self.show_links()
        for catalog in self._links_from(room_id):
            self.reload_catalog(catalog)

    def _wrap_link(self, home: str, link: dict) -> None:
        catalog = Catalog(uuid=VIEW_PREFIX + link["id"], name=f"{link['name']} (from {link['project_name']})",
                          provider=self, path=[home, LINKED])
        self._links[catalog.uuid] = link
        self._catalogs[catalog.uuid] = catalog
        source = self._linked_catalogue(catalog)
        self._set_events(catalog, self._readable_members(catalog, source) if source is not None else [])
        self.catalog_added.emit(catalog)

    def _linked_catalogue(self, catalog: Catalog):
        link = self._links[catalog.uuid]
        room = self._rooms.get(link["project"])
        if room is None:
            return None
        try:
            return room.catalogue(link["catalogue"])
        except cocat_rs.NotFound:
            return None

    def _links_from(self, room_id: str) -> list[Catalog]:
        return [self._catalogs[uuid] for uuid, link in self._links.items()
                if link["project"] == room_id and uuid in self._catalogs]

    def link_into_personal(self, catalog: Catalog) -> None:
        home = self._links_home()
        try:
            self._rooms[home].link(self._cocat_catalogue(catalog))
        except Exception as error:
            self.error_occurred.emit(f"Cannot link '{catalog.name}' into My catalogues: {describe(error)}")
            return
        self.show_links()

    def unlink(self, catalog: Catalog) -> None:
        self._rooms[self._links_home()].unlink(self._links[catalog.uuid]["id"])
        self.show_links()

    def _can_link(self, catalog: Catalog) -> bool:
        home = self._links_home()
        source = catalog.path[0] if catalog.path else None
        return (home is not None and self._can_write(home) and source in self._rooms and source != home
                and source not in self._local_ids and source not in self._public_ids)

    def link_tip(self, catalog: Catalog) -> str:
        link = self._links[catalog.uuid]
        readable = self._linked_catalogue(catalog) is not None
        return tips.link_tip(catalog.name, link, events=self._events.get(catalog.uuid, []) if readable else None,
                             problem=None if readable else self._link_problem(link))

    def _link_problem(self, link: dict) -> str:
        project = link["project_name"]
        if link["project"] in self._room_infos and link["project"] not in self._rooms:
            return f"Join {project} to see it"
        if not self._connected:
            return f"Sign in to see it (linked from {project})"
        return f"Not available: you are not a member of {project} any more, or the catalogue was deleted"
