"""Tests for the TagListDelegate (chip/token editor for list-of-strings)."""
from .fixtures import *
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QLineEdit


def test_tag_list_set_value_renders_chips(qtbot, qapp):
    from SciQLop.components.settings.ui.settings_delegates import TagListDelegate, _TagChip

    delegate = TagListDelegate()
    qtbot.addWidget(delegate)
    delegate.set_value(["foo", "bar"])
    chips = delegate.findChildren(_TagChip)
    texts = [c._text for c in chips]
    assert texts == ["foo", "bar"]
    assert delegate.get_value() == ["foo", "bar"]


def test_tag_list_enter_adds_tag(qtbot, qapp):
    from SciQLop.components.settings.ui.settings_delegates import TagListDelegate

    delegate = TagListDelegate()
    qtbot.addWidget(delegate)
    delegate._input.setText("solar")
    QTest.keyClick(delegate._input, Qt.Key.Key_Return)
    assert delegate.get_value() == ["solar"]
    assert delegate._input.text() == ""


def test_tag_list_enter_with_text_consumes_event(qtbot, qapp):
    """Enter on non-empty input commits the tag and consumes the event so the
    cell editor stays open (Qt would otherwise close it on Enter)."""
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent
    from SciQLop.components.settings.ui.settings_delegates import TagListDelegate

    delegate = TagListDelegate()
    qtbot.addWidget(delegate)
    delegate._input.setText("solar")
    ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    consumed = delegate.eventFilter(delegate._input, ev)
    assert consumed is True
    assert delegate.get_value() == ["solar"]


def test_tag_list_enter_with_empty_input_propagates(qtbot, qapp):
    """Enter on empty input does NOT consume the event — the user's 'I'm done' signal
    is forwarded to Qt so the cell editor closes naturally."""
    from PySide6.QtCore import QEvent
    from PySide6.QtGui import QKeyEvent
    from SciQLop.components.settings.ui.settings_delegates import TagListDelegate

    delegate = TagListDelegate()
    qtbot.addWidget(delegate)
    delegate.set_value(["foo"])
    delegate._input.setText("")
    ev = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
    consumed = delegate.eventFilter(delegate._input, ev)
    assert consumed is False
    assert delegate.get_value() == ["foo"]


def test_tag_list_comma_adds_tag(qtbot, qapp):
    from SciQLop.components.settings.ui.settings_delegates import TagListDelegate

    delegate = TagListDelegate()
    qtbot.addWidget(delegate)
    delegate._input.setText("magnetosheath,")
    assert delegate.get_value() == ["magnetosheath"]
    assert delegate._input.text() == ""


def test_tag_list_chip_close_removes_tag(qtbot, qapp):
    from SciQLop.components.settings.ui.settings_delegates import TagListDelegate, _TagChip

    delegate = TagListDelegate()
    qtbot.addWidget(delegate)
    delegate.set_value(["foo", "bar", "baz"])
    chips = delegate.findChildren(_TagChip)
    target = next(c for c in chips if c._text == "bar")
    target.removed.emit("bar")
    assert delegate.get_value() == ["foo", "baz"]


def test_tag_list_dedupes(qtbot, qapp):
    from SciQLop.components.settings.ui.settings_delegates import TagListDelegate

    delegate = TagListDelegate()
    qtbot.addWidget(delegate)
    delegate.set_value(["foo"])
    delegate._input.setText("foo")
    QTest.keyClick(delegate._input, Qt.Key.Key_Return)
    assert delegate.get_value() == ["foo"]


def test_tag_list_value_changed_signal_fires(qtbot, qapp):
    from SciQLop.components.settings.ui.settings_delegates import TagListDelegate

    delegate = TagListDelegate()
    qtbot.addWidget(delegate)
    received = []
    delegate.value_changed.connect(received.append)
    delegate._input.setText("alpha")
    QTest.keyClick(delegate._input, Qt.Key.Key_Return)
    assert received == [["alpha"]]


def test_tag_list_suggestions_attaches_completer(qtbot, qapp):
    from SciQLop.components.settings.ui.settings_delegates import TagListDelegate

    delegate = TagListDelegate(suggestions=["one", "two", "three"])
    qtbot.addWidget(delegate)
    assert delegate._input.completer() is not None


def test_event_table_delegate_uses_tag_list_for_stringlistknob(qapp):
    """When the provider declares StringListKnob for a key, createEditor returns TagListDelegate."""
    from PySide6.QtWidgets import QStyleOptionViewItem
    from SciQLop.components.catalogs.ui.event_table_delegate import EventTableDelegate
    from SciQLop.components.catalogs.ui.event_table import EventTableModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.settings.ui.settings_delegates import TagListDelegate
    from SciQLop.core.knobs import StringListKnob

    class TypedDummy(DummyProvider):
        def attribute_spec(self, catalog, key):
            if key == "tags":
                return StringListKnob(name=key, default=())
            return None

    provider = TypedDummy(num_catalogs=1, events_per_catalog=2)
    cat = provider.catalogs()[0]
    for ev in provider.events(cat):
        ev.set_meta("tags", ["alpha", "beta"])
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    delegate = EventTableDelegate(model)
    tags_col = len(model._FIXED_COLUMNS) + model._meta_keys.index("tags")
    idx = model.index(0, tags_col)
    editor = delegate.createEditor(None, QStyleOptionViewItem(), idx)
    assert isinstance(editor, TagListDelegate)


def test_event_table_delegate_setEditorData_loads_tags(qapp):
    from PySide6.QtWidgets import QStyleOptionViewItem
    from SciQLop.components.catalogs.ui.event_table_delegate import EventTableDelegate
    from SciQLop.components.catalogs.ui.event_table import EventTableModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.core.knobs import StringListKnob

    class TypedDummy(DummyProvider):
        def attribute_spec(self, catalog, key):
            if key == "tags":
                return StringListKnob(name=key, default=())
            return None

    provider = TypedDummy(num_catalogs=1, events_per_catalog=2)
    cat = provider.catalogs()[0]
    for ev in provider.events(cat):
        ev.set_meta("tags", ["x", "y"])
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    delegate = EventTableDelegate(model)
    tags_col = len(model._FIXED_COLUMNS) + model._meta_keys.index("tags")
    idx = model.index(0, tags_col)
    editor = delegate.createEditor(None, QStyleOptionViewItem(), idx)
    delegate.setEditorData(editor, idx)
    assert editor.get_value() == ["x", "y"]


def test_event_table_delegate_setModelData_writes_tags(qapp):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QStyleOptionViewItem
    from SciQLop.components.catalogs.ui.event_table_delegate import EventTableDelegate
    from SciQLop.components.catalogs.ui.event_table import EventTableModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.core.knobs import StringListKnob

    class TypedDummy(DummyProvider):
        def attribute_spec(self, catalog, key):
            if key == "tags":
                return StringListKnob(name=key, default=())
            return None

    provider = TypedDummy(num_catalogs=1, events_per_catalog=2)
    cat = provider.catalogs()[0]
    for ev in provider.events(cat):
        ev.set_meta("tags", [])
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    delegate = EventTableDelegate(model)
    tags_col = len(model._FIXED_COLUMNS) + model._meta_keys.index("tags")
    idx = model.index(0, tags_col)
    editor = delegate.createEditor(None, QStyleOptionViewItem(), idx)
    editor.set_value(["new1", "new2"])
    delegate.setModelData(editor, model, idx)
    assert provider.events(cat)[0].meta["tags"] == ["new1", "new2"]


def test_event_table_format_meta_value_for_list(qapp):
    """Display a list-of-strings as comma-separated, not Python repr."""
    from SciQLop.components.catalogs.ui.event_table import _format_meta_value

    assert _format_meta_value(["alpha", "beta"]) == "alpha, beta"
    assert _format_meta_value(("x", "y", "z")) == "x, y, z"
    assert _format_meta_value([]) == ""


def test_inferred_list_column_falls_back_to_tag_list_delegate(qapp):
    """No spec, but values are lists → infer list, return TagListDelegate."""
    from PySide6.QtWidgets import QStyleOptionViewItem
    from SciQLop.components.catalogs.ui.event_table_delegate import EventTableDelegate
    from SciQLop.components.catalogs.ui.event_table import EventTableModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.settings.ui.settings_delegates import TagListDelegate

    # DummyProvider returns None from attribute_spec — pure inference path
    provider = DummyProvider(num_catalogs=1, events_per_catalog=2)
    cat = provider.catalogs()[0]
    for ev in provider.events(cat):
        ev.set_meta("custom_tags", ["a", "b"])
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    delegate = EventTableDelegate(model)
    col = len(model._FIXED_COLUMNS) + model._meta_keys.index("custom_tags")
    idx = model.index(0, col)
    editor = delegate.createEditor(None, QStyleOptionViewItem(), idx)
    assert isinstance(editor, TagListDelegate)


def test_tscat_attribute_spec_tags_is_stringlistknob(qapp):
    from SciQLop.plugins.tscat_catalogs.tscat_provider import TscatCatalogProvider
    from SciQLop.core.knobs import StringListKnob

    provider = TscatCatalogProvider()
    cat = next(iter(provider.catalogs()), None)
    spec = provider.attribute_spec(cat, "tags")
    assert isinstance(spec, StringListKnob)


def test_cocat_attribute_spec_tags_is_stringlistknob(qapp):
    from SciQLop.plugins.collaborative_catalogs.cocat_provider import CocatCatalogProvider
    from SciQLop.core.knobs import StringListKnob

    provider = CocatCatalogProvider()
    spec = provider.attribute_spec(None, "tags")
    assert isinstance(spec, StringListKnob)
