from .fixtures import *
from datetime import datetime, timezone
from SciQLop.components.catalogs.backend.provider import CatalogEvent


def test_event_meta_changed_signal_emits_on_set_meta(qtbot, qapp):
    event = CatalogEvent(
        uuid="e1",
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
        meta={"score": 0.5},
    )
    with qtbot.waitSignal(event.meta_changed, timeout=1000) as blocker:
        event.set_meta("score", 0.9)
    assert blocker.args == ["score"]
    assert event.meta["score"] == 0.9


def test_event_meta_changed_not_emitted_when_value_unchanged(qtbot, qapp):
    event = CatalogEvent(
        uuid="e1",
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
        meta={"score": 0.5},
    )
    received = []
    event.meta_changed.connect(received.append)
    event.set_meta("score", 0.5)
    assert received == []


def test_set_meta_with_none_on_missing_key_emits(qtbot, qapp):
    """Sentinel guard: 'key absent' must not equal value=None — emit on first set."""
    event = CatalogEvent(
        uuid="e1",
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
        meta={},
    )
    with qtbot.waitSignal(event.meta_changed, timeout=1000) as blocker:
        event.set_meta("note", None)
    assert blocker.args == ["note"]
    assert "note" in event.meta
    assert event.meta["note"] is None


def test_remove_meta_present_emits(qtbot, qapp):
    event = CatalogEvent(
        uuid="e1",
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
        meta={"author": "alice"},
    )
    with qtbot.waitSignal(event.meta_changed, timeout=1000) as blocker:
        event.remove_meta("author")
    assert blocker.args == ["author"]
    assert "author" not in event.meta


def test_remove_meta_absent_silent(qtbot, qapp):
    event = CatalogEvent(
        uuid="e1",
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
        meta={},
    )
    received = []
    event.meta_changed.connect(received.append)
    event.remove_meta("missing")
    assert received == []
