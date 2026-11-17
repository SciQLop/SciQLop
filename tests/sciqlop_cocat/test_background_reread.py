"""Smart catalogues are re-read in one background worker (cocat-rs 0.10.2 reads without the GIL):
an edit in a big project no longer freezes SciQLop. The results are applied on the Qt thread, one
read at a time, and a result for a catalogue gone meanwhile is dropped."""
import threading
import time

import pytest
from PySide6.QtCore import QTimer

from SciQLop.components.catalogs import CatalogEvent

from .conftest import HOUR, T0

RULE = {"filter": {"all": True}, "where": {"contains": ["tags", "s"]}}
SLOW_S = 0.4


class Slow:
    """A cocat-rs catalogue whose bulk read takes a while, and which says where and when it ran."""

    def __init__(self, catalogue, log, fail=False):
        self._catalogue, self._log, self._fail = catalogue, log, fail

    def __getattr__(self, name):
        return getattr(self._catalogue, name)

    def event_arrays(self, **kw):
        self._log.append(("start", threading.current_thread() is threading.main_thread(), time.monotonic()))
        time.sleep(SLOW_S)
        self._log.append(("end", None, time.monotonic()))
        if self._fail:
            raise RuntimeError("this rule cannot be read")
        return self._catalogue.event_arrays(**kw)


@pytest.fixture
def smart(attached, room):
    catalog = attached.create_catalog("tagged", ["r"])
    room.catalogue(catalog.uuid).rule = RULE
    attached.reload_catalog(catalog)
    return catalog


def slow_reads(provider, monkeypatch, fail=False):
    log = []
    real = provider._cocat_catalogue
    monkeypatch.setattr(provider, "_cocat_catalogue", lambda c: Slow(real(c), log, fail))
    return log


def add_tagged_event(provider, room):
    plain = provider.create_catalog("plain", ["r"])
    provider.add_event(plain, CatalogEvent(uuid="e1", start=T0, stop=T0 + HOUR, meta={"tags": ["s"]}))


def test_a_re_read_runs_off_the_gui_thread_and_does_not_block_it(attached, room, smart, monkeypatch, qtbot):
    log = slow_reads(attached, monkeypatch)
    add_tagged_event(attached, room)
    ticks = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(time.monotonic()))
    timer.start(10)

    started = time.monotonic()
    attached.refresh_smart_catalogs()
    assert time.monotonic() - started < SLOW_S / 4  # returned at once

    qtbot.waitUntil(lambda: [e.uuid for e in attached.events(smart)] == ["e1"], timeout=5000)
    timer.stop()
    [(_, on_main, began)] = [entry for entry in log if entry[0] == "start"]
    ended = next(t for kind, _, t in log if kind == "end")
    assert not on_main
    assert len([t for t in ticks if began < t < ended]) >= 10  # the GUI kept running meanwhile


def test_one_read_at_a_time_and_marks_made_meanwhile_read_next(attached, room, smart, monkeypatch, qtbot):
    log = slow_reads(attached, monkeypatch)
    add_tagged_event(attached, room)
    attached.refresh_smart_catalogs()
    qtbot.waitUntil(lambda: any(kind == "start" for kind, *_ in log), timeout=2000)
    attached.mark_smart_dirty("r")
    attached.refresh_smart_catalogs()  # while the first read runs
    qtbot.waitUntil(lambda: [kind for kind, *_ in log].count("end") == 2, timeout=5000)
    kinds = [kind for kind, *_ in log]
    assert kinds == ["start", "end", "start", "end"]  # never two at once


def test_a_result_for_a_catalogue_gone_meanwhile_is_dropped(attached, room, smart, monkeypatch, qtbot):
    log = slow_reads(attached, monkeypatch)
    add_tagged_event(attached, room)
    attached.refresh_smart_catalogs()
    qtbot.waitUntil(lambda: any(kind == "start" for kind, *_ in log), timeout=2000)
    attached.remove_catalog(smart)
    qtbot.waitUntil(lambda: attached._reading is None, timeout=5000)
    assert smart.uuid not in [c.uuid for c in attached.catalogs()]
    assert attached.events(smart) == []


def test_a_rule_the_worker_cannot_read_marks_the_catalogue_unreadable(attached, room, smart, monkeypatch, qtbot):
    slow_reads(attached, monkeypatch, fail=True)
    add_tagged_event(attached, room)
    attached.refresh_smart_catalogs()
    qtbot.waitUntil(lambda: smart.uuid in attached._unreadable, timeout=5000)
    assert "cannot be read" in attached._unreadable[smart.uuid]


def test_closing_waits_for_the_read_in_flight(attached, room, smart, monkeypatch, qtbot):
    from .test_provider_rooms import run
    log = slow_reads(attached, monkeypatch)
    add_tagged_event(attached, room)
    attached.refresh_smart_catalogs()
    qtbot.waitUntil(lambda: any(kind == "start" for kind, *_ in log), timeout=2000)
    run(attached.close())
    assert [kind for kind, *_ in log] == ["start", "end"]


def test_results_are_shown_one_catalogue_per_turn_of_the_qt_loop(attached, room, smart, qtbot):
    from SciQLop.plugins.sciqlop_cocat.rereading import read_rows
    other = attached.create_catalog("tagged too", ["r"])
    room.catalogue(other.uuid).rule = RULE
    add_tagged_event(attached, room)
    reads = [(c, *read_rows(room.catalogue(c.uuid))) for c in (smart, other)]
    attached._reading = [smart, other]
    attached._apply_reads(reads)
    assert [e.uuid for e in attached.events(smart)] == ["e1"]
    assert attached.events(other) == []  # next turn
    qtbot.waitUntil(lambda: [e.uuid for e in attached.events(other)] == ["e1"], timeout=2000)
    assert attached._reading is None


def test_a_re_read_that_finds_nothing_new_says_nothing(attached, room, smart, qtbot):
    add_tagged_event(attached, room)
    attached.refresh_smart_catalogs()
    qtbot.waitUntil(lambda: [e.uuid for e in attached.events(smart)] == ["e1"], timeout=5000)
    changes = []
    attached.events_changed.connect(changes.append)
    attached.mark_smart_dirty("r")
    attached.refresh_smart_catalogs()
    qtbot.waitUntil(lambda: attached._reading is None, timeout=5000)
    assert changes == []
