"""Tests for the AddAttributeDialog (name + type → KnobSpec)."""
from .fixtures import *
from PySide6.QtCore import Qt


def test_dialog_default_type_is_text(qtbot, qapp):
    from SciQLop.components.catalogs.ui.add_attribute_dialog import AddAttributeDialog
    from SciQLop.core.knobs import StringKnob

    dialog = AddAttributeDialog()
    qtbot.addWidget(dialog)
    dialog._name.setText("note")
    spec = dialog.build_spec()
    assert isinstance(spec, StringKnob)
    assert spec.name == "note"


def test_dialog_integer_type_returns_intknob(qtbot, qapp):
    from SciQLop.components.catalogs.ui.add_attribute_dialog import AddAttributeDialog
    from SciQLop.core.knobs import IntKnob

    dialog = AddAttributeDialog()
    qtbot.addWidget(dialog)
    dialog._name.setText("count")
    dialog._select_type("Integer")
    spec = dialog.build_spec()
    assert isinstance(spec, IntKnob)
    assert spec.name == "count"


def test_dialog_number_type_returns_floatknob(qtbot, qapp):
    from SciQLop.components.catalogs.ui.add_attribute_dialog import AddAttributeDialog
    from SciQLop.core.knobs import FloatKnob

    dialog = AddAttributeDialog()
    qtbot.addWidget(dialog)
    dialog._name.setText("score")
    dialog._select_type("Number")
    spec = dialog.build_spec()
    assert isinstance(spec, FloatKnob)


def test_dialog_yes_no_returns_boolknob(qtbot, qapp):
    from SciQLop.components.catalogs.ui.add_attribute_dialog import AddAttributeDialog
    from SciQLop.core.knobs import BoolKnob

    dialog = AddAttributeDialog()
    qtbot.addWidget(dialog)
    dialog._name.setText("flag")
    dialog._select_type("Yes/No")
    spec = dialog.build_spec()
    assert isinstance(spec, BoolKnob)


def test_dialog_tags_returns_stringlistknob(qtbot, qapp):
    from SciQLop.components.catalogs.ui.add_attribute_dialog import AddAttributeDialog
    from SciQLop.core.knobs import StringListKnob

    dialog = AddAttributeDialog()
    qtbot.addWidget(dialog)
    dialog._name.setText("labels")
    dialog._select_type("Tags")
    spec = dialog.build_spec()
    assert isinstance(spec, StringListKnob)


def test_dialog_empty_name_returns_none(qtbot, qapp):
    from SciQLop.components.catalogs.ui.add_attribute_dialog import AddAttributeDialog

    dialog = AddAttributeDialog()
    qtbot.addWidget(dialog)
    spec = dialog.build_spec()
    assert spec is None


def test_browser_add_attribute_uses_dialog_and_writes_spec(qtbot, qapp, monkeypatch):
    from PySide6.QtCore import QItemSelectionModel
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.add_attribute_dialog import AddAttributeDialog
    from SciQLop.core.knobs import IntKnob

    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    provider = DummyProvider(num_catalogs=1, events_per_catalog=2)
    cat = provider.catalogs()[0]
    browser._current_provider = provider
    browser._current_catalog = cat
    browser._event_model.set_context(provider, cat)
    browser._event_model.set_events(provider.events(cat))

    sm = browser._event_table.selectionModel()
    sm.select(
        browser._sort_proxy.index(0, 0),
        QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
    )

    # Stub the dialog: instead of exec(), inject a pre-filled spec.
    fake_spec = IntKnob(name="precision", min=0, max=100, default=42)

    def fake_run_dialog(parent):
        return fake_spec

    monkeypatch.setattr(
        "SciQLop.components.catalogs.ui.add_attribute_dialog.run_add_attribute_dialog",
        fake_run_dialog,
    )

    browser._on_add_attribute_clicked()

    assert provider.attribute_spec(cat, "precision") == fake_spec
    assert provider.events(cat)[0].meta.get("precision") == 42


def test_browser_add_attribute_cancel_does_nothing(qtbot, qapp, monkeypatch):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    provider = DummyProvider(num_catalogs=1, events_per_catalog=2)
    cat = provider.catalogs()[0]
    browser._current_provider = provider
    browser._current_catalog = cat
    browser._event_model.set_context(provider, cat)
    browser._event_model.set_events(provider.events(cat))

    initial_keys = set(browser._event_model._meta_keys)

    monkeypatch.setattr(
        "SciQLop.components.catalogs.ui.add_attribute_dialog.run_add_attribute_dialog",
        lambda parent: None,
    )

    browser._on_add_attribute_clicked()
    assert set(browser._event_model._meta_keys) == initial_keys
