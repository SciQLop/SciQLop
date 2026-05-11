from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import QMimeData

from SciQLop.core.mime.types import EVENT_LIST_MIME_TYPE
from .provider import CatalogEvent


@dataclass(frozen=True)
class EventDropPayload:
    provider: str
    catalog_uuid: str | None
    event_uuids: list[str]


def encode_event_list(
    provider_name: str,
    catalog_uuid: str | None,
    events: Iterable[CatalogEvent],
) -> QMimeData:
    payload = {
        "provider": provider_name,
        "catalog_uuid": catalog_uuid,
        "event_uuids": [e.uuid for e in events],
    }
    md = QMimeData()
    md.setData(EVENT_LIST_MIME_TYPE, json.dumps(payload).encode("utf-8"))
    return md


def decode_event_list(mime: QMimeData) -> EventDropPayload | None:
    if not mime.hasFormat(EVENT_LIST_MIME_TYPE):
        return None
    raw = bytes(mime.data(EVENT_LIST_MIME_TYPE))
    if not raw:
        return None
    data = json.loads(raw.decode("utf-8"))
    return EventDropPayload(
        provider=data["provider"],
        catalog_uuid=data.get("catalog_uuid"),
        event_uuids=list(data.get("event_uuids", [])),
    )
