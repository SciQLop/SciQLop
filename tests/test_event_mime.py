import json
from datetime import datetime, timezone
from PySide6.QtCore import QMimeData

from SciQLop.components.catalogs.backend.provider import CatalogEvent
from SciQLop.core.mime.types import EVENT_LIST_MIME_TYPE


def _ev(uuid: str) -> CatalogEvent:
    return CatalogEvent(
        uuid=uuid,
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
        meta={"note": "x"},
    )


def test_encode_decode_roundtrip(qapp):
    from SciQLop.components.catalogs.backend.event_mime import (
        encode_event_list, decode_event_list,
    )

    events = [_ev("u1"), _ev("u2")]
    md = encode_event_list("My Catalogs", "cat-1", events)
    assert md.hasFormat(EVENT_LIST_MIME_TYPE)

    payload = json.loads(bytes(md.data(EVENT_LIST_MIME_TYPE)).decode())
    assert payload == {
        "provider": "My Catalogs",
        "catalog_uuid": "cat-1",
        "event_uuids": ["u1", "u2"],
    }

    decoded = decode_event_list(md)
    assert decoded.provider == "My Catalogs"
    assert decoded.catalog_uuid == "cat-1"
    assert decoded.event_uuids == ["u1", "u2"]


def test_decode_returns_none_for_unrelated_mime(qapp):
    from SciQLop.components.catalogs.backend.event_mime import decode_event_list
    md = QMimeData()
    md.setText("not an event payload")
    assert decode_event_list(md) is None


def test_decode_handles_missing_catalog_uuid(qapp):
    """Orphan-bucket drags carry catalog_uuid=None."""
    from SciQLop.components.catalogs.backend.event_mime import (
        encode_event_list, decode_event_list,
    )
    md = encode_event_list("My Catalogs", None, [_ev("u9")])
    decoded = decode_event_list(md)
    assert decoded.catalog_uuid is None
    assert decoded.event_uuids == ["u9"]
