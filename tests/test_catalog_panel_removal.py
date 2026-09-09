"""Removing a catalog from a panel used to require right-click -> Catalogs
-> provider -> every folder level -> uncheck (2026-09-07). Two shortcuts:
the panel's Catalogs menu lists the loaded ones first, flat; the tree's
context menu offers add/remove for the panel the user is working in.
"""
from .fixtures import *
import pytest
from datetime import datetime, timezone, timedelta


@pytest.fixture
def panel(qtbot, qapp):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange
    p = TimeSyncPanel("removal-panel")
    qtbot.addWidget(p)
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    p.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())
    return p


@pytest.fixture
def provider():
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    return DummyProvider(num_catalogs=2, events_per_catalog=2, name="RemovalProv")


def _catalogs_submenu(manager):
    from PySide6.QtWidgets import QMenu
    root = QMenu()
    # Keep the wrapper build_catalogs_menu returns: re-fetching the submenu
    # through QAction.menu() mints a wrapper Shiboken treats as Python-owned
    # (see test_catalog_color_by_menu._color_by_columns).
    return root, manager.build_catalogs_menu(root)


def _loaded_submenu(menu, catalog):
    from PySide6.QtWidgets import QMenu
    return menu.findChild(QMenu, f"loaded_catalog_{catalog.uuid}")


def _action(menu, prefix):
    for a in menu.actions():
        if a.text().startswith(prefix):
            return a
    return None


def test_panel_menu_lists_loaded_catalogs_first(panel, provider):
    cat_a, cat_b = provider.catalogs()
    manager = panel.catalog_manager
    manager.add_catalog(cat_b)

    root, menu = _catalogs_submenu(manager)
    first = menu.actions()[0]
    assert first.text() == cat_b.name
    assert not first.icon().isNull()
    assert _loaded_submenu(menu, cat_b) is not None
    assert menu.actions()[1].isSeparator()
    assert cat_a.name not in [a.text() for a in menu.actions()[:2]]


def test_loaded_entry_offers_removal_and_color_actions(panel, provider):
    from PySide6.QtWidgets import QMenu
    cat = provider.catalogs()[0]
    manager = panel.catalog_manager
    manager.add_catalog(cat)

    root, menu = _catalogs_submenu(manager)
    sub = _loaded_submenu(menu, cat)
    texts = [a.text() for a in sub.actions()]
    assert texts[0] == "Remove from panel"
    assert "Set color…" in texts
    assert sub.findChild(QMenu, "color_by_menu") is not None

    _action(sub, "Remove from panel").trigger()
    assert cat.uuid not in manager.catalog_uuids


def test_color_by_from_panel_menu_recolors_the_overlay(panel, provider, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR", str(tmp_path))
    from PySide6.QtWidgets import QMenu
    cat = provider.catalogs()[0]
    manager = panel.catalog_manager
    manager.add_catalog(cat)
    assert manager.overlay(cat.uuid)._mapper.column is None

    root, menu = _catalogs_submenu(manager)
    color_by = _loaded_submenu(menu, cat).findChild(QMenu, "color_by_menu")
    _action(color_by, "class").trigger()

    assert manager.overlay(cat.uuid)._mapper.column == "class"


def test_panel_menu_has_no_loaded_section_when_empty(panel, provider):
    root, menu = _catalogs_submenu(panel.catalog_manager)
    assert not menu.actions()[0].isSeparator()
    assert menu.actions()[0].menu() is not None


def _catalog_proxy_index(browser, catalog):
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


def test_tree_menu_toggles_catalog_on_the_working_panel(qtbot, panel, provider):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    cat = provider.catalogs()[0]
    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    browser.connect_to_panel(panel)
    idx = _catalog_proxy_index(browser, cat)

    add = _action(browser._build_tree_context_menu(idx), "Add to panel")
    assert add is not None and panel.windowTitle() in add.text()
    add.trigger()
    assert cat.uuid in panel.catalog_manager.catalog_uuids

    menu = browser._build_tree_context_menu(idx)
    assert _action(menu, "Add to panel") is None
    remove = _action(menu, "Remove from panel")
    assert remove is not None
    remove.trigger()
    assert cat.uuid not in panel.catalog_manager.catalog_uuids


def test_tree_menu_has_no_panel_entry_without_a_panel(qtbot, qapp, provider):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    menu = browser._build_tree_context_menu(_catalog_proxy_index(browser, provider.catalogs()[0]))
    assert _action(menu, "Add to panel") is None
    assert _action(menu, "Remove from panel") is None
