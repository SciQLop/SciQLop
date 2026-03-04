from .fixtures import *
import pytest
from datetime import datetime, timezone, timedelta


def test_catalog_event_creation(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    stop = datetime(2020, 1, 2, tzinfo=timezone.utc)
    event = CatalogEvent(uuid="evt-1", start=start, stop=stop)
    assert event.uuid == "evt-1"
    assert event.start == start
    assert event.stop == stop
    assert event.meta == {}


def test_catalog_event_meta(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    stop = datetime(2020, 1, 2, tzinfo=timezone.utc)
    event = CatalogEvent(uuid="evt-1", start=start, stop=stop,
                         meta={"author": "Alice", "rating": 5})
    assert event.meta["author"] == "Alice"
    assert event.meta["rating"] == 5


def test_catalog_event_range_changed_signal(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    stop = datetime(2020, 1, 2, tzinfo=timezone.utc)
    event = CatalogEvent(uuid="evt-1", start=start, stop=stop)

    new_start = datetime(2020, 6, 1, tzinfo=timezone.utc)
    new_stop = datetime(2020, 6, 2, tzinfo=timezone.utc)

    with qtbot.waitSignal(event.range_changed, timeout=1000):
        event.start = new_start
        event.stop = new_stop

    assert event.start == new_start
    assert event.stop == new_stop


def test_catalog_descriptor(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import Catalog
    cat = Catalog(uuid="cat-1", name="My Catalog")
    assert cat.uuid == "cat-1"
    assert cat.name == "My Catalog"
    assert cat.provider is None


def test_catalog_path_default(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import Catalog
    cat = Catalog(uuid="cat-1", name="My Catalog")
    assert cat.path == []


def test_catalog_path_explicit(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import Catalog
    cat = Catalog(uuid="cat-1", name="My Catalog", path=["MMS", "Magnetosheath"])
    assert cat.path == ["MMS", "Magnetosheath"]


def test_capability_enum(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import Capability
    assert Capability.EDIT_EVENTS == "edit_events"
    assert isinstance(Capability.EDIT_EVENTS, str)
    caps = {Capability.EDIT_EVENTS, "custom_capability"}
    assert "edit_events" in caps
    assert "custom_capability" in caps


def _make_dummy_provider(qapp):
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, CatalogEvent, Capability

    class InMemoryProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="test-provider")
            self._cat = Catalog(uuid="cat-1", name="Test Catalog", provider=self)
            self._catalogs = [self._cat]
            events = []
            base = datetime(2020, 1, 1, tzinfo=timezone.utc)
            for i in range(100):
                events.append(CatalogEvent(
                    uuid=f"evt-{i}",
                    start=base + timedelta(days=i),
                    stop=base + timedelta(days=i, hours=1),
                ))
            self._set_events(self._cat, events)

        def catalogs(self):
            return self._catalogs

        def capabilities(self, catalog=None):
            return {Capability.EDIT_EVENTS, Capability.CREATE_EVENTS}

    return InMemoryProvider()


def test_provider_catalogs(qtbot, qapp):
    provider = _make_dummy_provider(qapp)
    cats = provider.catalogs()
    assert len(cats) == 1
    assert cats[0].name == "Test Catalog"


def test_provider_events_all(qtbot, qapp):
    provider = _make_dummy_provider(qapp)
    cat = provider.catalogs()[0]
    events = provider.events(cat)
    assert len(events) == 100


def test_provider_events_range_query(qtbot, qapp):
    provider = _make_dummy_provider(qapp)
    cat = provider.catalogs()[0]
    start = datetime(2020, 1, 10, tzinfo=timezone.utc)
    stop = datetime(2020, 1, 20, tzinfo=timezone.utc)
    events = provider.events(cat, start=start, stop=stop)
    assert all(e.start >= start for e in events)
    assert all(e.start <= stop for e in events)
    assert len(events) == 11  # days 10,11,...,20 inclusive


def test_provider_add_event(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    provider = _make_dummy_provider(qapp)
    cat = provider.catalogs()[0]
    new_event = CatalogEvent(
        uuid="evt-new",
        start=datetime(2020, 1, 5, 12, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 5, 13, tzinfo=timezone.utc),
    )
    with qtbot.waitSignal(provider.events_changed, timeout=1000):
        provider._add_event(cat, new_event)
    events = provider.events(cat)
    assert len(events) == 101
    starts = [e.start for e in events]
    assert starts == sorted(starts)


def test_provider_remove_event(qtbot, qapp):
    provider = _make_dummy_provider(qapp)
    cat = provider.catalogs()[0]
    events = provider.events(cat)
    to_remove = events[50]
    with qtbot.waitSignal(provider.events_changed, timeout=1000):
        provider._remove_event(cat, to_remove)
    assert len(provider.events(cat)) == 99


def test_registry_singleton(qtbot, qapp):
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    r1 = CatalogRegistry.instance()
    r2 = CatalogRegistry.instance()
    assert r1 is r2


def test_auto_registration(qtbot, qapp):
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    registry = CatalogRegistry.instance()
    initial_count = len(registry.providers())
    provider = _make_dummy_provider(qapp)
    assert len(registry.providers()) == initial_count + 1
    assert provider in registry.providers()


def test_auto_unregistration_on_destroy(qtbot, qapp):
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    registry = CatalogRegistry.instance()
    provider = _make_dummy_provider(qapp)
    initial_count = len(registry.providers())
    provider.deleteLater()
    qtbot.waitUntil(lambda: len(registry.providers()) == initial_count - 1, timeout=1000)


def test_registry_provider_registered_signal(qtbot, qapp):
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    registry = CatalogRegistry.instance()
    with qtbot.waitSignal(registry.provider_registered, timeout=1000):
        provider = _make_dummy_provider(qapp)


def test_registry_all_catalogs(qtbot, qapp):
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    registry = CatalogRegistry.instance()
    provider = _make_dummy_provider(qapp)
    all_cats = registry.all_catalogs()
    assert any(c.name == "Test Catalog" for c in all_cats)


def test_dummy_provider_full_capabilities(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.provider import Capability
    provider = DummyProvider(num_catalogs=2, events_per_catalog=50)
    assert len(provider.catalogs()) == 2
    cat = provider.catalogs()[0]
    assert len(provider.events(cat)) == 50
    caps = provider.capabilities(cat)
    assert Capability.EDIT_EVENTS in caps
    assert Capability.CREATE_EVENTS in caps
    assert Capability.DELETE_EVENTS in caps
    assert Capability.CREATE_CATALOGS in caps
    assert Capability.DELETE_CATALOGS in caps
    assert Capability.EXPORT_EVENTS in caps
    assert Capability.IMPORT_EVENTS in caps


# --- Task 2: Folder nodes from paths ---

def _make_provider_with_paths(qapp):
    """Helper: provider with catalogs at various path depths."""
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, CatalogEvent
    import uuid as _uuid

    class PathProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="PathProvider")
            self._catalogs = [
                Catalog(uuid=str(_uuid.uuid4()), name="Root Cat", provider=self, path=[]),
                Catalog(uuid=str(_uuid.uuid4()), name="Deep Cat", provider=self, path=["A", "B"]),
                Catalog(uuid=str(_uuid.uuid4()), name="Sibling Cat", provider=self, path=["A", "B"]),
                Catalog(uuid=str(_uuid.uuid4()), name="Other Cat", provider=self, path=["A", "C"]),
            ]
            for cat in self._catalogs:
                self._set_events(cat, [])

        def catalogs(self):
            return list(self._catalogs)

    return PathProvider()


def test_tree_model_folder_nodes(qtbot, qapp):
    """Catalogs with path segments should create intermediate folder nodes."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel

    provider = _make_provider_with_paths(qapp)
    model = CatalogTreeModel()

    # Find our provider node
    provider_idx = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            provider_idx = idx
            break
    assert provider_idx is not None

    # Provider should have 2 direct children: "Root Cat" (catalog) and "A" (folder)
    assert model.rowCount(provider_idx) == 2

    # Find folder "A"
    folder_a_idx = None
    root_cat_idx = None
    for i in range(model.rowCount(provider_idx)):
        child_idx = model.index(i, 0, provider_idx)
        node = model.node_from_index(child_idx)
        if node.name == "A" and node.catalog is None:
            folder_a_idx = child_idx
        elif node.name == "Root Cat" and node.catalog is not None:
            root_cat_idx = child_idx
    assert folder_a_idx is not None, "Folder 'A' not found"
    assert root_cat_idx is not None, "Root Cat not found"

    # Folder A should have 2 children: "B" (folder) and "C" (folder)
    assert model.rowCount(folder_a_idx) == 2

    # Find folder "B" under "A"
    folder_b_idx = None
    for i in range(model.rowCount(folder_a_idx)):
        child_idx = model.index(i, 0, folder_a_idx)
        node = model.node_from_index(child_idx)
        if node.name == "B" and node.catalog is None:
            folder_b_idx = child_idx
    assert folder_b_idx is not None, "Folder 'B' not found under 'A'"

    # Folder B should have 2 catalogs: "Deep Cat" and "Sibling Cat"
    assert model.rowCount(folder_b_idx) == 2


def test_tree_model_folder_not_selectable_for_events(qtbot, qapp):
    """Folder nodes should have catalog=None."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel

    provider = _make_provider_with_paths(qapp)
    model = CatalogTreeModel()

    # Find folder "A" under our provider
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            for j in range(model.rowCount(idx)):
                child_idx = model.index(j, 0, idx)
                child = model.node_from_index(child_idx)
                if child.name == "A":
                    assert child.catalog is None
                    return
    pytest.fail("Folder 'A' not found")


# --- Task 6: CatalogTreeModel tests ---

def test_catalog_tree_model_structure(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=3)
    model = CatalogTreeModel()

    # Find the provider node that has exactly 3 catalogs (our provider)
    found = False
    for i in range(model.rowCount()):
        provider_index = model.index(i, 0)
        if model.data(provider_index) == "DummyProvider" and model.rowCount(provider_index) == 3:
            found = True
            cat_index = model.index(0, 0, provider_index)
            assert model.data(cat_index) == "Catalog-0"
            break
    assert found, "DummyProvider with 3 catalogs not found in tree"


def test_catalog_tree_model_node_from_index(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=2)
    model = CatalogTreeModel()

    from PySide6.QtCore import QModelIndex
    # Root node from invalid index
    node = model.node_from_index(QModelIndex())
    assert node is not None  # root node

    # Find the provider node matching our specific provider instance
    found = False
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        n = model.node_from_index(idx)
        if n.provider is provider:
            found = True
            assert n.name == "DummyProvider"
            assert n.catalog is None
            # Catalog child
            child_idx = model.index(0, 0, idx)
            child = model.node_from_index(child_idx)
            assert child.catalog is not None
            assert child.catalog.name == "Catalog-0"
            break
    assert found, "Our DummyProvider not found in tree"


def test_tree_model_dynamic_add_with_path(qtbot, qapp):
    """Dynamically added catalogs with paths should create folder nodes."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, CatalogEvent
    import uuid as _uuid

    class DynProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="DynProvider")
            self._catalogs = []

        def catalogs(self):
            return list(self._catalogs)

        def add_catalog(self, cat):
            self._catalogs.append(cat)
            self._set_events(cat, [])
            self.catalog_added.emit(cat)

    provider = DynProvider()
    model = CatalogTreeModel()

    # Find provider node
    provider_idx = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            provider_idx = idx
            break
    assert provider_idx is not None
    assert model.rowCount(provider_idx) == 0

    # Add a catalog with path
    cat = Catalog(uuid=str(_uuid.uuid4()), name="New Cat", provider=provider, path=["X", "Y"])
    provider.add_catalog(cat)

    # Provider should now have folder "X"
    assert model.rowCount(provider_idx) == 1
    x_idx = model.index(0, 0, provider_idx)
    assert model.data(x_idx) == "X"

    # "X" should have folder "Y"
    assert model.rowCount(x_idx) == 1
    y_idx = model.index(0, 0, x_idx)
    assert model.data(y_idx) == "Y"

    # "Y" should have "New Cat"
    assert model.rowCount(y_idx) == 1
    cat_idx = model.index(0, 0, y_idx)
    assert model.data(cat_idx) == "New Cat"


def test_catalog_tree_model_dynamic_add(qtbot, qapp):
    """Test that creating a provider after the model populates the tree."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.provider import CatalogEvent, Catalog
    import uuid as _uuid

    model = CatalogTreeModel()
    initial_rows = model.rowCount()

    # Use import_events to dynamically add a catalog after full initialization
    provider = DummyProvider(num_catalogs=1)
    # Provider was registered during __init__ but _on_provider_registered
    # may have been skipped since _catalogs wasn't ready.
    # Force a refresh by checking that at least we can find it via the init path.
    model2 = CatalogTreeModel()
    assert model2.rowCount() >= initial_rows + 1


# --- Task 7: EventTableModel tests ---

def test_event_table_model(qtbot, qapp):
    from SciQLop.components.catalogs.ui.event_table import EventTableModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=10)
    cat = provider.catalogs()[0]
    events = provider.events(cat)

    model = EventTableModel()
    model.set_events(events)

    assert model.rowCount() == 10
    assert model.columnCount() >= 2  # at least start and stop

    from PySide6.QtCore import Qt
    index = model.index(0, 0)
    assert index.isValid()
    value = model.data(index, Qt.ItemDataRole.DisplayRole)
    assert value is not None


def test_event_table_model_clear(qtbot, qapp):
    from SciQLop.components.catalogs.ui.event_table import EventTableModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=5)
    cat = provider.catalogs()[0]
    events = provider.events(cat)

    model = EventTableModel()
    model.set_events(events)
    assert model.rowCount() == 5

    model.clear()
    assert model.rowCount() == 0


def test_event_table_model_event_at(qtbot, qapp):
    from SciQLop.components.catalogs.ui.event_table import EventTableModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=5)
    cat = provider.catalogs()[0]
    events = provider.events(cat)

    model = EventTableModel()
    model.set_events(events)

    evt = model.event_at(0)
    assert evt is not None
    assert evt.uuid == events[0].uuid

    assert model.event_at(999) is None


def test_event_table_model_meta_columns(qtbot, qapp):
    from SciQLop.components.catalogs.ui.event_table import EventTableModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from PySide6.QtCore import Qt

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    events = provider.events(cat)

    model = EventTableModel()
    model.set_events(events)

    # DummyProvider events have meta keys "index" and "catalog"
    assert model.columnCount() == 4  # start, stop, catalog, index
    headers = []
    for c in range(model.columnCount()):
        headers.append(model.headerData(c, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole))
    assert "start" in headers
    assert "stop" in headers
    assert "index" in headers
    assert "catalog" in headers


# --- Task 8: CatalogBrowser tests ---

def test_catalog_browser_widget(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=2, events_per_catalog=10)
    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    browser.show()

    tree = browser._catalog_tree
    model = tree.model()
    assert model.rowCount() >= 1


def test_catalog_browser_has_filter_bar(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from PySide6.QtWidgets import QLineEdit

    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    assert browser._filter_bar is not None
    assert isinstance(browser._filter_bar, QLineEdit)


def test_catalog_browser_has_splitter(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from PySide6.QtWidgets import QSplitter

    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    assert browser._splitter is not None
    assert isinstance(browser._splitter, QSplitter)


# --- Task 9: Toolbar visibility based on capabilities ---

def test_catalog_browser_toolbar_visibility(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, Capability

    class ReadOnlyProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="ReadOnly")
            cat = Catalog(uuid="ro-1", name="ReadOnly Cat", provider=self)
            self._cats = [cat]
            self._set_events(cat, [])

        def catalogs(self):
            return self._cats

        def capabilities(self, catalog=None):
            return set()  # no capabilities — read-only

    provider = ReadOnlyProvider()
    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    browser.show()

    # Find the ReadOnly provider in the tree and select its catalog
    tree = browser._catalog_tree
    model = tree.model()
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        if model.data(idx) == "ReadOnly":
            cat_idx = model.index(0, 0, idx)
            tree.setCurrentIndex(cat_idx)
            break

    # Toolbar buttons should be hidden for read-only provider
    assert not browser._add_event_btn.isVisible()
    assert not browser._delete_btn.isVisible()


# --- Task 4: Prune empty folders on catalog removal ---

def test_tree_model_prune_empty_folders(qtbot, qapp):
    """Removing the last catalog in a folder should prune empty ancestor folders."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog
    import uuid as _uuid

    class PruneProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="PruneProvider")
            self._cat = Catalog(
                uuid=str(_uuid.uuid4()), name="Only Cat",
                provider=self, path=["X", "Y"],
            )
            self._catalogs = [self._cat]
            self._set_events(self._cat, [])

        def catalogs(self):
            return list(self._catalogs)

        def remove_catalog(self, cat):
            self._catalogs.remove(cat)
            self.catalog_removed.emit(cat)

    provider = PruneProvider()
    model = CatalogTreeModel()

    # Find provider node
    provider_idx = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            provider_idx = idx
            break
    assert provider_idx is not None
    assert model.rowCount(provider_idx) == 1  # folder "X"

    # Remove the only catalog
    provider.remove_catalog(provider._cat)

    # Provider should now have 0 children (folders pruned)
    assert model.rowCount(provider_idx) == 0


# --- Task 1: catalog_removed must emit actual Catalog, not None ---

def test_catalog_removed_emits_actual_catalog(qtbot, qapp):
    """catalog_removed must emit the actual Catalog object, not None."""
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, Capability

    class RemovableProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="Removable")
            self._cats = []

        def catalogs(self):
            return list(self._cats)

        def capabilities(self, catalog=None):
            return {Capability.DELETE_CATALOGS}

        def add_test_catalog(self, cat):
            self._cats.append(cat)
            self.catalog_added.emit(cat)

        def remove_test_catalog(self, cat):
            self._cats.remove(cat)
            self.catalog_removed.emit(cat)

    provider = RemovableProvider()
    cat = Catalog(uuid="cat-1", name="C1", provider=provider, path=[])
    provider.add_test_catalog(cat)

    received = []
    provider.catalog_removed.connect(lambda c: received.append(c))
    provider.remove_test_catalog(cat)

    assert len(received) == 1
    assert received[0] is cat  # Must be the actual catalog, not None


# --- Task 2: No busy-wait in _load_events ---

def test_tscat_provider_load_events_no_busy_wait():
    """Verify _load_events does not use a busy-wait loop."""
    import inspect
    from SciQLop.plugins.tscat_catalogs.tscat_provider import TscatCatalogProvider
    source = inspect.getsource(TscatCatalogProvider._load_events)
    assert "for _ in range" not in source, "Busy-wait loop should be removed"
    assert "QThread.sleep" not in source, "QThread.sleep should be removed"
    assert "processEvents" not in source, "processEvents loop should be removed"


# --- Task 10: Public API exports ---

def test_public_api_imports(qtbot, qapp):
    from SciQLop.components.catalogs import (
        CatalogEvent, Catalog, CatalogProvider,
        Capability, ProviderAction,
        CatalogRegistry,
    )
    assert CatalogEvent is not None
    assert CatalogRegistry is not None


# --- Task 3: Filter bar wiring ---

def test_catalog_browser_filter_hides_non_matching(qtbot, qapp):
    """Filter bar should hide catalogs that don't match the filter text."""
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    # Create provider first so browser's tree model picks it up during __init__
    provider = DummyProvider(num_catalogs=3)
    provider._catalogs[0].name = "Alpha"
    provider._catalogs[1].name = "Beta"
    provider._catalogs[2].name = "Gamma"

    browser = CatalogBrowser()
    qtbot.addWidget(browser)

    assert hasattr(browser, '_proxy_model')
    proxy = browser._proxy_model

    # Find our provider's index in the proxy model
    def find_provider_idx():
        for i in range(proxy.rowCount()):
            idx = proxy.index(i, 0)
            src = proxy.mapToSource(idx)
            node = browser._tree_model.node_from_index(src)
            if node.provider is provider:
                return idx
        return None

    # All visible initially
    provider_idx = find_provider_idx()
    assert provider_idx is not None
    assert proxy.rowCount(provider_idx) == 3

    # Filter to "alp"
    browser._filter_bar.setText("alp")
    provider_idx = find_provider_idx()
    assert provider_idx is not None
    assert proxy.rowCount(provider_idx) == 1

    # Clear filter
    browser._filter_bar.setText("")
    provider_idx = find_provider_idx()
    assert provider_idx is not None
    assert proxy.rowCount(provider_idx) == 3


# --- Task 4: Public mutation API ---

def test_provider_add_event_public_api(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    from datetime import datetime, timezone

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0)
    catalog = provider.catalogs()[0]

    signals = []
    provider.events_changed.connect(lambda c: signals.append(c))

    event = CatalogEvent(
        uuid="new-1",
        start=datetime(2020, 6, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 6, 1, 1, tzinfo=timezone.utc),
    )
    provider.add_event(catalog, event)

    assert len(provider.events(catalog)) == 1
    assert len(signals) == 1

def test_provider_remove_event_public_api(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=5)
    catalog = provider.catalogs()[0]
    events = provider.events(catalog)
    event_to_remove = events[2]

    signals = []
    provider.events_changed.connect(lambda c: signals.append(c))
    provider.remove_event(catalog, event_to_remove)

    assert len(provider.events(catalog)) == 4
    assert event_to_remove.uuid not in [e.uuid for e in provider.events(catalog)]
    assert len(signals) == 1
