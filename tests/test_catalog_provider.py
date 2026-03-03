from .fixtures import *
import pytest
from datetime import datetime, timezone, timedelta


def test_catalog_event_creation(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    stop = datetime(2020, 1, 2, tzinfo=timezone.utc)
    event = CatalogEvent(uuid="evt-1", start=start, stop=stop)
    assert event.uuid == "evt-1"
    assert event.start == start
    assert event.stop == stop
    assert event.meta == {}


def test_catalog_event_meta(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    stop = datetime(2020, 1, 2, tzinfo=timezone.utc)
    event = CatalogEvent(uuid="evt-1", start=start, stop=stop,
                         meta={"author": "Alice", "rating": 5})
    assert event.meta["author"] == "Alice"
    assert event.meta["rating"] == 5


def test_catalog_event_range_changed_signal(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    stop = datetime(2020, 1, 2, tzinfo=timezone.utc)
    event = CatalogEvent(uuid="evt-1", start=start, stop=stop)

    new_start = datetime(2020, 6, 1, tzinfo=timezone.utc)
    new_stop = datetime(2020, 6, 2, tzinfo=timezone.utc)

    with qtbot.waitSignal(event.range_changed, timeout=1000):
        event.start = new_start
        event.stop = new_stop

    assert event.start == new_start
    assert event.stop == new_stop


def test_catalog_descriptor(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import Catalog
    cat = Catalog(uuid="cat-1", name="My Catalog")
    assert cat.uuid == "cat-1"
    assert cat.name == "My Catalog"
    assert cat.provider is None


def test_capability_enum(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import Capability
    assert Capability.EDIT_EVENTS == "edit_events"
    assert isinstance(Capability.EDIT_EVENTS, str)
    caps = {Capability.EDIT_EVENTS, "custom_capability"}
    assert "edit_events" in caps
    assert "custom_capability" in caps


def _make_dummy_provider(qapp):
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, CatalogEvent, Capability

    class InMemoryProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="test-provider")
            self._cat = Catalog(uuid="cat-1", name="Test Catalog", provider=self)
            self._catalogs = [self._cat]
            events = []
            base = datetime(2020, 1, 1, tzinfo=timezone.utc)
            for i in range(100):
                events.append(CatalogEvent(
                    uuid=f"evt-{i}",
                    start=base + timedelta(days=i),
                    stop=base + timedelta(days=i, hours=1),
                ))
            self._set_events(self._cat, events)

        def catalogs(self):
            return self._catalogs

        def capabilities(self, catalog=None):
            return {Capability.EDIT_EVENTS, Capability.CREATE_EVENTS}

    return InMemoryProvider()


def test_provider_catalogs(qtbot, qapp):
    provider = _make_dummy_provider(qapp)
    cats = provider.catalogs()
    assert len(cats) == 1
    assert cats[0].name == "Test Catalog"


def test_provider_events_all(qtbot, qapp):
    provider = _make_dummy_provider(qapp)
    cat = provider.catalogs()[0]
    events = provider.events(cat)
    assert len(events) == 100


def test_provider_events_range_query(qtbot, qapp):
    provider = _make_dummy_provider(qapp)
    cat = provider.catalogs()[0]
    start = datetime(2020, 1, 10, tzinfo=timezone.utc)
    stop = datetime(2020, 1, 20, tzinfo=timezone.utc)
    events = provider.events(cat, start=start, stop=stop)
    assert all(e.start >= start for e in events)
    assert all(e.start <= stop for e in events)
    assert len(events) == 11  # days 10,11,...,20 inclusive


def test_provider_add_event(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    provider = _make_dummy_provider(qapp)
    cat = provider.catalogs()[0]
    new_event = CatalogEvent(
        uuid="evt-new",
        start=datetime(2020, 1, 5, 12, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 5, 13, tzinfo=timezone.utc),
    )
    with qtbot.waitSignal(provider.events_changed, timeout=1000):
        provider._add_event(cat, new_event)
    events = provider.events(cat)
    assert len(events) == 101
    starts = [e.start for e in events]
    assert starts == sorted(starts)


def test_provider_remove_event(qtbot, qapp):
    provider = _make_dummy_provider(qapp)
    cat = provider.catalogs()[0]
    events = provider.events(cat)
    to_remove = events[50]
    with qtbot.waitSignal(provider.events_changed, timeout=1000):
        provider._remove_event(cat, to_remove)
    assert len(provider.events(cat)) == 99
