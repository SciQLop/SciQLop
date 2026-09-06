"""set_events() is a full model reset, which used to silently drop the
table's selection on every incidental refresh -- an async load completing,
a peer's edit landing in a shared cocat catalog, or the browser's own
_on_add_event refreshing right after adding (2026-09-06 review).
"""
from PySide6.QtCore import QItemSelectionModel

from .fixtures import *


def _select_row(browser, row):
    sm = browser._event_table.selectionModel()
    sm.select(
        browser._sort_proxy.index(row, 0),
        QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
    )


def _selected_uuids(browser):
    sm = browser._event_table.selectionModel()
    uuids = set()
    for proxy_idx in sm.selectedRows():
        source_idx = browser._sort_proxy.mapToSource(proxy_idx)
        ev = browser._event_model.event_at(source_idx.row())
        if ev is not None:
            uuids.add(ev.uuid)
    return uuids


def test_events_changed_refresh_preserves_selection(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3, name="SelPreserveProv")
    cat = provider.catalogs()[0]
    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    browser._current_provider = provider
    browser._current_catalog = cat
    browser._event_model.set_context(provider, cat)
    browser._event_model.set_events(provider.events(cat))

    _select_row(browser, 1)
    selected_before = _selected_uuids(browser)
    assert len(selected_before) == 1

    # Simulate a peer's edit landing (events_changed for the same catalog,
    # unrelated to anything the local user did).
    browser._on_events_changed(cat)

    assert _selected_uuids(browser) == selected_before


def test_add_event_refresh_preserves_existing_selection(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3, name="SelPreserveAddProv")
    cat = provider.catalogs()[0]
    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    browser._current_provider = provider
    browser._current_catalog = cat
    browser._event_model.set_context(provider, cat)
    browser._event_model.set_events(provider.events(cat))

    _select_row(browser, 0)
    selected_before = _selected_uuids(browser)
    assert len(selected_before) == 1

    browser._on_add_event()

    assert selected_before <= _selected_uuids(browser)
