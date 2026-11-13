"""A catalog provider and the event table follow each event's range without one closure per event.

PySide keeps every connection to a closure in one table that it scans when a sender dies, so destroying n
events that each have one costs n²: a session with big catalogs took hours to exit.
"""
from .fixtures import *  # noqa: F401,F403
import time
from datetime import datetime, timedelta, timezone

import shiboken6
from PySide6.QtCore import QObject

from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
from SciQLop.components.catalogs.backend.provider import CatalogEvent
from SciQLop.components.catalogs.ui.event_table import EventTableModel

MANY = 20_000
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


def test_the_table_repaints_the_row_of_a_moved_event(qapp, qtbot):
    model = EventTableModel()
    events = _events(3)
    model.set_events(events)

    with qtbot.waitSignal(model.dataChanged, timeout=1000) as changed:
        events[1].stop = T0 + timedelta(days=3)

    assert changed.args[0].row() == 1


def test_the_table_stops_following_the_events_it_no_longer_shows(qapp, qtbot):
    model = EventTableModel()
    old = _events(2)
    model.set_events(old)
    model.set_events([])

    with qtbot.assertNotEmitted(model.dataChanged):
        old[0].stop = T0 + timedelta(days=3)
