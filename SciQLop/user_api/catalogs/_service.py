from __future__ import annotations

import uuid as _uuid
from typing import Any

from speasy.products.catalog import Catalog as SpeasyCatalog, Event as SpeasyEvent

from SciQLop.components.catalogs.backend.provider import (
    Catalog,
    CatalogEvent,
    CatalogProvider,
    Capability,
)
from SciQLop.components.catalogs.backend.registry import CatalogRegistry

_UUID_KEY = "__sciqlop_uuid__"


def _split_segments(path: str) -> list[str]:
    if "//" in path:
        return path.split("//")
    return path.split("/")


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


def _normalize_input(data) -> SpeasyCatalog:
    if isinstance(data, SpeasyCatalog):
        return data
    events = []
    for item in data:
        if len(item) == 2:
            events.append(SpeasyEvent(item[0], item[1]))
        elif len(item) == 3:
            events.append(SpeasyEvent(item[0], item[1], meta=item[2]))
        else:
            raise ValueError(f"Expected (start, stop) or (start, stop, meta), got {len(item)} elements")
    return SpeasyCatalog(name="", events=events)


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

    def _resolve(self, path: str) -> tuple[CatalogProvider, Catalog]:
        provider_name, segments, name = _parse_path(path)
        provider = self._find_provider(provider_name)
        catalog = self._find_catalog(provider, segments, name)
        if catalog is None:
            raise KeyError(f"Catalog not found: {path!r}")
        return provider, catalog

    def _persist(self, provider: CatalogProvider, catalog: Catalog, events: list[CatalogEvent]) -> None:
        # Route through add_event/remove_event so backends (e.g. tscat) can
        # persist to their ORM/DB.  Each call may invalidate the in-memory
        # cache, so we do a final _set_events to guarantee consistency.
        for old in list(provider.events(catalog)):
            provider.remove_event(catalog, old)

        for event in events:
            provider.add_event(catalog, event)

        # Authoritative cache update — backends may have wiped self._events
        # during the individual add/remove calls above.
        provider._set_events(catalog, events)
        provider.events_changed.emit(catalog)

        if Capability.SAVE_CATALOG in provider.capabilities():
            provider.save_catalog(catalog)
        elif Capability.SAVE in provider.capabilities():
            provider.save()

    def list(self, prefix: str | None = None) -> list[str]:
        """Return full paths of all catalogs, optionally filtered by *prefix*.

        Parameters
        ----------
        prefix : str, optional
            If given, only catalogs whose path starts with this prefix are
            returned.  E.g. ``"tscat"`` lists all tscat catalogs,
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

    def get(self, path: str) -> SpeasyCatalog:
        """Retrieve a catalog as a ``speasy.Catalog``.

        Parameters
        ----------
        path : str
            Fully-qualified catalog path (e.g. ``"tscat//my_catalog"``).

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

    def save(self, path: str, data) -> None:
        """Save events to a catalog, creating it if it doesn't exist (upsert).

        Existing events are replaced in bulk. UUIDs embedded in
        ``event.meta["__sciqlop_uuid__"]`` are preserved on round-trip.

        Parameters
        ----------
        path : str
            Fully-qualified catalog path.
        data : CatalogInput
            A ``speasy.Catalog``, an iterable of ``(start, stop)`` tuples,
            or an iterable of ``(start, stop, meta_dict)`` tuples.

        Raises
        ------
        PermissionError
            If the provider doesn't support catalog creation and the catalog
            doesn't already exist.
        """
        speasy_cat = _normalize_input(data)
        new_events = [_event_to_internal(e) for e in speasy_cat]
        provider_name, segments, name = _parse_path(path)
        provider = self._find_provider(provider_name)

        existing = self._find_catalog(provider, segments, name)
        if existing is None:
            if Capability.CREATE_CATALOGS not in provider.capabilities():
                raise PermissionError(f"Provider {provider_name!r} cannot create catalogs")
            existing = provider.create_catalog(name, path=segments)

        self._persist(provider, existing, new_events)

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

    def create(self, path: str, data) -> None:
        """Create a new catalog with the given events (strict — fails if exists).

        Parameters
        ----------
        path : str
            Fully-qualified catalog path.
        data : CatalogInput
            A ``speasy.Catalog``, an iterable of ``(start, stop)`` tuples,
            or an iterable of ``(start, stop, meta_dict)`` tuples.

        Raises
        ------
        ValueError
            If a catalog at *path* already exists.
        PermissionError
            If the provider doesn't support catalog creation.
        """
        provider_name, segments, name = _parse_path(path)
        provider = self._find_provider(provider_name)

        if self._find_catalog(provider, segments, name) is not None:
            raise ValueError(f"Catalog already exists: {path!r}")
        if Capability.CREATE_CATALOGS not in provider.capabilities():
            raise PermissionError(f"Provider {provider_name!r} cannot create catalogs")

        catalog = provider.create_catalog(name, path=segments)
        speasy_cat = _normalize_input(data)
        new_events = [_event_to_internal(e) for e in speasy_cat]
        if new_events:
            self._persist(provider, catalog, new_events)

    def add_events(self, path: str, data) -> None:
        """Append events to an existing catalog.

        Parameters
        ----------
        path : str
            Fully-qualified catalog path.
        data : CatalogInput
            A ``speasy.Catalog``, an iterable of ``(start, stop)`` tuples,
            or an iterable of ``(start, stop, meta_dict)`` tuples.

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

    def remove_events(self, path: str, events) -> None:
        """Remove specific events from a catalog.

        Events are identified by their ``__sciqlop_uuid__`` metadata key
        (present on events returned by :meth:`get`). Raw UUID strings are
        also accepted.

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
