"""Provider hooks asked for by the cocat-rs plugin (2026-11-09): tooltips on every node,
folder rows that follow status_changed, capabilities_changed, notice, action tooltips.
Every hook defaults to the behaviour from before, so other providers see no change."""
from datetime import datetime, timedelta, timezone

from .fixtures import *


def _provider(**kw):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.provider import Capability, ProviderAction

    class Provider(DummyProvider):
        """A dummy that can turn read-only, describes its nodes and offers one action of each kind."""
        read_only = False

        def capabilities(self, catalog=None):
            return set() if self.read_only else super().capabilities(catalog)

        def node_tooltip(self, node_type, path=None, catalog=None):
            return f"{node_type.value}:{'/'.join(path or [])}:{catalog.name if catalog else ''}"

        def actions(self, catalog=None):
            return [ProviderAction("Act", lambda _: None, tooltip=f"on {catalog.name if catalog else 'provider'}")]

        def folder_actions(self, path):
            return [ProviderAction("Join", lambda _: None, tooltip="join it")]

    assert Capability.CREATE_CATALOGS in DummyProvider().capabilities()
    return Provider(**kw)


def _child(model, parent, predicate):
    from PySide6.QtCore import QModelIndex
    for row in range(model.rowCount(parent)):
        idx = model.index(row, 0, parent)
        if predicate(model.node_from_index(idx)):
            return idx
    return QModelIndex()


def _provider_index(model, provider):
    from PySide6.QtCore import QModelIndex
    return _child(model, QModelIndex(), lambda n: n.provider is provider)


def _tooltip(model, idx):
    from PySide6.QtCore import Qt
    return model.data(idx, Qt.ItemDataRole.ToolTipRole)


# ---- 1. tooltips on every node ----

def test_the_provider_gives_tooltips_on_folders_and_catalogues(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    provider = _provider(num_catalogs=1, events_per_catalog=0, paths=[["room"]])
    model = CatalogTreeModel()
    provider.folder_added.emit(["room"])
    prov = _provider_index(model, provider)
    folder = _child(model, prov, lambda n: n.name == "room")
    catalog = _child(model, folder, lambda n: n.catalog is not None)
    assert _tooltip(model, prov) == "provider::"
    assert _tooltip(model, folder) == "folder:room:"
    assert _tooltip(model, catalog) == "catalog::Catalog-0"


def test_without_the_hook_only_the_provider_row_has_a_tooltip(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, paths=[["room"]])
    provider._description = "a dummy"
    model = CatalogTreeModel()
    prov = _provider_index(model, provider)
    folder = _child(model, prov, lambda n: n.name == "room")
    assert _tooltip(model, prov) == "a dummy"
    assert _tooltip(model, folder) is None
    assert _tooltip(model, _child(model, folder, lambda n: n.catalog is not None)) is None


# ---- 2. status_changed repaints the provider's rows ----

def test_status_changed_repaints_the_provider_folder_rows(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    provider = _provider(num_catalogs=1, events_per_catalog=0, paths=[["room"]])
    model = CatalogTreeModel()
    provider.folder_added.emit(["room"])
    prov = _provider_index(model, provider)
    folder = _child(model, prov, lambda n: n.name == "room")
    repainted = []
    model.dataChanged.connect(lambda tl, br, roles: repainted.append((tl.parent(), tl.row(), br.row())))
    provider.status_changed.emit()
    assert any(parent == prov and first <= folder.row() <= last for parent, first, last in repainted)


# ---- 3. capabilities_changed ----

def _browser_on_first_catalog(qtbot, provider):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    browser = CatalogBrowser()
    model = browser._tree_model
    idx = _child(model, _provider_index(model, provider), lambda n: n.catalog is not None)
    browser._catalog_tree.setCurrentIndex(browser._proxy_model.mapFromSource(idx))
    return browser


def test_capabilities_changed_makes_the_open_event_table_read_only_and_keeps_it_open(qtbot, qapp):
    from PySide6.QtCore import Qt
    provider = _provider(num_catalogs=1, events_per_catalog=3)
    browser = _browser_on_first_catalog(qtbot, provider)
    table, events = browser._event_table, browser._event_model
    table.selectRow(1)
    cell = events.index(0, 0)
    assert events.flags(cell) & Qt.ItemFlag.ItemIsEditable
    resets = []
    events.modelReset.connect(lambda: resets.append(1))

    provider.read_only = True
    provider.capabilities_changed.emit(provider.catalogs()[0])

    assert not events.flags(cell) & Qt.ItemFlag.ItemIsEditable
    assert not browser._add_event_action.isVisible() and not browser._delete_action.isVisible()
    assert resets == [] and [i.row() for i in table.selectionModel().selectedRows()] == [1]


def test_capabilities_changed_for_all_catalogues_reaches_the_open_table(qtbot, qapp):
    from PySide6.QtCore import Qt
    provider = _provider(num_catalogs=1, events_per_catalog=1)
    browser = _browser_on_first_catalog(qtbot, provider)
    provider.read_only = True
    provider.capabilities_changed.emit(None)
    assert not browser._event_model.flags(browser._event_model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable


def test_capabilities_changed_updates_the_tree_creation_rows(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    provider = _provider(num_catalogs=1, events_per_catalog=0, paths=[["room"]])
    model = CatalogTreeModel()

    def placeholders():
        prov = _provider_index(model, provider)
        folder = _child(model, prov, lambda n: n.name == "room")
        return [model.node_from_index(model.index(r, 0, p)).is_placeholder
                for p in (prov, folder) for r in range(model.rowCount(p))].count(True)

    assert placeholders() == 4
    provider.read_only = True
    provider.capabilities_changed.emit(None)
    assert placeholders() == 0
    provider.read_only = False
    provider.capabilities_changed.emit(None)
    assert placeholders() == 4


def test_capabilities_changed_makes_overlays_read_only_in_edit_mode(qtbot, qapp):
    from SciQLop.components.catalogs.backend.panel_manager import InteractionMode, PanelCatalogManager
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange
    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())
    provider = _provider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    manager = PanelCatalogManager(panel)
    manager.add_catalog(cat)
    manager.mode = InteractionMode.EDIT
    assert manager._overlays[cat.uuid].read_only is False
    provider.read_only = True
    provider.capabilities_changed.emit(cat)
    assert manager._overlays[cat.uuid].read_only is True


# ---- 4. notice ----

def test_a_notice_reaches_the_browser_on_its_own_signal(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    provider = _provider(num_catalogs=0, events_per_catalog=0)
    browser = CatalogBrowser()
    later = _provider(num_catalogs=0, events_per_catalog=0)
    errors = []
    browser.provider_error.connect(errors.append)
    for p, text in ((provider, "offline: showing the last session"), (later, "3 catalogues moved")):
        with qtbot.waitSignal(browser.provider_notice, timeout=1000) as blocker:
            p.notice.emit(text)
        assert blocker.args == [text]
    assert errors == []


# ---- 5. action tooltips ----

def test_provider_catalogue_and_folder_actions_carry_their_tooltips(qtbot, qapp):
    provider = _provider(num_catalogs=1, events_per_catalog=0, paths=[["room"]])
    browser = _browser_on_first_catalog(qtbot, provider)
    provider.folder_added.emit(["room"])
    model = browser._tree_model
    prov = _provider_index(model, provider)
    folder = _child(model, prov, lambda n: n.name == "room")
    catalog = _child(model, folder, lambda n: n.catalog is not None)

    def tooltip(idx, name):
        menu = browser._build_tree_context_menu(browser._proxy_model.mapFromSource(idx))
        return next(a.toolTip() for a in menu.actions() if a.text() == name)

    assert tooltip(prov, "Act") == "on provider"
    assert tooltip(catalog, "Act") == "on Catalog-0"
    assert tooltip(folder, "Join") == "join it"


def test_an_action_without_tooltip_still_builds(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import ProviderAction
    assert ProviderAction("Connect", lambda _: None).tooltip is None
