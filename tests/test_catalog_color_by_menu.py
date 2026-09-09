"""'Color by…' menu must use the right-clicked catalog's own meta
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
        if a.text() == "Color by…":
            color_menu = a.menu()
            break
    return {a.text() for a in color_menu.actions()
            if a.text() not in ("Uniform (default)", "Configure colormap…")} - {""}


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


def test_color_by_menu_reports_instead_of_raising_on_provider_failure(qtbot, qapp, monkeypatch):
    """The fix above reads catalog.provider.events(catalog) -- a real
    backend call, unlike the old in-memory self._event_model._events read
    it replaced. A provider failure while building a right-click menu must
    not crash menu construction (opencode review of c7d5e682)."""
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, name="ColorByFailProv")
    cat = provider.catalogs()[0]
    browser = CatalogBrowser()
    qtbot.addWidget(browser)

    def _raise(*a, **k):
        raise RuntimeError("backend down")
    monkeypatch.setattr(provider, "events", _raise)

    cat_proxy_idx = _catalog_tree_index(browser, cat)
    with qtbot.waitSignal(browser.provider_error, timeout=1000) as blocker:
        menu = browser._build_tree_context_menu(cat_proxy_idx)  # must not raise
    assert "backend down" in blocker.args[0]

    # The menu itself stays usable -- just without a per-column list.
    color_menu = None
    for a in menu.actions():
        if a.text() == "Color by…":
            color_menu = a.menu()
            break
    assert color_menu is not None
    assert any(a.text() == "Uniform (default)" for a in color_menu.actions())


def _submenu(menu, object_name):
    # findChild, not QAction.menu(): the wrapper QAction.menu() returns is
    # invalidated as soon as the temporary list from menu.actions() that
    # held the action is freed (Shiboken parent policy), so it cannot be
    # returned from a helper.
    from PySide6.QtWidgets import QMenu
    return menu.findChild(QMenu, object_name)


def _color_by_menu(browser, catalog):
    # Keep the wrapper the builder returns: re-fetching a submenu through
    # QAction.menu() across a function boundary trips Shiboken's
    # "already deleted" guard (see _color_by_columns above).
    from PySide6.QtWidgets import QMenu
    root = QMenu(browser)
    return root, browser._build_color_by_menu(root, catalog)


@pytest.fixture
def colored_catalog(qtbot, qapp, tmp_path, monkeypatch):
    """A catalog with a numeric 'score' and a discrete 'class' column, opened
    in a browser, with an isolated settings dir."""
    monkeypatch.setattr(
        "SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR", str(tmp_path))
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    provider = DummyProvider(num_catalogs=1, events_per_catalog=5, name="ColorByCfg")
    cat = provider.catalogs()[0]
    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    return browser, cat


def test_numeric_column_offers_a_colormap_submenu(colored_catalog):
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    from SciQLop.components.catalogs.backend.color_mapper_storage import get_color_mapper
    browser, cat = colored_catalog
    browser._apply_color_mapper(cat, ColorMapper(column="score"))

    root, color_menu = _color_by_menu(browser, cat)
    cmap_menu = _submenu(color_menu, "colormap_menu")
    assert cmap_menu is not None
    checked = [a.text() for a in cmap_menu.actions() if a.isChecked()]
    assert checked == ["viridis"]
    assert "Category colors…" not in [a.text() for a in color_menu.actions()]

    plasma = next(a for a in cmap_menu.actions() if a.text() == "plasma")
    plasma.trigger()
    assert get_color_mapper(cat).colormap == "plasma"
    assert get_color_mapper(cat).column == "score"


def test_discrete_column_offers_category_colors_not_colormap(colored_catalog):
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    browser, cat = colored_catalog
    browser._apply_color_mapper(cat, ColorMapper(column="class"))

    root, color_menu = _color_by_menu(browser, cat)
    texts = [a.text() for a in color_menu.actions()]
    assert "Category colors…" in texts
    assert _submenu(color_menu, "colormap_menu") is None
    assert "Configure colormap…" not in texts


def test_uniform_offers_neither(colored_catalog):
    browser, cat = colored_catalog
    root, color_menu = _color_by_menu(browser, cat)
    texts = [a.text() for a in color_menu.actions()]
    assert "Category colors…" not in texts
    assert _submenu(color_menu, "colormap_menu") is None


def test_category_colors_dialog_result_is_stored_and_applied(colored_catalog, monkeypatch):
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    from SciQLop.components.catalogs.backend.color_mapper_storage import get_color_mapper
    from SciQLop.components.catalogs.ui import category_colors_dialog
    browser, cat = colored_catalog
    browser._apply_color_mapper(cat, ColorMapper(column="class"))

    seen = {}

    class FakeDialog:
        def __init__(self, categories, current, default_color, parent=None):
            seen["categories"] = categories
            seen["current"] = current
            assert default_color("x").isValid()

        def exec(self):
            return category_colors_dialog.CategoryColorsDialog.DialogCode.Accepted

        DialogCode = category_colors_dialog.CategoryColorsDialog.DialogCode
        category_colors = {"A": "#ff0000"}

    monkeypatch.setattr(category_colors_dialog, "CategoryColorsDialog", FakeDialog)
    root, color_menu = _color_by_menu(browser, cat)
    next(a for a in color_menu.actions() if a.text() == "Category colors…").trigger()

    assert seen["current"] == {}
    assert set(seen["categories"]) == {str(e.meta["class"]) for e in cat.provider.events(cat)}
    stored = get_color_mapper(cat)
    assert stored.column == "class"
    assert stored.category_colors == {"A": "#ff0000"}
