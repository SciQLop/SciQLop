"""The event filter delegates of the catalog browser's event table: the default one, PlainTextFilter,
matches the text the table shows, off the GUI thread; a provider may supply its own
(CatalogProvider.event_filter). Also the providers' default filter_events, for Python."""
import threading
from datetime import datetime, timezone

import pytest

from .fixtures import *  # noqa: F401,F403


def _ev(uuid, meta, day=1):
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    return CatalogEvent(uuid=uuid, start=datetime(2024, 1, day, tzinfo=timezone.utc),
                        stop=datetime(2024, 1, day, 1, tzinfo=timezone.utc), meta=meta)


@pytest.fixture
def events(qapp):
    return [_ev("e1", {"class": "Solar_Wind", "probe": "mms 1 / 2024-01"}),
            _ev("e2", {"class": "magnetosheath", "rating": 0.5}, day=2),
            _ev("e3", {"class": "cusp"}, day=3)]


def test_an_event_s_text_is_what_its_row_shows(qapp):
    from SciQLop.components.catalogs.backend.event_text import event_text
    text = event_text(_ev("e1", {"class": "Solar_Wind", "tags": ["a", "b"], "n": 1.5}))
    assert text == "2024-01-01 00:00:00\n2024-01-01 01:00:00\nsolar_wind\na, b\n1.5"


@pytest.fixture
def plain(qapp, events):
    from SciQLop.components.catalogs.ui.event_filter import PlainTextFilter
    f = PlainTextFilter()
    f.set_events(events)
    yield f
    f.dispose()


def _kept_after(qtbot, f, text):
    with qtbot.waitSignal(f.changed, timeout=2000):
        f.box.setText(text)
    return f.kept()


def test_an_empty_box_keeps_everything(plain):
    assert plain.kept() is None


def test_any_column_matches_case_insensitively(plain, qtbot):
    assert _kept_after(qtbot, plain, "SOLAR") == {"e1"}
    assert _kept_after(qtbot, plain, "MMS 1") == {"e1"}          # punctuation and spaces kept
    assert _kept_after(qtbot, plain, "2024-01-02") == {"e2"}     # the start time as shown
    assert _kept_after(qtbot, plain, "0.5") == {"e2"}            # a number as shown
    assert _kept_after(qtbot, plain, "") is None


def test_matching_runs_off_the_gui_thread_and_typing_is_debounced(plain, qtbot, monkeypatch):
    from SciQLop.components.catalogs.ui import event_filter
    runs = []
    real = event_filter.text_keeps
    monkeypatch.setattr(event_filter, "text_keeps", lambda texts, needle: (
        runs.append(threading.current_thread() is threading.main_thread()), real(texts, needle))[1])
    with qtbot.waitSignal(plain.changed, timeout=2000):
        for ch in "magneto":
            plain.box.setText(plain.box.text() + ch)
    assert plain.kept() == {"e2"} and runs == [False]


def test_new_events_are_filtered_with_the_text_already_typed(plain, events, qtbot):
    _kept_after(qtbot, plain, "cusp")
    with qtbot.waitSignal(plain.changed, timeout=2000):
        plain.set_events([*events, _ev("e4", {"class": "cusp again"}, day=4)])
    assert plain.kept() == {"e3", "e4"}


def test_its_state_is_its_text(plain, qtbot):
    _kept_after(qtbot, plain, "cusp")
    assert plain.state() == "cusp"
    from SciQLop.components.catalogs.ui.event_filter import PlainTextFilter
    other = PlainTextFilter()
    with qtbot.waitSignal(other.changed, timeout=2000):
        other.set_events([_ev("x", {"class": "cusp"})])
        other.restore("cusp")
    assert other.box.text() == "cusp" and other.kept() == {"x"}
    other.dispose()


def test_clear_empties_the_box_at_once(plain, qtbot):
    _kept_after(qtbot, plain, "cusp")
    plain.clear()
    assert plain.box.text() == "" and plain.kept() is None


def test_providers_default_to_the_plain_filter(qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, name="FilterDefaults")
    catalog = provider.catalogs()[0]
    provider.add_event(catalog, _ev("e1", {"class": "solar_wind"}))
    provider.add_event(catalog, _ev("e2", {"class": "cusp"}, day=2))
    assert provider.event_filter(catalog, None) is None
    assert [e.uuid for e in provider.filter_events(catalog, "SOLAR")] == ["e1"]
    assert len(provider.filter_events(catalog, "")) == 2
