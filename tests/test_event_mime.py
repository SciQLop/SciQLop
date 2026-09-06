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


def test_decode_returns_none_for_malformed_payload(qapp):
    """decode_event_list is reached from CatalogTreeModel._drop_events, a
    public Qt drop-target entry point, before the later try/except that
    wraps the actual provider operation -- a foreign or malformed drag
    merely advertising EVENT_LIST_MIME_TYPE must not raise out of it, same
    contract as the sibling TimeRange mime decoder added in this same
    review (2026-09-06 final review)."""
    from SciQLop.components.catalogs.backend.event_mime import decode_event_list
    from SciQLop.core.mime.types import EVENT_LIST_MIME_TYPE

    def _mime_with(raw: bytes) -> QMimeData:
        md = QMimeData()
        md.setData(EVENT_LIST_MIME_TYPE, raw)
        return md

    assert decode_event_list(_mime_with(b"not json")) is None
    assert decode_event_list(_mime_with(b'{"catalog_uuid": "c1"}')) is None  # missing "provider"
    assert decode_event_list(_mime_with(b"\xff\xfe\x00")) is None  # invalid utf-8


def test_decode_handles_missing_catalog_uuid(qapp):
    """Orphan-bucket drags carry catalog_uuid=None."""
    from SciQLop.components.catalogs.backend.event_mime import (
        encode_event_list, decode_event_list,
    )
    md = encode_event_list("My Catalogs", None, [_ev("u9")])
    decoded = decode_event_list(md)
    assert decoded.catalog_uuid is None
    assert decoded.event_uuids == ["u9"]


def test_event_table_drag_also_carries_a_time_range(qtbot, qapp):
    """Dragging event(s) out of the table must also tag the drag with
    TIME_RANGE_MIME_TYPE, spanning the selection, so dropping on a plot
    panel (which already accepts that MIME type) jumps there for free --
    previously the table only ever produced EVENT_LIST_MIME_TYPE, so a
    plot drop was a silent no-op (2026-09-06 review)."""
    from datetime import datetime, timezone
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.event_table import EventTableModel
    from SciQLop.core.mime import decode_mime
    from SciQLop.core.mime.types import TIME_RANGE_MIME_TYPE

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, name="DragProv")
    cat = provider.catalogs()[0]
    e1 = _ev_at("e1", datetime(2020, 1, 1, tzinfo=timezone.utc), datetime(2020, 1, 1, 1, tzinfo=timezone.utc))
    e2 = _ev_at("e2", datetime(2020, 1, 2, tzinfo=timezone.utc), datetime(2020, 1, 2, 2, tzinfo=timezone.utc))
    provider.add_event(cat, e1)
    provider.add_event(cat, e2)

    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    md = model.mimeData([model.index(0, 0), model.index(1, 0)])
    assert md.hasFormat(TIME_RANGE_MIME_TYPE)
    assert md.hasFormat(EVENT_LIST_MIME_TYPE)
    decoded = decode_mime(md)
    assert decoded.start() == e1.start.timestamp()
    assert decoded.stop() == e2.stop.timestamp()

    from SciQLop.components.catalogs.backend.event_mime import decode_event_list
    event_payload = decode_event_list(md)
    assert set(event_payload.event_uuids) == {"e1", "e2"}
    assert TIME_RANGE_MIME_TYPE in model.mimeTypes()


def _ev_at(uuid, start, stop) -> CatalogEvent:
    return CatalogEvent(uuid=uuid, start=start, stop=stop, meta={})
