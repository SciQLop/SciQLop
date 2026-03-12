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

    def list(self, prefix: str | None = None) -> list[str]:
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
        provider, catalog = self._resolve(path)
        events = provider.events(catalog)
        speasy_events = [_event_to_speasy(e) for e in events]
        return SpeasyCatalog(name=catalog.name, events=speasy_events)

    def save(self, path: str, data) -> None:
        speasy_cat = _normalize_input(data)
        new_events = [_event_to_internal(e) for e in speasy_cat]
        provider_name, segments, name = _parse_path(path)
        provider = self._find_provider(provider_name)

        existing = self._find_catalog(provider, segments, name)
        if existing is None:
            if Capability.CREATE_CATALOGS not in provider.capabilities():
                raise PermissionError(f"Provider {provider_name!r} cannot create catalogs")
            existing = provider.create_catalog(name, path=segments)

        provider._set_events(existing, new_events)
        provider.events_changed.emit(existing)
        provider.mark_dirty(existing)
        if Capability.SAVE_CATALOG in provider.capabilities():
            provider.save_catalog(existing)
        elif Capability.SAVE in provider.capabilities():
            provider.save()

    def create(self, path: str, data) -> None:
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
            provider._set_events(catalog, new_events)
            provider.events_changed.emit(catalog)
            provider.mark_dirty(catalog)
            if Capability.SAVE_CATALOG in provider.capabilities():
                provider.save_catalog(catalog)
            elif Capability.SAVE in provider.capabilities():
                provider.save()
