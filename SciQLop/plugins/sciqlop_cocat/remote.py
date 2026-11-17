"""Applies one room's remote changes to the provider.

cocat-rs calls these methods on the Qt thread, for changes made by other clients only. A change
naming a catalogue or event this provider does not hold is ignored: it was not loaded, or is
already gone.
"""
from __future__ import annotations

import cocat_rs

from SciQLop.components.sciqlop_logging import getLogger

from .convert import SUBPATH_ATTR, decode_subpath, rows_of, schema_key, schema_specs, typed_meta

log = getLogger(__name__)


class RoomListener:
    def __init__(self, provider, room_id: str):
        self._provider = provider
        self._room_id = room_id

    @property
    def _room(self):
        return self._provider._rooms.get(self._room_id)

    def _catalog(self, uuid: str):
        catalog = self._provider._catalogs.get(uuid)
        if catalog is None or catalog.path[0] != self._room_id:
            log.debug("Remote change for unknown catalogue %s ignored", uuid)
            return None
        return catalog

    def _wrapper(self, uuid: str):
        return self._provider._wrappers.get(self._room_id, {}).get(uuid)

    def _catalogs_holding(self, wrapper):
        return [c for c in self._provider._catalogs_of(self._room_id)
                if wrapper in self._provider._events.get(c.uuid, [])]

    def _read_events(self, uuids: list[str]):
        """Unknown uuids are left out: those events are already gone."""
        rows = rows_of(self._room.event_arrays(uuids, attributes=True)) if uuids else []
        return [self._provider._wrapper(self._room_id, r.uuid, r.start, r.stop, r.meta) for r in rows]

    # ---- catalogues ----

    def catalogue_added(self, uuid):
        if uuid in self._provider._catalogs or self._room is None or self._room_id in self._provider._public_ids:
            return  # a public catalogue shows through its listed view, re-read once the changes are done
        try:
            cocat_cat = self._room.catalogue(uuid)
        except cocat_rs.NotFound:
            return log.debug("Remote catalogue %s is gone", uuid)
        with self._provider.remote_changes():
            self._provider._wrap_catalogue(self._room_id, cocat_cat)

    def catalogue_removed(self, uuid):
        catalog = self._catalog(uuid)
        if catalog is not None:
            self._provider._forget_catalog(catalog)

    def catalogue_renamed(self, uuid, name):
        catalog = self._catalog(uuid)
        if catalog is not None and catalog.name != name:
            catalog.name = name
            self._provider.catalog_renamed.emit(catalog)

    def catalogue_rule(self, uuid):
        catalog = self._catalog(uuid)
        if catalog is not None:
            self._provider.reload_catalog(catalog)

    def catalogue_attributes(self, uuid, set, removed):
        catalog = self._catalog(uuid)
        if catalog is None:
            return
        if SUBPATH_ATTR in set or SUBPATH_ATTR in removed:
            self._move(catalog, decode_subpath(set.get(SUBPATH_ATTR)))
        self._update_specs(catalog, set, removed)

    def _move(self, catalog, sub_path):
        new_path = [self._room_id, *sub_path]
        if list(catalog.path) != new_path:
            catalog.path = new_path
            self._provider.catalog_moved.emit(catalog)

    def _update_specs(self, catalog, set, removed):
        specs = self._provider._attribute_specs
        changed = list(schema_specs(set).items())
        for key, spec in changed:
            specs.setdefault(catalog.uuid, {})[key] = spec
        dropped = [k for k in map(schema_key, removed)
                   if k is not None and specs.get(catalog.uuid, {}).pop(k, None) is not None]
        for key in [k for k, _ in changed] + dropped:
            self._provider.attribute_spec_changed.emit(catalog, key)

    # ---- events ----

    def events_added(self, catalogue, uuids):
        catalog = self._catalog(catalogue)
        if catalog is None:
            return
        held = {e.uuid for e in self._provider._events.get(catalog.uuid, [])}
        wrappers = self._read_events([u for u in uuids if u not in held])
        with self._provider.remote_changes(), self._provider.batch_events_update(catalog):
            for wrapper in wrappers:
                self._provider._add_event(catalog, wrapper)
        self._provider.mark_smart_dirty(self._room_id)

    def events_removed(self, catalogue, uuids):
        catalog = self._catalog(catalogue)
        if catalog is None:
            return
        targets = set(uuids)
        with self._provider.batch_events_update(catalog):
            for event in [e for e in self._provider._events.get(catalog.uuid, []) if e.uuid in targets]:
                self._provider._remove_event(catalog, event)
        self._provider.mark_smart_dirty(self._room_id)

    def event_range(self, uuid, start, stop):
        wrapper = self._wrapper(uuid)
        if wrapper is not None:
            with self._provider.remote_changes():
                wrapper.apply_remote_range(start, stop)
        self._provider.mark_smart_dirty(self._room_id)

    def event_attributes(self, uuid, set, removed):
        wrapper = self._wrapper(uuid)
        if wrapper is None:
            return
        for key, value in set.items():
            wrapper.set_meta(key, value)
        for key in removed:
            wrapper.remove_meta(key)
        for catalog in self._catalogs_holding(wrapper):
            for key in [*set, *removed]:
                self._provider.event_meta_changed.emit(catalog, wrapper, key)
        self._provider.mark_smart_dirty(self._room_id)

    def event_fields(self, uuid, set, removed):
        """Typed fields (tags, status, confidence...). A status of "deleted" is the trash."""
        if set.get("status") == "deleted":
            self.event_removed(uuid)
        elif "status" in set or "status" in removed:
            self._restore(uuid)
        if {"tags", "confidence"} & ({*set} | {*removed}):
            self._typed_fields_changed(uuid)
        self._provider.mark_smart_dirty(self._room_id)

    def _typed_fields_changed(self, uuid):
        """Tags and confidence show as the event's tags and rating, as a bulk read gives them."""
        wrapper = self._wrapper(uuid)
        try:
            stored = self._room.event(uuid)
        except cocat_rs.NotFound:
            return
        if wrapper is None:
            return
        now = typed_meta(stored.tags, stored.confidence)
        changed = [key for key in ("tags", "rating") if wrapper.meta.get(key) != now.get(key)]
        for key in changed:
            if key in now:
                wrapper.set_meta(key, now[key])
            else:
                wrapper.remove_meta(key)
        for catalog in self._catalogs_holding(wrapper):
            for key in changed:
                self._provider.event_meta_changed.emit(catalog, wrapper, key)

    def _restore(self, uuid):
        try:
            catalogues = self._room.event(uuid).catalogues
        except cocat_rs.NotFound:
            return
        for catalogue in catalogues:
            self.events_added(catalogue, [uuid])

    def event_removed(self, uuid):
        wrapper = self._provider._wrappers.get(self._room_id, {}).pop(uuid, None)
        if wrapper is None:
            return
        self._provider._pending_ranges.pop((self._room_id, uuid), None)
        for catalog in self._catalogs_holding(wrapper):
            self._provider._remove_event(catalog, wrapper)
        self._provider.mark_smart_dirty(self._room_id)

    # ---- connection ----

    def status(self, value):
        self._provider.room_status_changed(self._room_id, value)

    def role(self, value):
        self._provider.room_role_changed(self._room_id, value)

    def changes_done(self):
        self._provider.catalogues_may_have_changed(self._room_id)
