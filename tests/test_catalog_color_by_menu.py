"""'Color by...' menu must use the right-clicked catalog's own meta
columns, not whichever catalog happens to be open in the event table
(2026-09-06 review): right-click catalog B while A is loaded in the table
used to show A's columns in B's menu.
"""
from .fixtures import *


def _select_catalog(browser, catalog):
    from PySide6.QtCore import QModelIndex
    model = browser._tree_model
    for row in range(model.rowCount(QModelIndex())):
        prov_idx = model.index(row, 0, QModelIndex())
        node = model.node_from_index(prov_idx)
        if node.provider is catalog.provider:
            for crow in range(model.rowCount(prov_idx)):
                cat_idx = model.index(crow, 0, prov_idx)
                cat_node = model.node_from_index(cat_idx)
                if cat_node.catalog is catalog:
                    proxy_idx = browser._proxy_model.mapFromSource(cat_idx)
                    browser._catalog_tree.setCurrentIndex(proxy_idx)
                    return
    raise AssertionError("catalog node not found")


def _catalog_tree_index(browser, catalog):
    from PySide6.QtCore import QModelIndex
    model = browser._tree_model
    for row in range(model.rowCount(QModelIndex())):
        prov_idx = model.index(row, 0, QModelIndex())
        node = model.node_from_index(prov_idx)
        if node.provider is catalog.provider:
            for crow in range(model.rowCount(prov_idx)):
                cat_idx = model.index(crow, 0, prov_idx)
                if model.node_from_index(cat_idx).catalog is catalog:
                    return browser._proxy_model.mapFromSource(cat_idx)
    raise AssertionError("catalog node not found")


def _color_by_columns(menu):
    # A plain loop, not next(genexpr for ...): consuming a.menu() through a
    # generator expression's frame teardown has been observed to drop the
    # last live Python reference to the returned QMenu before use, tripping
    # Shiboken's "already deleted" guard on the very next call.
    color_menu = None
    for a in menu.actions():
        if a.text() == "Color by...":
            color_menu = a.menu()
            break
    return {a.text() for a in color_menu.actions()
            if a.text() not in ("Uniform (default)", "Configure colormap...")} - {""}


def test_color_by_menu_uses_the_right_clicked_catalogs_own_columns(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from datetime import datetime, timezone

    provider = DummyProvider(num_catalogs=2, events_per_catalog=0, name="ColorByProv")
    cat_a, cat_b = provider.catalogs()

    def _ev(uuid, meta):
        return CatalogEvent(
            uuid=uuid,
            start=datetime(2020, 1, 1, tzinfo=timezone.utc),
            stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
            meta=meta,
        )
    provider.add_event(cat_a, _ev("a1", {"alpha_only_column": 1}))
    provider.add_event(cat_b, _ev("b1", {"beta_only_column": 2}))

    browser = CatalogBrowser()
    qtbot.addWidget(browser)

    # Catalog A is the one currently open/selected in the event table...
    _select_catalog(browser, cat_a)
    assert browser._current_catalog is cat_a

    # ...but the user right-clicks catalog B in the tree.
    b_proxy_idx = _catalog_tree_index(browser, cat_b)
    menu = browser._build_tree_context_menu(b_proxy_idx)

    columns = _color_by_columns(menu)
    assert "beta_only_column" in columns
    assert "alpha_only_column" not in columns
