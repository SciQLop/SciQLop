from __future__ import annotations

import time
import uuid as _uuid
from functools import wraps
from typing import Any

from speasy.products.catalog import Catalog as SpeasyCatalog, Event as SpeasyEvent

from SciQLop.components.catalogs.backend.provider import (
    Catalog,
    CatalogEvent,
    CatalogProvider,
    Capability,
)
from SciQLop.components.catalogs.backend.registry import CatalogRegistry
from SciQLop.user_api.threading import _on_main_thread, on_main_thread

_UUID_KEY = "__sciqlop_uuid__"

_WRITE_CAPABILITIES = {Capability.EDIT_EVENTS, Capability.CREATE_EVENTS,
                       Capability.DELETE_EVENTS, Capability.CREATE_CATALOGS,
                       Capability.DELETE_CATALOGS}

_LOAD_TIMEOUT_S = 30.0


def _on_main_thread_once_loaded(method):
    """`on_main_thread`, after waiting for the catalog's events to finish
    loading in the background. Reading or appending to a half-loaded catalog
    silently works on the events that have arrived so far.

    Only a caller off the GUI thread (a cell, an agent) can wait: on the GUI
    thread the wait would block the load itself.
    """
    marshalled = on_main_thread(method)

    @wraps(method)
    def wrapper(self, path, *args, **kwargs):
        if not _on_main_thread():
            deadline = time.monotonic() + _LOAD_TIMEOUT_S
            while self._still_loading(path) and time.monotonic() < deadline:
                time.sleep(0.05)
        return marshalled(self, path, *args, **kwargs)
    return wrapper


def _split_segments(path: str) -> list[str]:
    if not isinstance(path, str):
        raise TypeError(f"catalog path must be a str, got {type(path).__name__}")
    segments = path.split("//")
    for seg in segments:
        if "/" in seg:
            raise ValueError(
                f"Invalid path {path!r}: segments must be separated by '//', "
                f"and segments cannot contain '/' (got {seg!r})"
            )
        if not seg:
            raise ValueError(f"Invalid path {path!r}: empty segment")
    return segments


def _parse_path(path: str) -> tuple[str, list[str], str]:
    segments = _split_segments(path)
    if len(segments) < 2:
        raise ValueError(f"Path must have at least provider and catalog name: {path!r}")
    return segments[0], segments[1:-1], segments[-1]


def _parse_prefix(prefix: str) -> tuple[str, list[str]]:
    segments = _split_segments(prefix)
    return segments[0], segments[1:]


def _build_path_string(provider_name: str, path: list[str], catalog_name: str) -> str:
    parts = [provider_name] + path + [catalog_name]
    return "//".join(parts)


def _event_to_speasy(event: CatalogEvent) -> SpeasyEvent:
    meta = {**event.meta, _UUID_KEY: event.uuid}
    return SpeasyEvent(event.start, event.stop, meta=meta)


def _event_to_internal(event: SpeasyEvent) -> CatalogEvent:
    meta = dict(event.meta) if event.meta else {}
    uuid = meta.pop(_UUID_KEY, str(_uuid.uuid4()))
    return CatalogEvent(uuid=uuid, start=event.start_time, stop=event.stop_time, meta=meta)


def _reject_inverted_events(catalog: SpeasyCatalog) -> SpeasyCatalog:
    """Start > stop raises, start == stop is fine, whatever the provider: a store
    that rejects such an event later, or on another thread, would leave the
    user-api cache holding events the store does not have."""
    for event in catalog:
        if event.start_time > event.stop_time:
            raise ValueError(
                f"event start must be before stop, got "
                f"{event.start_time} > {event.stop_time}")
    return catalog


def _normalize_input(data) -> SpeasyCatalog:
    if isinstance(data, SpeasyCatalog):
        return _reject_inverted_events(data)
    events = []
    for item in data:
        if isinstance(item, SpeasyEvent):  # before the tuples: an Event also has a length of 2
            events.append(item)
        elif len(item) == 2:
            events.append(SpeasyEvent(item[0], item[1]))
        elif len(item) == 3:
            if not isinstance(item[2], dict):
                raise TypeError(
                    f"event meta must be a dict, got {type(item[2]).__name__}")
            events.append(SpeasyEvent(item[0], item[1], meta=item[2]))
        else:
            raise ValueError(f"Expected (start, stop) or (start, stop, meta), got {len(item)} elements")
    return _reject_inverted_events(SpeasyCatalog(name="", events=events))


class CatalogService:
    """Notebook-facing facade for catalog CRUD operations.

    Singleton instance available as ``catalogs`` from
    ``SciQLop.user_api.catalogs``.  All paths follow the convention
    ``"provider//sub//path//catalog_name"`` (``//``-separated segments).
    """

    def _registry(self) -> CatalogRegistry:
        return CatalogRegistry.instance()

    def _find_provider(self, provider_name: str) -> CatalogProvider:
        for p in self._registry().providers():
            if p.name == provider_name:
                return p
        raise KeyError(f"Provider not found: {provider_name!r}")

    def _find_catalog(self, provider: CatalogProvider, path: list[str], name: str) -> Catalog | None:
        for cat in provider.catalogs():
            if cat.name == name and cat.path == path:
                return cat
        return None

    @on_main_thread
    def _still_loading(self, path: str) -> bool:
        try:
            provider, catalog = self._resolve(path)
        except (KeyError, ValueError, TypeError):
            return False  # nothing to wait for; the real call reports it
        provider.events(catalog)  # starts the background load if needed
        return provider.is_loading(catalog)

    def _target(self, path: str) -> tuple[CatalogProvider, list[str], str]:
        """The provider, folder and name a path means; no folder means the provider's default one."""
        provider_name, segments, name = _parse_path(path)
        provider = self._find_provider(provider_name)
        return provider, segments or provider.default_folder(), name

    def _resolve(self, path: str) -> tuple[CatalogProvider, Catalog]:
        provider, segments, name = self._target(path)
        catalog = self._find_catalog(provider, segments, name)
        if catalog is None:
            raise KeyError(f"Catalog not found: {path!r}")
        return provider, catalog

    @staticmethod
    def _update_event(provider: CatalogProvider, catalog: Catalog,
                      old: CatalogEvent, new: CatalogEvent) -> None:
        """Apply *new*'s times and meta onto the cached *old* event.

        Range changes go through the cached object's setters (providers like
        tscat persist ranges only there); meta changes go through the
        provider's set/remove_event_meta hooks (uuid-keyed persistence)."""
        if new.start != old.start:
            old.start = new.start
        if new.stop != old.stop:
            old.stop = new.stop
        for key, value in new.meta.items():
            provider.set_event_meta(catalog, old, key, value)
        for key in set(old.meta) - set(new.meta):
            provider.remove_event_meta(catalog, old, key)

    def _persist(self, provider: CatalogProvider, catalog: Catalog, events: list[CatalogEvent]) -> None:
        with provider.batch_events_update(catalog):
            old_by_uuid = {e.uuid: e for e in provider.events(catalog)}
            new_uuids = {e.uuid for e in events}

            for uuid, old in old_by_uuid.items():
                if uuid not in new_uuids:
                    provider.remove_event(catalog, old)
            for event in events:
                old = old_by_uuid.get(event.uuid)
                if old is None:
                    provider.add_event(catalog, event)
                else:
                    self._update_event(provider, catalog, old, event)

            # Don't call save() here — providers like tscat queue mutations
            # asynchronously (QThread worker), so saving immediately would
            # race with pending ORM actions. The cache below is authoritative;
            # disk persistence happens only through provider.save(), from the
            # browser's Save or CatalogService.persist(). Prefer the provider's own cached objects (then
            # the pre-save ones) over our plain copies, so persistence-wired
            # wrappers (e.g. TscatEvent) stay in the cache.
            current_by_uuid = {e.uuid: e for e in provider.events(catalog)}
            final = [current_by_uuid.get(e.uuid) or old_by_uuid.get(e.uuid, e)
                     for e in events]
            provider._set_events(catalog, final)

    @on_main_thread
    def list(self, prefix: str | None = None) -> list[str]:
        """Return full paths of all catalogs, optionally filtered by *prefix*.

        Parameters
        ----------
        prefix : str, optional
            If given, only catalogs whose path starts with this prefix are
            returned.  E.g. ``"Catalogs (cocat-rs)"`` lists your own catalogs,
            ``"cocat//room_id"`` lists catalogs in a specific cocat room.

        Returns
        -------
        list[str]
            Fully-qualified ``//``-separated catalog paths.
        """
        if prefix is None:
            return [
                _build_path_string(p.name, cat.path, cat.name)
                for p in self._registry().providers()
                for cat in p.catalogs()
            ]
        provider_name, path_prefix = _parse_prefix(prefix)
        provider = self._find_provider(provider_name)
        return [
            _build_path_string(provider.name, cat.path, cat.name)
            for cat in provider.catalogs()
            if cat.path[:len(path_prefix)] == path_prefix
        ]

    @_on_main_thread_once_loaded
    def get(self, path: str) -> SpeasyCatalog:
        """Retrieve a catalog as a ``speasy.Catalog``.

        Parameters
        ----------
        path : str
            Fully-qualified catalog path (e.g. ``"Catalogs (cocat-rs)//my_catalog"``).

        Returns
        -------
        speasy.products.catalog.Catalog
            Catalog with events. Each event's ``meta["__sciqlop_uuid__"]``
            preserves the internal UUID for round-trip editing.

        Raises
        ------
        KeyError
            If the provider or catalog is not found.
        """
        provider, catalog = self._resolve(path)
        events = provider.events(catalog)
        speasy_events = [_event_to_speasy(e) for e in events]
        return SpeasyCatalog(name=catalog.name, events=speasy_events)

    @_on_main_thread_once_loaded
    def filter(self, path: str, text: str) -> SpeasyCatalog:
        """The catalog's events a filter text keeps, as the catalog browser's filter box would.

        Each provider filters in its own way: by default the text is looked for in any column, as
        the event table shows it (``"2020-01-01"``, ``"solar_wind"``). An empty text keeps all.

        Parameters
        ----------
        path : str
            Fully-qualified catalog path.
        text : str
            The filter.

        Returns
        -------
        speasy.products.catalog.Catalog
            The kept events, with ``meta["__sciqlop_uuid__"]`` like :meth:`get`.
        """
        provider, catalog = self._resolve(path)
        kept = provider.filter_events(catalog, text)
        return SpeasyCatalog(name=catalog.name, events=[_event_to_speasy(e) for e in kept])

    @_on_main_thread_once_loaded
    def save(self, path: str, data) -> None:
        """Replace the events of a catalog, creating it if it doesn't exist (upsert).

        Existing events are replaced in bulk. UUIDs embedded in
        ``event.meta["__sciqlop_uuid__"]`` are preserved on round-trip.

        "Catalogs (cocat-rs)" stores the change at once. Other providers may
        keep it in memory until :meth:`persist`, like the catalog browser's
        Save.

        Parameters
        ----------
        path : str
            Fully-qualified catalog path.
        data : CatalogInput
            A ``speasy.Catalog``, an iterable of ``speasy`` events (their meta
            and ``__sciqlop_uuid__`` are kept), of ``(start, stop)`` tuples,
            or of ``(start, stop, meta_dict)`` tuples.

        Raises
        ------
        PermissionError
            If the provider doesn't support catalog creation and the catalog
            doesn't already exist.
        """
        speasy_cat = _normalize_input(data)
        new_events = [_event_to_internal(e) for e in speasy_cat]
        provider, segments, name = self._target(path)

        existing = self._find_catalog(provider, segments, name)
        if existing is None:
            if Capability.CREATE_CATALOGS not in provider.capabilities():
                raise PermissionError(f"Provider {provider.name!r} cannot create catalogs")
            existing = provider.create_catalog(name, path=segments)

        self._persist(provider, existing, new_events)

    @on_main_thread
    def remove(self, path: str) -> None:
        """Delete a catalog.

        Parameters
        ----------
        path : str
            Fully-qualified catalog path.

        Raises
        ------
        KeyError
            If the provider or catalog is not found.
        PermissionError
            If the provider doesn't support catalog deletion.
        """
        provider, catalog = self._resolve(path)
        if Capability.DELETE_CATALOGS not in provider.capabilities():
            raise PermissionError(f"Provider {provider.name!r} cannot delete catalogs")
        provider.remove_catalog(catalog)

    @on_main_thread
    def persist(self, path: str) -> None:
        """Write a catalog's pending changes to storage, like the catalog
        browser's Save.

        Providers that store each change as it happens ("Catalogs (cocat-rs)")
        need no save, and this does nothing for them. Others keep written
        events (``create``, ``add_events``, ``save``, ...) in memory until
        saved; where such a provider can only save as a whole, this saves
        every pending change of that provider, as the browser does.

        Parameters
        ----------
        path : str
            Fully-qualified catalog path.

        Raises
        ------
        KeyError
            If the provider or catalog is not found.
        PermissionError
            If the catalog is read-only.
        """
        provider, catalog = self._resolve(path)
        caps = provider.capabilities(catalog)
        if Capability.SAVE_CATALOG in caps:
            provider.save_catalog(catalog)
        elif Capability.SAVE in caps:
            provider.save()
        elif not caps & _WRITE_CAPABILITIES:
            raise PermissionError(f"Catalog {path!r} is read-only")

    @on_main_thread
    def create(self, path: str, data) -> None:
        """Create a new catalog with the given events (strict — fails if exists).

        "Catalogs (cocat-rs)" stores the change at once. Other providers may
        keep it in memory until :meth:`persist`, like the catalog browser's
        Save.

        Parameters
        ----------
        path : str
            Fully-qualified catalog path.
        data : CatalogInput
            A ``speasy.Catalog``, an iterable of ``speasy`` events (their meta
            and ``__sciqlop_uuid__`` are kept), of ``(start, stop)`` tuples,
            or of ``(start, stop, meta_dict)`` tuples.

        Raises
        ------
        ValueError
            If a catalog at *path* already exists.
        PermissionError
            If the provider doesn't support catalog creation.
        """
        provider, segments, name = self._target(path)

        if self._find_catalog(provider, segments, name) is not None:
            raise ValueError(f"Catalog already exists: {path!r}")
        if Capability.CREATE_CATALOGS not in provider.capabilities():
            raise PermissionError(f"Provider {provider.name!r} cannot create catalogs")

        catalog = provider.create_catalog(name, path=segments)
        speasy_cat = _normalize_input(data)
        new_events = [_event_to_internal(e) for e in speasy_cat]
        if new_events:
            self._persist(provider, catalog, new_events)

    # ---- smart catalogues ----

    @on_main_thread
    def create_smart(self, path: str, query: str, source: str | None = None) -> None:
        """Create a smart catalogue: its events are those its search finds, as the project changes.

        The search is one line, as in the catalog tree's editor and the CoCat web app:
        ``"tag:shock confidence:>=0.7"``, ``"(tag:shock) OR (#density:>10)"``,
        ``"created:now-7d"``, ``"NOT _exists_:catalogue"``.

        Parameters
        ----------
        path : str
            Fully-qualified path of the new catalogue.
        query : str
            The search.
        source : str, optional
            Path of a catalogue of the same project to search in; all events when omitted.

        Raises
        ------
        ValueError
            If a catalog at *path* already exists, or the search is wrong (a
            ``cocat_rs.QueryError`` for "Catalogs (cocat-rs)", with ``position``,
            ``length`` and ``suggestion``).
        PermissionError
            If the provider has no smart catalogues.
        """
        provider, segments, name = self._target(path)
        if self._find_catalog(provider, segments, name) is not None:
            raise ValueError(f"Catalog already exists: {path!r}")
        provider.create_smart_catalog(name, segments, query, source=self._source(provider, source))

    @on_main_thread
    def search_of(self, path: str) -> str | None:
        """The catalogue's search as one line; None for a plain catalogue, or a rule the line cannot say
        (see :meth:`rule_of`)."""
        provider, catalog = self._resolve(path)
        search = provider.catalog_search(catalog)
        return search.query if search is not None else None

    @on_main_thread
    def rule_of(self, path: str) -> dict | None:
        """The rule the catalogue's search is stored as (JSON); None for a plain catalogue."""
        provider, catalog = self._resolve(path)
        search = provider.catalog_search(catalog)
        return search.rule if search is not None else None

    @on_main_thread
    def set_search(self, path: str, query: str, source: str | None = None) -> None:
        """Give the catalogue this search; a plain catalogue becomes smart. See :meth:`create_smart`."""
        provider, catalog = self._resolve(path)
        provider.set_catalog_search(catalog, query, source=self._source(provider, source))

    @on_main_thread
    def set_rule(self, path: str, rule: dict) -> None:
        """Give the catalogue a rule as JSON: for what one search line cannot say (``merge``,
        ``shift``, ``window``...). ``ValueError`` if the rule does not read."""
        provider, catalog = self._resolve(path)
        provider.set_catalog_search(catalog, rule=rule)

    @on_main_thread
    def remove_search(self, path: str) -> None:
        """The catalogue keeps the events it lists and stops adding events."""
        provider, catalog = self._resolve(path)
        provider.remove_catalog_search(catalog)

    @on_main_thread
    def freeze(self, path: str, name: str) -> str:
        """A normal catalogue named *name*, beside this one, holding the events it holds now.
        Returns its path."""
        provider, catalog = self._resolve(path)
        frozen = provider.freeze_catalog(catalog, name)
        return _build_path_string(provider.name, frozen.path, frozen.name)

    def _source(self, provider, source: str | None):
        if source is None:
            return None
        source_provider, catalog = self._resolve(source)
        if source_provider is not provider:
            raise ValueError(f"A search looks in a catalogue of the same provider: {source!r}")
        return catalog

    @_on_main_thread_once_loaded
    def add_events(self, path: str, data) -> None:
        """Append events to an existing catalog.

        "Catalogs (cocat-rs)" stores the change at once. Other providers may
        keep it in memory until :meth:`persist`, like the catalog browser's
        Save.

        Parameters
        ----------
        path : str
            Fully-qualified catalog path.
        data : CatalogInput
            A ``speasy.Catalog``, an iterable of ``speasy`` events (their meta
            and ``__sciqlop_uuid__`` are kept), of ``(start, stop)`` tuples,
            or of ``(start, stop, meta_dict)`` tuples.

        Raises
        ------
        KeyError
            If the provider or catalog is not found.
        """
        provider, catalog = self._resolve(path)
        existing = provider.events(catalog)
        speasy_cat = _normalize_input(data)
        new_events = [_event_to_internal(e) for e in speasy_cat]
        self._persist(provider, catalog, existing + new_events)

    @_on_main_thread_once_loaded
    def remove_events(self, path: str, events) -> None:
        """Remove specific events from a catalog.

        Events are identified by their ``__sciqlop_uuid__`` metadata key
        (present on events returned by :meth:`get`). Raw UUID strings are
        also accepted.

        "Catalogs (cocat-rs)" stores the change at once. Other providers may
        keep it in memory until :meth:`persist`, like the catalog browser's
        Save.

        Parameters
        ----------
        path : str
            Fully-qualified catalog path.
        events : iterable of speasy.Event or str
            Events to remove. Speasy ``Event`` objects must carry a
            ``meta["__sciqlop_uuid__"]`` key. Plain UUID strings are also
            accepted.

        Raises
        ------
        KeyError
            If the provider or catalog is not found.
        ValueError
            If an event has no UUID and is not a string.
        """
        uuids_to_remove = set()
        for e in events:
            if isinstance(e, str):
                uuids_to_remove.add(e)
            elif isinstance(e, SpeasyEvent) and e.meta and _UUID_KEY in e.meta:
                uuids_to_remove.add(e.meta[_UUID_KEY])
            else:
                raise ValueError(f"Cannot identify event to remove (no UUID): {e!r}")

        provider, catalog = self._resolve(path)
        existing = provider.events(catalog)
        remaining = [e for e in existing if e.uuid not in uuids_to_remove]
        self._persist(provider, catalog, remaining)
