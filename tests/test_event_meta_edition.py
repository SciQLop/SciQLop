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


def test_provider_set_event_meta_marks_dirty_and_emits(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    event = provider.events(cat)[0]

    received = []
    provider.event_meta_changed.connect(lambda c, e, k: received.append((c.uuid, e.uuid, k)))

    with qtbot.waitSignal(provider.dirty_changed, timeout=1000):
        provider.set_event_meta(cat, event, "score", 0.42)

    assert event.meta["score"] == 0.42
    assert received == [(cat.uuid, event.uuid, "score")]
    assert provider.is_dirty(cat)


def test_provider_set_events_meta_bulk(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=5)
    cat = provider.catalogs()[0]
    events = provider.events(cat)[:3]

    provider.set_events_meta(cat, events, "class", "boundary")

    for e in events:
        assert e.meta["class"] == "boundary"
    assert provider.is_dirty(cat)


def test_provider_remove_event_meta_emits_and_marks_dirty(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    event = provider.events(cat)[0]
    # DummyProvider seeds events with a "score" key, drop it
    received = []
    provider.event_meta_changed.connect(lambda c, e, k: received.append(k))

    with qtbot.waitSignal(provider.dirty_changed, timeout=1000):
        provider.remove_event_meta(cat, event, "score")

    assert "score" not in event.meta
    assert received == ["score"]


def test_provider_set_event_meta_noop_when_value_unchanged(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    event = provider.events(cat)[0]
    current_score = event.meta["score"]

    received = []
    provider.event_meta_changed.connect(lambda c, e, k: received.append(k))
    provider.set_event_meta(cat, event, "score", current_score)

    assert received == []
    assert not provider.is_dirty(cat)


def test_set_events_meta_default_delegates_to_set_event_meta(qtbot, qapp):
    """Subclasses overriding only set_event_meta must still see bulk writes."""
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    calls = []

    class TrackingProvider(DummyProvider):
        def set_event_meta(self, catalog, event, key, value):
            calls.append((event.uuid, key, value))
            super().set_event_meta(catalog, event, key, value)

    provider = TrackingProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    events = provider.events(cat)

    provider.set_events_meta(cat, events, "tag", "x")

    assert len(calls) == 3
    for ev in events:
        assert ev.meta["tag"] == "x"
