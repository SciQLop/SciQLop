from .fixtures import *
from PySide6.QtCore import Qt, QModelIndex
from SciQLop.components.catalogs.ui.event_table import EventTableModel
from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
from SciQLop.components.catalogs.backend.provider import Capability


def test_event_model_flags_editable_when_provider_has_edit_capability(qapp):
    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    idx = model.index(0, 0)
    assert model.flags(idx) & Qt.ItemFlag.ItemIsEditable
    idx_meta = model.index(0, 2)
    assert model.flags(idx_meta) & Qt.ItemFlag.ItemIsEditable


def test_event_model_flags_not_editable_without_capability(qapp):
    class ReadOnlyProvider(DummyProvider):
        def capabilities(self, catalog=None):
            return set()  # no EDIT_EVENTS

    provider = ReadOnlyProvider(num_catalogs=1, events_per_catalog=2)
    cat = provider.catalogs()[0]
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    idx = model.index(0, 0)
    assert not (model.flags(idx) & Qt.ItemFlag.ItemIsEditable)


def test_event_model_setdata_meta_routes_to_provider(qtbot, qapp):
    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    score_col = len(model._FIXED_COLUMNS) + model._meta_keys.index("score")
    idx = model.index(0, score_col)

    with qtbot.waitSignal(provider.event_meta_changed, timeout=1000):
        ok = model.setData(idx, 0.99, Qt.ItemDataRole.EditRole)

    assert ok is True
    event = provider.events(cat)[0]
    assert event.meta["score"] == 0.99


def test_event_model_setdata_start_updates_event(qtbot, qapp):
    from datetime import datetime, timezone
    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    target = model.event_at(0)
    new_start = datetime(2025, 6, 15, 12, 0, tzinfo=timezone.utc)
    ok = model.setData(model.index(0, 0), new_start, Qt.ItemDataRole.EditRole)
    assert ok is True
    assert target.start == new_start


def test_event_model_setdata_returns_false_without_context(qapp):
    model = EventTableModel()
    # No set_context called
    model.set_events([])
    assert model.setData(model.index(0, 0), "anything", Qt.ItemDataRole.EditRole) is False


def test_event_meta_changed_emits_data_changed_for_existing_key(qtbot, qapp):
    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    event = provider.events(cat)[0]
    with qtbot.waitSignal(model.dataChanged, timeout=1000):
        provider.set_event_meta(cat, event, "score", 0.77)


def test_event_meta_changed_with_new_key_extends_columns(qtbot, qapp):
    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    initial_cols = model.columnCount()
    event = provider.events(cat)[0]
    provider.set_event_meta(cat, event, "brand_new_key", "x")
    qapp.processEvents()
    assert model.columnCount() > initial_cols
    assert "brand_new_key" in model._meta_keys


def test_new_meta_key_emits_columns_inserted_not_reset(qtbot, qapp):
    """Adding a new meta key must use begin/endInsertColumns to preserve view state."""
    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    received_inserts = []
    received_resets = []
    model.columnsInserted.connect(lambda *args: received_inserts.append(args))
    model.modelReset.connect(lambda: received_resets.append(True))

    event = provider.events(cat)[0]
    provider.set_event_meta(cat, event, "brand_new", "x")
    qapp.processEvents()

    assert len(received_inserts) == 1
    assert received_resets == []


def test_event_table_delegate_creates_int_editor_for_int_column(qapp):
    from PySide6.QtWidgets import QSpinBox, QStyleOptionViewItem
    from SciQLop.components.catalogs.ui.event_table_delegate import EventTableDelegate

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    delegate = EventTableDelegate(model)
    index_col = len(model._FIXED_COLUMNS) + model._meta_keys.index("index")
    idx = model.index(0, index_col)
    editor = delegate.createEditor(None, QStyleOptionViewItem(), idx)
    assert editor is not None
    spinboxes = editor.findChildren(QSpinBox)
    assert len(spinboxes) == 1


def test_event_table_delegate_creates_float_editor_for_float_column(qapp):
    from PySide6.QtWidgets import QDoubleSpinBox, QStyleOptionViewItem
    from SciQLop.components.catalogs.ui.event_table_delegate import EventTableDelegate

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    delegate = EventTableDelegate(model)
    score_col = len(model._FIXED_COLUMNS) + model._meta_keys.index("score")
    idx = model.index(0, score_col)
    editor = delegate.createEditor(None, QStyleOptionViewItem(), idx)
    spinboxes = editor.findChildren(QDoubleSpinBox)
    assert len(spinboxes) == 1


def test_event_table_delegate_creates_string_editor_for_str_column(qapp):
    from PySide6.QtWidgets import QLineEdit, QStyleOptionViewItem
    from SciQLop.components.catalogs.ui.event_table_delegate import EventTableDelegate

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    delegate = EventTableDelegate(model)
    class_col = len(model._FIXED_COLUMNS) + model._meta_keys.index("class")
    idx = model.index(0, class_col)
    editor = delegate.createEditor(None, QStyleOptionViewItem(), idx)
    assert editor.findChildren(QLineEdit)


def test_event_table_delegate_creates_datetime_editor_for_start_column(qapp):
    from PySide6.QtWidgets import QDateTimeEdit, QStyleOptionViewItem
    from SciQLop.components.catalogs.ui.event_table_delegate import EventTableDelegate

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    delegate = EventTableDelegate(model)
    idx = model.index(0, 0)
    editor = delegate.createEditor(None, QStyleOptionViewItem(), idx)
    assert isinstance(editor, QDateTimeEdit)


def test_event_table_delegate_setEditorData_setModelData_roundtrip_meta(qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QStyleOptionViewItem
    from SciQLop.components.catalogs.ui.event_table_delegate import EventTableDelegate

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))
    delegate = EventTableDelegate(model)
    score_col = len(model._FIXED_COLUMNS) + model._meta_keys.index("score")
    idx = model.index(0, score_col)
    editor = delegate.createEditor(None, QStyleOptionViewItem(), idx)
    delegate.setEditorData(editor, idx)
    # Inject a new value via the SettingDelegate API
    editor.set_value(0.123)
    delegate.setModelData(editor, model, idx)
    assert provider.events(cat)[0].meta["score"] == 0.123


def test_event_table_delegate_column_type_inference_resets_on_model_reset(qapp):
    from SciQLop.components.catalogs.ui.event_table_delegate import EventTableDelegate

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))
    delegate = EventTableDelegate(model)
    score_col = len(model._FIXED_COLUMNS) + model._meta_keys.index("score")
    delegate._column_type(score_col)  # cache something
    assert score_col in delegate._column_types

    # Trigger a reset
    model.set_events(provider.events(cat))
    assert delegate._column_types == {}
