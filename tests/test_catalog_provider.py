from .fixtures import *
import pytest
from datetime import datetime, timezone


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
