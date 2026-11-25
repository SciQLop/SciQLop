"""A catalog provider and the event table follow each event's range without one closure per event.

PySide keeps every connection to a closure in one table that it scans when a sender dies, so destroying n
events that each have one costs n²: a session with big catalogs took hours to exit.
"""
from .fixtures import *  # noqa: F401,F403
import time
from datetime import datetime, timedelta, timezone

import shiboken6
from PySide6.QtCore import QObject, SIGNAL

from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
from SciQLop.components.catalogs.backend.provider import CatalogEvent
from SciQLop.components.catalogs.ui.event_table import EventTableModel

MANY = 20_000
SIGNAL_RANGE_CHANGED = SIGNAL("range_changed()")
T0 = datetime(2020, 1, 1, tzinfo=timezone.utc)


def _events(count, parent=None):
    return [CatalogEvent(uuid=f"e{i}", start=T0 + timedelta(hours=i), stop=T0 + timedelta(hours=i, minutes=30),
                         parent=parent) for i in range(count)]


def _seconds_to_destroy(holder):
    start = time.perf_counter()
    shiboken6.delete(holder)
    return time.perf_counter() - start


def _provider(catalogs=1):
    return DummyProvider(num_catalogs=catalogs, events_per_catalog=0)


def test_destroying_the_events_of_a_big_catalog_is_fast(qapp):
    provider, holder = _provider(), QObject()
    provider._set_events(provider.catalogs()[0], _events(MANY, parent=holder))

    assert _seconds_to_destroy(holder) < 1.0


def test_destroying_the_events_shown_in_the_table_is_fast(qapp):
    model, holder = EventTableModel(), QObject()
    model.set_events(_events(MANY, parent=holder))

    assert _seconds_to_destroy(holder) < 1.0


def test_moving_an_event_marks_every_catalog_holding_it(qapp):
    provider = _provider(catalogs=2)
    first, second = provider.catalogs()
    event, = _events(1)
    provider._set_events(first, [event])
    provider._add_event(second, event)

    event.start = T0 - timedelta(days=1)

    assert provider.is_dirty(first) and provider.is_dirty(second)


def test_an_event_taken_out_of_a_catalog_no_longer_marks_it(qapp):
    provider = _provider(catalogs=2)
    first, second = provider.catalogs()
    event, = _events(1)
    provider._set_events(first, [event])
    provider._set_events(second, [event])
    provider._remove_event(first, event)
    provider._set_events(second, [])

    event.start = T0 - timedelta(days=1)

    assert not provider.is_dirty(first) and not provider.is_dirty(second)


def _table_of(provider, events):
    """The table showing a catalogue: it hears of moved events from the provider, which follows
    each event once (the table connecting to 100,000 events took about 0.3 s per opening)."""
    catalog = provider.catalogs()[0]
    provider._set_events(catalog, events)
    model = EventTableModel()
    model.set_context(provider, catalog)
    model.set_events(provider.events(catalog))
    return model


def test_the_table_repaints_the_row_of_a_moved_event(qapp, qtbot):
    events = _events(3)
    model = _table_of(_provider(), events)

    with qtbot.waitSignal(model.dataChanged, timeout=1000) as changed:
        events[1].stop = T0 + timedelta(days=3)

    assert changed.args[0].row() == 1


def test_the_table_ignores_events_it_no_longer_shows(qapp, qtbot):
    provider, old = _provider(), _events(2)
    model = _table_of(provider, old)
    model.set_events([])

    with qtbot.assertNotEmitted(model.dataChanged):
        old[0].stop = T0 + timedelta(days=3)


def test_the_table_does_not_connect_to_each_event(qapp):
    events = _events(3)
    model = _table_of(_provider(), events)

    assert model.rowCount() == 3 and [event.receivers(SIGNAL_RANGE_CHANGED) for event in events] == [1, 1, 1]  # the provider's only


def test_a_moved_event_takes_its_sorted_place(qapp, qtbot):
    from PySide6.QtCore import Qt
    events = _events(3)
    model = _table_of(_provider(), events)
    model.sort(0, Qt.SortOrder.AscendingOrder)

    events[0].start, events[0].stop = T0 + timedelta(days=5), T0 + timedelta(days=5, hours=1)

    qtbot.waitUntil(lambda: [model.event_at(row).uuid for row in range(3)] == ["e1", "e2", "e0"], timeout=1000)
