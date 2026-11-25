"""Pure conversions between cocat-rs room data and what SciQLop's catalog backend needs."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

SUBPATH_ATTR = "sciqlop_path"
TSCAT_PATH_ATTR = "path__"  # where tscat keeps a catalogue's folder; it survives cocat-rs's tscat import
SCHEMA_ATTR_PREFIX = "sciqlop_schema__"
TYPED_EVENT_FIELDS = ("tags", "products")
RATING_SCALE = 10  # SciQLop rates 1..10; cocat-rs stores a confidence in 0..1, as its tscat import does


def encode_subpath(segments: list[str]) -> str:
    return "/".join(segments)


def subpath_of(attributes: dict) -> list[str]:
    """The catalogue's folder: SciQLop's own attribute when present, even empty (moved to the
    root), else the folder a tscat import brought."""
    if SUBPATH_ATTR in attributes:
        return decode_subpath(attributes[SUBPATH_ATTR])
    return decode_subpath(attributes.get(TSCAT_PATH_ATTR))


def decode_subpath(value) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        return [s for s in value.split("/") if s]
    return [str(s) for s in value if s]


def parse_schema(value):
    """One `sciqlop_schema__*` attribute value -> KnobSpec, or None when unreadable."""
    from SciQLop.core.knobs import spec_from_dict
    try:
        return spec_from_dict(json.loads(value) if isinstance(value, str) else value)
    except (TypeError, ValueError, KeyError):
        return None


def schema_key(attribute: str) -> str | None:
    if attribute.startswith(SCHEMA_ATTR_PREFIX):
        return attribute[len(SCHEMA_ATTR_PREFIX):]
    return None


def schema_specs(attributes: dict) -> dict:
    specs = {}
    for attribute, value in attributes.items():
        key = schema_key(attribute)
        spec = parse_schema(value) if key is not None else None
        if spec is not None:
            specs[key] = spec
    return specs


@dataclass(frozen=True)
class EventRow:
    uuid: str
    start: datetime
    stop: datetime
    meta: dict
    derived: bool = False  # an interval a smart catalogue's rule computed: no room event behind it


def _utc(times) -> list[datetime]:
    return [t.replace(tzinfo=timezone.utc) for t in times.astype("datetime64[us]").tolist()]


DERIVED_PREFIX = "derived:"


def _derived_id(start: datetime, sources) -> str:
    """Stable across reads, so the same merged interval keeps one id while the rule holds."""
    return f"{DERIVED_PREFIX}{start.isoformat()}:{','.join(sources or [])}"


def typed_meta(tags, confidence) -> dict:
    """The bulk read's tags and confidence as SciQLop's meta: none when there are none."""
    meta = {}
    if tags:
        meta["tags"] = sorted(tags)  # one order, whether cocat-rs gives a list or a set
    if confidence is not None:
        meta["rating"] = round(confidence * RATING_SCALE)
    return meta


def _row(uuid, start, stop, meta, sources) -> EventRow:
    if uuid is None:
        return EventRow(_derived_id(start, sources), start, stop, dict(meta), derived=True)
    return EventRow(uuid, start, stop, dict(meta))


def event_rows(arrays: dict, attributes: list[dict]) -> list[EventRow]:
    uuids = list(arrays["uuid"])
    if len(attributes) != len(uuids):
        raise ValueError(f"{len(attributes)} attribute rows for {len(uuids)} events")
    sources = arrays.get("sources")
    sources = [None] * len(uuids) if sources is None else sources
    typed = [typed_meta(*fields) for fields in zip(arrays.get("tags") or [None] * len(uuids),
                                                   arrays.get("confidence") or [None] * len(uuids))]
    metas = [{**extra, **fields} for extra, fields in zip(attributes, typed)]
    return [_row(*fields) for fields in zip(uuids, _utc(arrays["start"]), _utc(arrays["stop"]),
                                            metas, sources)]


def confidence_of(rating) -> float | None:
    return None if rating is None else min(max(float(rating) / RATING_SCALE, 0.0), 1.0)


def typed_fields(key: str, value: Any) -> dict:
    """The cocat-rs fields one edited tag list or rating goes to (``value`` None clears them);
    {} for any other key, which is a plain attribute."""
    if key == "tags":
        return {"tags": set(value or ())}
    if key == "rating":
        return {"confidence": confidence_of(value)}
    return {}


def split_typed_meta(meta: dict[str, Any]) -> tuple[dict, dict]:
    typed = {k: v for k, v in meta.items() if k in TYPED_EVENT_FIELDS}
    if meta.get("rating") is not None:
        typed["confidence"] = confidence_of(meta["rating"])
    rest = {k: v for k, v in meta.items() if k not in TYPED_EVENT_FIELDS and k != "rating"}
    return typed, rest


def rows_of(arrays: dict) -> list[EventRow]:
    """Rows from cocat-rs ``event_arrays(..., attributes=True)``: one read, already aligned."""
    return event_rows(arrays, arrays["attributes"])
