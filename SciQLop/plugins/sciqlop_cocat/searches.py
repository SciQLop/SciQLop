"""Smart catalogues made and changed from SciQLop, mixed into the provider: a search on all events or
on one catalogue of the same project, as text or as a rule (JSON), freezing, and removing the
search."""
from __future__ import annotations


from SciQLop.components.catalogs import Catalog, CatalogSearch
from SciQLop.components.sciqlop_logging import getLogger

from .convert import SUBPATH_ATTR, encode_subpath

log = getLogger(__name__)

class Searching:
    """Mixed into the provider: its rooms, catalogues and reads are used as they are."""

    # ---- the provider API (Capability.SEARCHES) ----

    def create_smart_catalog(self, name: str, path: list[str] | None, query: str,
                             source: Catalog | None = None) -> Catalog:
        room_id = self._room_for_new_catalog(path)
        self._rooms[room_id].parse_query(query, source=self._source_uuid(room_id, source))  # nothing made if wrong
        catalog = self.create_catalog(name, path)
        self.set_catalog_search(catalog, query, source)
        return catalog

    def catalog_search(self, catalog: Catalog) -> CatalogSearch | None:
        cocat_cat = self._cocat_catalogue(catalog)
        try:
            rule = cocat_cat.rule if cocat_cat is not None else None
        except ValueError as error:  # a rule this cocat-rs cannot read: its tooltip says so
            log.warning("Cannot read the search of '%s': %s", catalog.name, error)
            return None
        if rule is None:
            return None
        source = cocat_cat.query_source
        return CatalogSearch(cocat_cat.query, self._catalogs.get(source.uuid) if source is not None else None, rule)

    def set_catalog_search(self, catalog: Catalog, query: str | None = None, source: Catalog | None = None,
                           rule: dict | None = None) -> None:
        cocat_cat = self._searchable_catalogue(catalog)
        if rule is not None:
            cocat_cat.rule = rule
        else:
            cocat_cat.set_query(query, source=self._source_uuid(catalog.path[0], source))
        self._search_changed(catalog, cocat_cat)

    def remove_catalog_search(self, catalog: Catalog) -> None:
        cocat_cat = self._searchable_catalogue(catalog)
        cocat_cat.rule = None
        self._search_changed(catalog, cocat_cat)

    def freeze_catalog(self, catalog: Catalog, name: str) -> Catalog:
        cocat_cat = self._searchable_catalogue(catalog)
        room_id = catalog.path[0]
        frozen = cocat_cat.materialize(name)
        if catalog.path[1:]:
            frozen.set_attributes(**{SUBPATH_ATTR: encode_subpath(list(catalog.path[1:]))})
        return self._catalogs.get(frozen.uuid) or self._wrap_catalogue(room_id, frozen)

    def _searchable_catalogue(self, catalog: Catalog):
        if not self._can_search_in(catalog.path[0] if catalog.path else None) or catalog.uuid in self._links:
            raise PermissionError(f"'{catalog.name}' is read-only for you")
        cocat_cat = self._cocat_catalogue(catalog)
        if cocat_cat is None:
            raise KeyError(f"'{catalog.name}' is not available now")
        return cocat_cat

    def _source_uuid(self, room_id: str, source: Catalog | None) -> str | None:
        if source is None:
            return None
        if not source.path or source.path[0] != room_id:
            raise ValueError(f"A search looks in a catalogue of its own project; '{source.name}' is in another")
        return source.uuid

    def _search_changed(self, catalog: Catalog, cocat_cat) -> None:
        """Its rights, icon and members follow; the members are read in the background."""
        self._note_rule(catalog, cocat_cat)
        self._unread.discard(catalog.uuid)
        if catalog.uuid not in self._first_reads:  # loading until its new members are shown
            self._first_reads.add(catalog.uuid)
            self.loading_started.emit(catalog)
        self._queue_rereads([catalog])
        self.capabilities_changed.emit(catalog)

    def _can_search_in(self, room_id: str | None) -> bool:
        return room_id in self._rooms and room_id not in self._public_ids and self._can_write(room_id)
