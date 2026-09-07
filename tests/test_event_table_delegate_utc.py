"""Catalog event editors must show and store UTC, never local time."""
import time
from datetime import datetime, timedelta, timezone

import pytest

from .fixtures import *
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QStyleOptionViewItem

from SciQLop.components.catalogs.ui.event_table_delegate import (
    EventTableDelegate, _qdatetime_from_iso,
)
from SciQLop.components.catalogs.ui.event_table import EventTableModel
from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
from SciQLop.core.knobs import DatetimeKnob

_START = datetime(2020, 1, 1, tzinfo=timezone.utc)
_ISO = "2026-01-15T08:00:00+00:00"


class _TypedDummy(DummyProvider):
    def attribute_spec(self, catalog, key):
        return DatetimeKnob(name=key) if key == "discovered_at" else None


@pytest.fixture
def paris_tz(monkeypatch):
    monkeypatch.setenv("TZ", "Europe/Paris")
    time.tzset()
    yield
    time.tzset()


@pytest.fixture
def model(qapp):
    provider = _TypedDummy(num_catalogs=1, events_per_catalog=2)
    cat = provider.catalogs()[0]
    for ev in provider.events(cat):
        ev.set_meta("discovered_at", _ISO)
    m = EventTableModel()
    m.set_context(provider, cat)
    m.set_events(provider.events(cat))
    return m


def _open_editor(model, col):
    delegate = EventTableDelegate(model)
    idx = model.index(0, col)
    editor = delegate.createEditor(None, QStyleOptionViewItem(), idx)
    delegate.setEditorData(editor, idx)
    return delegate, editor, idx


def test_start_editor_shows_the_utc_value_displayed_in_the_cell(paris_tz, model, qapp):
    _, editor, idx = _open_editor(model, 0)
    assert editor.text() == model.data(idx, Qt.ItemDataRole.DisplayRole)
    assert editor.dateTime().toSecsSinceEpoch() == int(_START.timestamp())


def test_start_editor_writes_back_the_same_instant(paris_tz, model, qapp):
    delegate, editor, idx = _open_editor(model, 0)
    editor.setTime(editor.time().addSecs(60))
    delegate.setModelData(editor, model, idx)
    assert model._events[0].start == _START + timedelta(minutes=1)


def test_datetimeknob_editor_shows_utc_and_roundtrips(paris_tz, model, qapp):
    col = len(model._FIXED_COLUMNS) + model._meta_keys.index("discovered_at")
    delegate, editor, idx = _open_editor(model, col)
    assert editor.text() == "2026-01-15 08:00:00"
    delegate.setModelData(editor, model, idx)
    assert datetime.fromisoformat(model._events[0].meta["discovered_at"]) == datetime.fromisoformat(_ISO)


def test_qdatetime_from_iso_keeps_the_instant(paris_tz, qapp):
    qdt = _qdatetime_from_iso(_ISO)
    assert qdt.toSecsSinceEpoch() == int(datetime.fromisoformat(_ISO).timestamp())
