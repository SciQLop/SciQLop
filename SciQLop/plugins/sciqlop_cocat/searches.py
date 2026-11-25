"""Smart catalogues made and changed from SciQLop, mixed into the provider: a search on all events or
on one catalogue of the same project, as text or as a rule (JSON), freezing, and removing the
search. The menus use the CoCat web app's words."""
from __future__ import annotations

import cocat_rs
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from SciQLop.components.catalogs import Catalog, CatalogSearch
from SciQLop.components.sciqlop_logging import getLogger

from . import smart_search
from .convert import SUBPATH_ATTR, encode_subpath
from .history_dialog import ask_text, confirm

log = getLogger(__name__)

NEW_SMART = "New smart catalogue"
REMOVE_SEARCH_QUESTION = "“{name}” keeps the events it lists and stops adding events. The events the search picked leave it."
FREEZE_LABEL = "A normal catalogue holding the events this one picks now. Joined intervals become events you " \
               "can edit. This smart catalogue stays as it is.\n\nName of the normal catalogue:"


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
        if self._is_all_events(catalog):
            return None
        cocat_cat = self._cocat_catalogue(catalog)
        try:
            rule = cocat_cat.rule if cocat_cat is not None else None
        except ValueError as error:  # a rule this cocat-rs cannot read: its tooltip says so
            log.warning("Cannot read the search of '%s': %s", catalog.name, error)
            return None
        if rule is None:
            return None
        source = cocat_cat.query_source
        return CatalogSearch(cocat_cat.query, self._catalogs.get(source.uuid) if source is not None else None, rule,
                             public=cocat_cat.searches_public)

    def set_catalog_search(self, catalog: Catalog, query: str | None = None, source: Catalog | None = None,
                           rule: dict | None = None, public: bool = False) -> None:
        """``public``: the search looks in every public catalogue on the server (needs signing in)."""
        cocat_cat = self._searchable_catalogue(catalog)
        if rule is not None:
            cocat_cat.rule = rule
        else:
            cocat_cat.set_query(query, source=self._source_uuid(catalog.path[0], source), public=public)
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

    # ---- the event table's search box ----

    def event_filter(self, catalog: Catalog, parent):
        if self._room_of(catalog) is None:
            return None
        from .search_filter import CocatSearchFilter
        return CocatSearchFilter(self, catalog, parent)

    def filter_events(self, catalog: Catalog, text: str) -> list:
        """The search box's language: a search as a smart catalogue reads it, or plain words."""
        room = self._room_of(catalog)
        if room is None:
            return super().filter_events(catalog, text)
        kind = room.query_kind(text)
        if kind == "broken":
            room.parse_query(text)  # raises the QueryError that says where
        events = self.events(catalog)
        kept = smart_search.kept_ids(room, kind, text, smart_search.match_items(events), [e.uuid for e in events])
        return events if kept is None else [e for e in events if e.uuid in kept]

    def _can_hold_search(self, catalog: Catalog) -> bool:
        """Its box can save a search as its own: any catalogue of a writable project, but All events."""
        return self._can_save_search_from(catalog) and not self._is_all_events(catalog)

    def _can_save_search_from(self, catalog: Catalog) -> bool:
        """A search typed in its box can become a smart catalogue of the same project."""
        return self._can_search_in(catalog.path[0] if catalog.path else None) and catalog.uuid not in self._links

    def _searchable_catalogue(self, catalog: Catalog):
        if not self._can_search_in(catalog.path[0] if catalog.path else None) or catalog.uuid in self._links \
                or self._is_all_events(catalog):
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

    # ---- the tree's menus ----

    def _search_catalog_actions(self, catalog: Catalog) -> list:
        from .provider import action
        if catalog.uuid not in self._smart or not self._can_search_in(catalog.path[0] if catalog.path else None):
            return []
        return [action("Edit search…", self.open_requested.emit),
                action("Edit as JSON…", self.open_rule_editor),
                action("Freeze…", self._ask_and_freeze),
                action("Remove the search…", self._ask_and_remove_search)]

    def _preset_actions(self, room_id: str) -> list:
        from .provider import action
        if not self._can_search_in(room_id):
            return []
        return [action(p["name"], lambda path, p=p: self._new_smart_catalogue(path, p["name"], p["query"]),
                       p["query"], group=NEW_SMART) for p in cocat_rs.presets(self._author)]

    def _new_smart_catalogue(self, path: list[str], name: str, query: str) -> None:
        try:
            made = self.create_smart_catalog(name, [path[0]], query)
        except Exception as error:
            return self.error_occurred.emit(f"Cannot make the smart catalogue '{name}': {error}")
        self.open_requested.emit(made)

    def open_rule_editor(self, catalog: Catalog):
        from .rule_editor import RuleEditor
        return self._keep_open(RuleEditor(self, catalog, parent=QApplication.activeWindow()))

    def _keep_open(self, dialog):
        """Held until closed: a dialog without a parent window would otherwise go with its last reference."""
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        open_dialogs = self.__dict__.setdefault("_open_dialogs", set())
        open_dialogs.add(dialog)
        dialog.finished.connect(lambda _result: open_dialogs.discard(dialog))
        dialog.show()
        dialog.raise_()
        return dialog

    def _ask_and_freeze(self, catalog: Catalog) -> None:
        name = ask_text(QApplication.activeWindow(), "Freeze", FREEZE_LABEL, f"{catalog.name} (frozen)")
        if not name:
            return
        try:
            self.freeze_catalog(catalog, name)
        except Exception as error:
            self.error_occurred.emit(f"Cannot freeze '{catalog.name}': {error}")

    def _ask_and_remove_search(self, catalog: Catalog) -> None:
        if not confirm(QApplication.activeWindow(), "Remove the search", REMOVE_SEARCH_QUESTION.format(name=catalog.name),
                       "Remove the search"):
            return
        try:
            self.remove_catalog_search(catalog)
        except Exception as error:
            self.error_occurred.emit(f"Cannot remove the search of '{catalog.name}': {error}")
