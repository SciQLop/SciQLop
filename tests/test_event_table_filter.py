"""Free-text filter on the event table (2026-09-06 review): the catalog
tree has one, the event table didn't, despite catalogs with thousands of
events being an explicitly documented perf case (AMDA shared catalogs,
ICME_multi_catalog).
"""
from datetime import datetime, timezone

from .fixtures import *


def _ev(uuid, meta):
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    return CatalogEvent(
        uuid=uuid,
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
        meta=meta,
    )


def test_event_sort_proxy_filters_across_all_columns(qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.event_table import EventTableModel, EventSortProxy

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, name="EvFilterProv")
    cat = provider.catalogs()[0]
    provider.add_event(cat, _ev("e1", {"class": "solar_wind"}))
    provider.add_event(cat, _ev("e2", {"class": "magnetosheath"}))

    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))
    proxy = EventSortProxy()
    proxy.setSourceModel(model)

    proxy.setFilterFixedString("solar")
    assert proxy.rowCount() == 1
    idx = proxy.index(0, len(model._FIXED_COLUMNS))
    assert proxy.data(idx) == "solar_wind"

    proxy.setFilterFixedString("")
    assert proxy.rowCount() == 2


def test_event_sort_proxy_filter_is_case_insensitive(qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.event_table import EventTableModel, EventSortProxy

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, name="EvFilterCaseProv")
    cat = provider.catalogs()[0]
    provider.add_event(cat, _ev("e1", {"class": "Solar_Wind"}))

    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))
    proxy = EventSortProxy()
    proxy.setSourceModel(model)

    proxy.setFilterFixedString("SOLAR")
    assert proxy.rowCount() == 1


def test_catalog_browser_has_event_filter_bar(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from PySide6.QtWidgets import QLineEdit

    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    assert isinstance(browser._event_filter_bar, QLineEdit)
    assert browser._event_filter_bar.isClearButtonEnabled()


def test_catalog_browser_event_filter_bar_filters_the_table(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, name="EvFilterUIProv")
    cat = provider.catalogs()[0]
    provider.add_event(cat, _ev("e1", {"class": "solar_wind"}))
    provider.add_event(cat, _ev("e2", {"class": "magnetosheath"}))

    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    browser._current_provider = provider
    browser._current_catalog = cat
    browser._event_model.set_context(provider, cat)
    browser._event_model.set_events(provider.events(cat))

    assert browser._sort_proxy.rowCount() == 2
    browser._event_filter_bar.setText("magneto")
    assert browser._sort_proxy.rowCount() == 1


def test_event_filter_bar_clears_when_switching_catalog(qtbot, qapp):
    """A filter left over from catalog A must not silently hide rows when
    switching to catalog B -- it looked like B just had fewer events."""
    from PySide6.QtCore import QModelIndex
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=2, events_per_catalog=1, name="EvFilterSwitchProv")
    cat_a, cat_b = provider.catalogs()

    browser = CatalogBrowser()
    qtbot.addWidget(browser)

    model = browser._tree_model
    prov_idx = None
    for row in range(model.rowCount(QModelIndex())):
        idx = model.index(row, 0, QModelIndex())
        if model.node_from_index(idx).provider is provider:
            prov_idx = idx
            break
    assert prov_idx is not None

    for row in range(model.rowCount(prov_idx)):
        cat_idx = model.index(row, 0, prov_idx)
        node = model.node_from_index(cat_idx)
        if node.catalog is cat_a:
            browser._catalog_tree.setCurrentIndex(browser._proxy_model.mapFromSource(cat_idx))
            break
    assert browser._current_catalog is cat_a

    browser._event_filter_bar.setText("nonexistent-text")
    assert browser._sort_proxy.rowCount() == 0

    for row in range(model.rowCount(prov_idx)):
        cat_idx = model.index(row, 0, prov_idx)
        node = model.node_from_index(cat_idx)
        if node.catalog is cat_b:
            browser._catalog_tree.setCurrentIndex(browser._proxy_model.mapFromSource(cat_idx))
            break

    assert browser._event_filter_bar.text() == ""
    assert browser._sort_proxy.rowCount() == 1
