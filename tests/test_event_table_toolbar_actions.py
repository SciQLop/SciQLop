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


def test_event_table_context_menu_has_delete_and_add_attribute(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser

    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    _load_provider(browser)
    _select_rows(browser, [0])

    menu = browser._build_event_context_menu()
    texts = [a.text() for a in menu.actions()]
    assert "Delete" in texts
    assert "+ Attribute" in texts


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
    assert "+ Attribute" not in texts


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
