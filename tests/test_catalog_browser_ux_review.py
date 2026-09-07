"""Catalog browser fixes from the 2026-09-07 UX review: filter boxes broke
on any non-alphanumeric character, Enter on "Delete Catalog?" destroyed the
catalog, column Reset ignored order and left the popover stale, Rename was
double-click-only, and "Color by..." only sampled the first 200 events.
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


def _catalog_tree_index(browser, catalog):
    from PySide6.QtCore import QModelIndex
    model = browser._tree_model
    for row in range(model.rowCount(QModelIndex())):
        prov_idx = model.index(row, 0, QModelIndex())
        if model.node_from_index(prov_idx).provider is catalog.provider:
            for crow in range(model.rowCount(prov_idx)):
                cat_idx = model.index(crow, 0, prov_idx)
                if model.node_from_index(cat_idx).catalog is catalog:
                    return browser._proxy_model.mapFromSource(cat_idx)
    raise AssertionError("catalog node not found")


def _select_catalog(browser, catalog):
    browser._catalog_tree.setCurrentIndex(_catalog_tree_index(browser, catalog))
    assert browser._current_catalog is catalog


def _menu_action(menu, text):
    # Plain loop, not next(genexpr): see test_catalog_color_by_menu.py.
    for a in menu.actions():
        if a.text() == text:
            return a
    return None


def _browser_with(qtbot, provider):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    return browser


# ---- 1. filter boxes vs. non-alphanumeric characters ----

def test_tree_filter_matches_names_with_punctuation(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=0, events_per_catalog=0, name="TreeFilterProv")
    provider.create_catalog("mms 1 2024-01")
    provider.create_catalog("other")
    browser = _browser_with(qtbot, provider)

    browser._filter_bar.setText("2024-01")
    assert browser._proxy_model.rowCount() >= 1
    prov_proxy = None
    for row in range(browser._proxy_model.rowCount()):
        idx = browser._proxy_model.index(row, 0)
        if browser._tree_model.node_from_index(
                browser._proxy_model.mapToSource(idx)).provider is provider:
            prov_proxy = idx
    assert prov_proxy is not None, "provider node dropped by the filter"
    names = [browser._proxy_model.index(r, 0, prov_proxy).data()
             for r in range(browser._proxy_model.rowCount(prov_proxy))]
    assert names == ["mms 1 2024-01"]

    browser._filter_bar.setText("MMS 1")
    names = [browser._proxy_model.index(r, 0, prov_proxy).data()
             for r in range(browser._proxy_model.rowCount(prov_proxy))]
    assert names == ["mms 1 2024-01"]


def test_event_filter_matches_text_with_punctuation(qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.event_table import EventTableModel, EventSortProxy

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, name="EvPunctProv")
    cat = provider.catalogs()[0]
    provider.add_event(cat, _ev("e1", {"tag": "mms 1 / 2024-01"}))
    provider.add_event(cat, _ev("e2", {"tag": "cluster"}))

    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))
    proxy = EventSortProxy()
    proxy.setSourceModel(model)

    proxy.setFilterFixedString("2024-01")
    assert proxy.rowCount() == 1
    proxy.setFilterFixedString("MMS 1")
    assert proxy.rowCount() == 1


# ---- 4. Delete Catalog? must default to No ----

def test_delete_catalog_confirmation_defaults_to_no(qtbot, qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, name="DelDefaultProv")
    cat = provider.catalogs()[0]
    browser = _browser_with(qtbot, provider)

    seen = {}

    def spy(*args, **kwargs):
        seen["default"] = kwargs.get("defaultButton", args[4] if len(args) > 4 else None)
        return QMessageBox.StandardButton.No
    monkeypatch.setattr(QMessageBox, "question", staticmethod(spy))

    node = browser._tree_model.node_from_index(
        browser._proxy_model.mapToSource(_catalog_tree_index(browser, cat)))
    browser._delete_catalog(node)
    assert seen["default"] == QMessageBox.StandardButton.No
    assert cat in provider.catalogs()


# ---- 5. column Reset restores order and refreshes the popover ----

def test_columns_reset_restores_natural_order_and_closes_popover(qtbot, qapp):
    from PySide6.QtCore import QPoint
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.column_visibility_popover import ColumnVisibilityPopover

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, name="ColResetProv")
    cat = provider.catalogs()[0]
    provider.add_event(cat, _ev("e1", {"alpha": 1, "beta": 2}))
    browser = _browser_with(qtbot, provider)
    _select_catalog(browser, cat)

    browser._reorder_columns(["start", "stop", "beta", "alpha"])
    browser._on_column_visibility_changed("alpha", False)
    header = browser._event_table.horizontalHeader()
    assert [header.logicalIndex(v) for v in range(4)] == [0, 1, 3, 2]

    browser._open_column_popover(at_header_pos=QPoint(0, 0))
    popover = browser.findChildren(ColumnVisibilityPopover)[0]
    popover._reset_btn.click()

    assert [header.logicalIndex(v) for v in range(4)] == [0, 1, 2, 3]
    assert not any(browser._event_table.isColumnHidden(c) for c in range(4))
    assert not popover.isVisible()


# ---- 8. Rename in the tree context menu ----

def test_tree_context_menu_offers_rename_when_capable(qtbot, qapp):
    from PySide6.QtWidgets import QAbstractItemView
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, name="RenameMenuProv")
    cat = provider.catalogs()[0]
    browser = _browser_with(qtbot, provider)
    browser.show()
    browser._catalog_tree.expandAll()

    proxy_idx = _catalog_tree_index(browser, cat)
    menu = browser._build_tree_context_menu(proxy_idx)
    rename = _menu_action(menu, "Rename")
    assert rename is not None
    rename.trigger()
    assert browser._catalog_tree.state() == QAbstractItemView.State.EditingState


def test_tree_context_menu_hides_rename_without_capability(qtbot, qapp, monkeypatch):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.provider import Capability

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, name="NoRenameProv")
    cat = provider.catalogs()[0]
    full = provider.capabilities()
    monkeypatch.setattr(provider, "capabilities",
                        lambda catalog=None: full - {Capability.RENAME_CATALOG})
    browser = _browser_with(qtbot, provider)

    menu = browser._build_tree_context_menu(_catalog_tree_index(browser, cat))
    assert _menu_action(menu, "Rename") is None
    assert _menu_action(menu, "Delete Catalog") is not None


# ---- 7. "Color by..." sees every column of the open catalog ----

def test_color_by_menu_lists_columns_beyond_the_first_200_events(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, name="ColorByLateProv")
    cat = provider.catalogs()[0]
    for i in range(200):
        provider.add_event(cat, _ev(f"e{i}", {"early": i}))
    provider.add_event(cat, _ev("late", {"late_column": 1}))
    browser = _browser_with(qtbot, provider)
    _select_catalog(browser, cat)

    menu = browser._build_tree_context_menu(_catalog_tree_index(browser, cat))
    color_action = _menu_action(menu, "Color by...")
    color_menu = color_action.menu()
    assert "late_column" in {a.text() for a in color_menu.actions()}
