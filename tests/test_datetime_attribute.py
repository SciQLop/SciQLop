"""Tests for DatetimeKnob spec + editor wiring."""
from .fixtures import *
from datetime import datetime, timezone


def test_datetimeknob_default_is_iso_string(qapp):
    from SciQLop.core.knobs import DatetimeKnob
    spec = DatetimeKnob(name="discovered_at")
    assert isinstance(spec.default, str)


def test_datetimeknob_roundtrip_serialization(qapp):
    from SciQLop.core.knobs import DatetimeKnob, spec_to_dict, spec_from_dict
    spec = DatetimeKnob(name="t", default="2026-05-02T14:30:00+00:00")
    d = spec_to_dict(spec)
    assert d["type"] == "DatetimeKnob"
    restored = spec_from_dict(d)
    assert restored == spec


def test_dialog_datetime_type_returns_datetimeknob(qtbot, qapp):
    from SciQLop.components.catalogs.ui.add_attribute_dialog import AddAttributeDialog
    from SciQLop.core.knobs import DatetimeKnob

    dialog = AddAttributeDialog()
    qtbot.addWidget(dialog)
    dialog._name.setText("discovered_at")
    dialog._select_type("Date/Time")
    spec = dialog.build_spec()
    assert isinstance(spec, DatetimeKnob)
    assert spec.name == "discovered_at"


def test_event_table_delegate_uses_datetime_editor_for_datetimeknob(qapp):
    from PySide6.QtWidgets import QStyleOptionViewItem, QDateTimeEdit
    from SciQLop.components.catalogs.ui.event_table_delegate import EventTableDelegate
    from SciQLop.components.catalogs.ui.event_table import EventTableModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.core.knobs import DatetimeKnob

    class TypedDummy(DummyProvider):
        def attribute_spec(self, catalog, key):
            if key == "discovered_at":
                return DatetimeKnob(name=key)
            return None

    provider = TypedDummy(num_catalogs=1, events_per_catalog=2)
    cat = provider.catalogs()[0]
    for ev in provider.events(cat):
        ev.set_meta("discovered_at", "2026-01-15T08:00:00+00:00")
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    delegate = EventTableDelegate(model)
    col = len(model._FIXED_COLUMNS) + model._meta_keys.index("discovered_at")
    idx = model.index(0, col)
    editor = delegate.createEditor(None, QStyleOptionViewItem(), idx)
    assert isinstance(editor, QDateTimeEdit)


def test_event_table_delegate_setEditorData_parses_iso_string(qapp):
    from PySide6.QtCore import QDateTime
    from PySide6.QtWidgets import QStyleOptionViewItem
    from SciQLop.components.catalogs.ui.event_table_delegate import EventTableDelegate
    from SciQLop.components.catalogs.ui.event_table import EventTableModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.core.knobs import DatetimeKnob

    class TypedDummy(DummyProvider):
        def attribute_spec(self, catalog, key):
            if key == "discovered_at":
                return DatetimeKnob(name=key)
            return None

    provider = TypedDummy(num_catalogs=1, events_per_catalog=2)
    cat = provider.catalogs()[0]
    for ev in provider.events(cat):
        ev.set_meta("discovered_at", "2026-01-15T08:00:00+00:00")
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    delegate = EventTableDelegate(model)
    col = len(model._FIXED_COLUMNS) + model._meta_keys.index("discovered_at")
    idx = model.index(0, col)
    editor = delegate.createEditor(None, QStyleOptionViewItem(), idx)
    delegate.setEditorData(editor, idx)
    qdt = editor.dateTime()
    assert qdt.date().year() == 2026
    assert qdt.date().month() == 1
    assert qdt.date().day() == 15


def test_event_table_delegate_setModelData_writes_iso_string(qapp):
    from PySide6.QtCore import QDateTime, Qt
    from PySide6.QtWidgets import QStyleOptionViewItem
    from SciQLop.components.catalogs.ui.event_table_delegate import EventTableDelegate
    from SciQLop.components.catalogs.ui.event_table import EventTableModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.core.knobs import DatetimeKnob

    class TypedDummy(DummyProvider):
        def attribute_spec(self, catalog, key):
            if key == "when":
                return DatetimeKnob(name=key)
            return None

    provider = TypedDummy(num_catalogs=1, events_per_catalog=2)
    cat = provider.catalogs()[0]
    for ev in provider.events(cat):
        ev.set_meta("when", "")
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    delegate = EventTableDelegate(model)
    col = len(model._FIXED_COLUMNS) + model._meta_keys.index("when")
    idx = model.index(0, col)
    editor = delegate.createEditor(None, QStyleOptionViewItem(), idx)
    target = QDateTime.fromString("2030-12-31T23:59:00", Qt.DateFormat.ISODate)
    target.setTimeSpec(Qt.TimeSpec.UTC)
    editor.setDateTime(target)
    delegate.setModelData(editor, model, idx)
    stored = provider.events(cat)[0].meta["when"]
    # Must be a string, parseable back to a datetime
    from datetime import datetime
    parsed = datetime.fromisoformat(stored)
    assert parsed.year == 2030
    assert parsed.month == 12


def test_format_meta_value_renders_iso_datetime_prettily(qapp):
    from SciQLop.components.catalogs.ui.event_table import _format_meta_value
    s = _format_meta_value("2026-05-02T14:30:00+00:00")
    assert s == "2026-05-02 14:30:00"
    # Non-iso strings pass through unchanged
    assert _format_meta_value("not-a-date") == "not-a-date"
