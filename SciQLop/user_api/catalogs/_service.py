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
