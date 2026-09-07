"""Nice-to-haves from the 2026-09-07 catalog UX review: clearing the tree
filter must not throw away the expansion the user built before typing, and
column widths the user dragged must survive model resets and reselection.
"""
from .fixtures import *
import pytest
from datetime import datetime, timezone

from PySide6.QtCore import QModelIndex


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR", str(tmp_path))


@pytest.fixture
def browser(qtbot, qapp, isolated_config):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    b = CatalogBrowser()
    qtbot.addWidget(b)
    return b


def _provider_proxy_index(browser, provider):
    model = browser._tree_model
    for row in range(model.rowCount(QModelIndex())):
        idx = model.index(row, 0, QModelIndex())
        if model.node_from_index(idx).provider is provider:
            return browser._proxy_model.mapFromSource(idx)
    raise AssertionError("provider node not found")


def test_clearing_the_filter_restores_the_previous_expansion(qtbot, qapp, isolated_config):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    prov_a = DummyProvider(num_catalogs=1, events_per_catalog=0, name="ExpandA")
    prov_b = DummyProvider(num_catalogs=1, events_per_catalog=0, name="ExpandB")
    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    tree = browser._catalog_tree
    tree.collapseAll()
    tree.expand(_provider_proxy_index(browser, prov_a))

    browser._filter_bar.setText("zzz-no-match")
    browser._filter_bar.setText("")

    assert tree.isExpanded(_provider_proxy_index(browser, prov_a))
    assert not tree.isExpanded(_provider_proxy_index(browser, prov_b))


def _open_catalog(browser, provider, catalog):
    browser._current_provider = provider
    browser._current_catalog = catalog
    browser._event_model.set_context(provider, catalog)
    browser._event_model.set_events(provider.events(catalog))
    browser._apply_view_state(catalog)


def _col(browser, key):
    model = browser._event_model
    if key in model._FIXED_COLUMNS:
        return model._FIXED_COLUMNS.index(key)
    return len(model._FIXED_COLUMNS) + model._meta_keys.index(key)


def _event(uuid):
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    return CatalogEvent(uuid=uuid, start=datetime(2020, 1, 1, tzinfo=timezone.utc),
                        stop=datetime(2020, 1, 2, tzinfo=timezone.utc),
                        meta={"class": 1.0, "class": "long text " * 20})


def test_dragged_column_width_survives_a_model_reset(browser):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    provider = DummyProvider(num_catalogs=1, events_per_catalog=3, name="WidthReset")
    cat = provider.catalogs()[0]
    _open_catalog(browser, provider, cat)
    header = browser._event_table.horizontalHeader()
    col = _col(browser, "class")
    header.resizeSection(col, 222)

    browser._event_model.set_events(provider.events(cat) + [_event("w-1")])

    assert header.sectionSize(col) == 222


def test_dragged_column_width_is_persisted_and_reapplied(browser):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.event_table_view_state import get_view_state
    provider = DummyProvider(num_catalogs=2, events_per_catalog=3, name="WidthPersist")
    cat_a, cat_b = provider.catalogs()
    _open_catalog(browser, provider, cat_a)
    header = browser._event_table.horizontalHeader()
    col = _col(browser, "class")
    header.resizeSection(col, 222)
    browser._save_view_state()
    assert get_view_state(cat_a.uuid).column_widths == {"class": 222}

    _open_catalog(browser, provider, cat_b)
    assert header.sectionSize(_col(browser, "class")) != 222
    _open_catalog(browser, provider, cat_a)
    assert header.sectionSize(_col(browser, "class")) == 222


def test_columns_reset_forgets_dragged_widths(browser):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.event_table_view_state import get_view_state
    provider = DummyProvider(num_catalogs=1, events_per_catalog=3, name="WidthResetAll")
    cat = provider.catalogs()[0]
    _open_catalog(browser, provider, cat)
    header = browser._event_table.horizontalHeader()
    col = _col(browser, "class")
    header.resizeSection(col, 222)

    browser._on_columns_reset()

    assert header.sectionSize(col) != 222
    assert get_view_state(cat.uuid).column_widths == {}


def test_hiding_a_column_does_not_record_a_zero_width(browser):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    provider = DummyProvider(num_catalogs=1, events_per_catalog=3, name="WidthHide")
    cat = provider.catalogs()[0]
    _open_catalog(browser, provider, cat)
    browser._event_table.setColumnHidden(_col(browser, "class"), True)
    browser._save_view_state()
    from SciQLop.components.catalogs.backend.event_table_view_state import get_view_state
    assert "class" not in get_view_state(cat.uuid).column_widths
