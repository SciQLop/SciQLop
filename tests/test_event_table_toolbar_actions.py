"""Event-table toolbar as QActions: keyboard Delete, right-click context
menu, and a confirmation before a multi-row delete (2026-09-06 review).

Before this: the event toolbar was a mix of QPushButton/QToolButton with no
shared QAction, so the table had zero keyboard access (Delete did nothing)
and zero right-click menu -- both present on the sibling catalog tree.
"""
from PySide6.QtCore import Qt, QItemSelectionModel
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QMessageBox

from .fixtures import *


def _select_rows(browser, rows):
    sm = browser._event_table.selectionModel()
    for row in rows:
        sm.select(
            browser._sort_proxy.index(row, 0),
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
        )


def _load_provider(browser, num_events=3):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    provider = DummyProvider(num_catalogs=1, events_per_catalog=num_events)
    cat = provider.catalogs()[0]
    browser._current_provider = provider
    browser._current_catalog = cat
    browser._event_model.set_context(provider, cat)
    browser._event_model.set_events(provider.events(cat))
    browser._update_toolbar()
    return provider, cat


def test_delete_action_is_wired_to_the_table_with_the_delete_shortcut(qtbot, qapp):
    """Real WM-level focus isn't available headless, so the shortcut's
    end-to-end key delivery can't be simulated portably here (same reason
    the sibling tree Delete shortcut has no keyClick test either). Check the
    two things that make it fire for real: the shortcut is bound, and the
    action is registered on the table so WidgetShortcut scoping applies to
    it specifically (not globally)."""
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser

    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    assert browser._delete_action.shortcut() == QKeySequence(QKeySequence.StandardKey.Delete)
    assert browser._delete_action.shortcutContext() == Qt.ShortcutContext.WidgetShortcut
    assert browser._delete_action in browser._event_table.actions()


def test_delete_action_trigger_deletes_single_selected_event_without_confirming(qtbot, qapp, monkeypatch):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser

    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    provider, cat = _load_provider(browser)
    _select_rows(browser, [0])

    asked = []
    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: asked.append(1) or QMessageBox.StandardButton.Yes)

    initial = len(provider.events(cat))
    browser._delete_action.trigger()

    assert len(provider.events(cat)) == initial - 1
    assert not asked, "a single-event delete must not ask for confirmation"


def test_delete_action_trigger_confirms_before_bulk_delete(qtbot, qapp, monkeypatch):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser

    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    provider, cat = _load_provider(browser)
    _select_rows(browser, [0, 1])

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)
    initial = len(provider.events(cat))
    browser._delete_action.trigger()
    assert len(provider.events(cat)) == initial, "declining the confirmation must not delete anything"

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes)
    browser._delete_action.trigger()
    assert len(provider.events(cat)) == initial - 2


def test_event_table_context_menu_offers_open_link_for_a_url_cell(qtbot, qapp, monkeypatch):
    """No metadata value in SciQLop's catalog event table was ever
    clickable (2026-09-06 review) -- a right-click "Open link" action on a
    URL-looking cell is the mechanism least likely to conflict with
    editing (unlike double-click, which already opens the cell editor)."""
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from datetime import datetime, timezone

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, name="UrlLinkProv")
    cat = provider.catalogs()[0]
    event = CatalogEvent(
        uuid="u1",
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
        meta={"reference": "https://example.org/report", "note": "not a link"},
    )
    provider.add_event(cat, event)

    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    browser._current_provider = provider
    browser._current_catalog = cat
    browser._event_model.set_context(provider, cat)
    browser._event_model.set_events(provider.events(cat))

    ref_col = len(browser._event_model._FIXED_COLUMNS) + browser._event_model._meta_keys.index("reference")
    note_col = len(browser._event_model._FIXED_COLUMNS) + browser._event_model._meta_keys.index("note")

    url_menu = browser._build_event_context_menu(url="https://example.org/report")
    assert any(a.text() == "Open link" for a in url_menu.actions())

    no_url_menu = browser._build_event_context_menu(url=None)
    assert not any(a.text() == "Open link" for a in no_url_menu.actions())

    ref_proxy_idx = browser._sort_proxy.mapFromSource(browser._event_model.index(0, ref_col))
    note_proxy_idx = browser._sort_proxy.mapFromSource(browser._event_model.index(0, note_col))
    assert browser._url_at(ref_proxy_idx) == "https://example.org/report"
    assert browser._url_at(note_proxy_idx) is None

    open_action = next(a for a in url_menu.actions() if a.text() == "Open link")
    opened = []
    from PySide6.QtGui import QDesktopServices
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toString()))
    open_action.trigger()
    assert opened == ["https://example.org/report"]


def test_on_event_table_context_menu_resolves_the_url_at_the_click_position(qtbot, qapp, monkeypatch):
    """Exercises the real slot's pos -> indexAt -> _url_at chain (opencode
    review: the narrower tests above call _build_event_context_menu and
    _url_at directly and wouldn't catch a regression in how the slot wires
    them together, e.g. indexAt(pos) not being used, or the wrong index
    passed through). _build_event_context_menu is a plain Python method,
    so monkeypatching it to return an empty QMenu short-circuits before
    .exec() -- no blocking modal, and no need to fake Qt's own event loop."""
    from PySide6.QtWidgets import QMenu
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from datetime import datetime, timezone

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, name="UrlPosProv")
    cat = provider.catalogs()[0]
    event = CatalogEvent(
        uuid="u1",
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
        meta={"reference": "https://example.org/report", "note": "not a link"},
    )
    provider.add_event(cat, event)

    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    browser._current_provider = provider
    browser._current_catalog = cat
    browser._event_model.set_context(provider, cat)
    browser._event_model.set_events(provider.events(cat))

    ref_col = len(browser._event_model._FIXED_COLUMNS) + browser._event_model._meta_keys.index("reference")
    note_col = len(browser._event_model._FIXED_COLUMNS) + browser._event_model._meta_keys.index("note")
    ref_pos = browser._event_table.visualRect(
        browser._sort_proxy.mapFromSource(browser._event_model.index(0, ref_col))).center()
    note_pos = browser._event_table.visualRect(
        browser._sort_proxy.mapFromSource(browser._event_model.index(0, note_col))).center()

    seen_urls = []
    monkeypatch.setattr(browser, "_build_event_context_menu",
                         lambda url=None: seen_urls.append(url) or QMenu(browser))

    browser._on_event_table_context_menu(ref_pos)
    browser._on_event_table_context_menu(note_pos)

    assert seen_urls == ["https://example.org/report", None]


def test_event_table_context_menu_has_delete_and_add_attribute(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser

    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    _load_provider(browser)
    _select_rows(browser, [0])

    menu = browser._build_event_context_menu()
    texts = [a.text() for a in menu.actions()]
    assert "Delete" in texts
    assert "Add attribute…" in texts


def test_event_table_context_menu_hides_actions_for_read_only_provider(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    class _ReadOnly(DummyProvider):
        def capabilities(self, catalog=None):
            return set()

    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    provider = _ReadOnly(num_catalogs=1, events_per_catalog=1)
    cat = provider.catalogs()[0]
    browser._current_provider = provider
    browser._current_catalog = cat
    browser._event_model.set_context(provider, cat)
    browser._event_model.set_events(provider.events(cat))
    browser._update_toolbar()

    menu = browser._build_event_context_menu()
    texts = [a.text() for a in menu.actions()]
    assert "Delete" not in texts
    assert "Add attribute…" not in texts


def test_columns_action_click_opens_popover_anchored_on_the_toolbar(qtbot, qapp):
    """_open_column_popover(at_header_pos=None) (the toolbar-button path, as
    opposed to right-clicking the header) needs a real QWidget to anchor on
    -- QAction itself has no mapToGlobal/rect. Regression check for the
    _columns_btn -> _columns_action rename."""
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser

    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    _load_provider(browser)

    browser._open_column_popover()  # must not raise


def test_actions_toolbutton_removed_in_favor_of_tree_context_menu(qtbot, qapp):
    """C13 review finding: the bottom 'Actions' button duplicated the tree's
    own provider-node context menu for every real provider (tscat/cocat both
    return [] from actions(catalog) for a non-None catalog) and was the only
    place to reach provider actions when a catalog -- rather than the
    provider node -- was selected. Removed; catalog-scoped actions are now
    also surfaced from the tree's own context menu (see the sibling test)."""
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser

    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    assert not hasattr(browser, "_actions_btn")
    assert not hasattr(browser, "_actions_menu")


def test_event_actions_hidden_when_selection_moves_off_the_catalog(qtbot, qapp):
    """opencode review finding #2: _update_toolbar only ever checked
    _current_provider is None, so switching from a catalog to its provider
    (or a folder) node left Delete/+Attribute/Add-Event visible -- and now
    that those same actions drive the table's right-click menu, an empty
    table would offer inert Delete/+Attribute entries."""
    from PySide6.QtCore import QModelIndex
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=1, name="ToggleProv")
    browser = CatalogBrowser()
    qtbot.addWidget(browser)

    model = browser._tree_model
    prov_source_idx = None
    for row in range(model.rowCount(QModelIndex())):
        idx = model.index(row, 0, QModelIndex())
        if model.node_from_index(idx).provider is provider:
            prov_source_idx = idx
            break
    assert prov_source_idx is not None
    cat_source_idx = model.index(0, 0, prov_source_idx)

    browser._catalog_tree.setCurrentIndex(browser._proxy_model.mapFromSource(cat_source_idx))
    assert browser._delete_action.isVisible()
    assert browser._add_attr_action.isVisible()

    browser._catalog_tree.setCurrentIndex(browser._proxy_model.mapFromSource(prov_source_idx))
    assert browser._current_catalog is None
    assert not browser._add_event_action.isVisible()
    assert not browser._delete_action.isVisible()
    assert not browser._add_attr_action.isVisible()

    menu = browser._build_event_context_menu()
    texts = [a.text() for a in menu.actions()]
    assert "Delete" not in texts
    assert "Add attribute…" not in texts


def test_tree_context_menu_shows_catalog_scoped_actions(qtbot, qapp):
    from PySide6.QtCore import QModelIndex
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.provider import ProviderAction

    class _WithCatalogActions(DummyProvider):
        def actions(self, catalog=None):
            if catalog is None:
                return []
            return [ProviderAction(name="Frobnicate", callback=lambda c: None)]

    # Provider must exist before the browser (and its tree model) are built --
    # CatalogProvider.__init__ registers with CatalogRegistry before the
    # subclass sets self._catalogs, so a CatalogTreeModel built in between
    # would miss it (catalog-system.md's documented registration-timing
    # pitfall).
    provider = _WithCatalogActions(num_catalogs=1, events_per_catalog=0, name="ActionProv")
    browser = CatalogBrowser()
    qtbot.addWidget(browser)

    model = browser._tree_model
    prov_node = model._provider_node(provider)
    cat_node = next(c for c in prov_node.children if c.catalog is not None)
    source_index = model.createIndex(cat_node.row(), 0, cat_node)
    proxy_index = browser._proxy_model.mapFromSource(source_index)

    menu = browser._build_tree_context_menu(proxy_index)
    texts = [a.text() for a in menu.actions()]
    assert "Frobnicate" in texts


def test_tree_context_menu_tolerates_actions_returning_none(qtbot, qapp):
    """opencode review finding #1: actions() is a provider extension point
    with no runtime-enforced contract; a provider returning None instead of
    [] (for either the provider-level or the catalog-scoped call) must not
    crash menu building."""
    from PySide6.QtCore import QModelIndex
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    class _NoneActions(DummyProvider):
        def actions(self, catalog=None):
            return None

    provider = _NoneActions(num_catalogs=1, events_per_catalog=0, name="NoneActionsProv")
    browser = CatalogBrowser()
    qtbot.addWidget(browser)

    model = browser._tree_model
    prov_node = model._provider_node(provider)
    prov_index = model.createIndex(prov_node.row(), 0, prov_node)
    prov_proxy = browser._proxy_model.mapFromSource(prov_index)
    browser._build_tree_context_menu(prov_proxy)  # must not raise

    cat_node = next(c for c in prov_node.children if c.catalog is not None)
    cat_index = model.createIndex(cat_node.row(), 0, cat_node)
    cat_proxy = browser._proxy_model.mapFromSource(cat_index)
    browser._build_tree_context_menu(cat_proxy)  # must not raise
