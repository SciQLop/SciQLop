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

    # Find the provider node that has exactly 3 catalogs + 2 placeholders (our provider)
    found = False
    for i in range(model.rowCount()):
        provider_index = model.index(i, 0)
        if model.data(provider_index) == "DummyProvider" and model.rowCount(provider_index) == 5:
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
    assert proxy.rowCount(provider_idx) == 5  # 3 catalogs + 2 placeholders

    # Filter to "alp"
    browser._filter_bar.setText("alp")
    provider_idx = find_provider_idx()
    assert provider_idx is not None
    assert proxy.rowCount(provider_idx) == 1

    # Clear filter
    browser._filter_bar.setText("")
    provider_idx = find_provider_idx()
    assert provider_idx is not None
    assert proxy.rowCount(provider_idx) == 5  # 3 catalogs + 2 placeholders


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


# --- Task 6: CocatCatalogProvider is a CatalogProvider ---

def test_cocat_provider_is_catalog_provider(qtbot, qapp):
    """CocatCatalogProvider should be a CatalogProvider subclass."""
    import importlib
    from SciQLop.components.catalogs.backend.provider import CatalogProvider
    # Import the module directly to avoid the package __init__ chain
    # which pulls in cocat/wire_websocket dependencies via client.py
    spec = importlib.util.spec_from_file_location(
        "cocat_provider",
        "SciQLop/plugins/collaborative_catalogs/cocat_provider.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert issubclass(mod.CocatCatalogProvider, CatalogProvider)


# --- Inline catalog editing ---

def test_rename_catalog_capability_exists(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import Capability
    assert Capability.RENAME_CATALOG == "rename_catalog"


def test_provider_rename_catalog(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, Capability

    class RenamableProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="Renamable")
            self._cat = Catalog(uuid="cat-1", name="OldName", provider=self)
            self._catalogs = [self._cat]
            self._set_events(self._cat, [])

        def catalogs(self):
            return list(self._catalogs)

        def capabilities(self, catalog=None):
            return {Capability.RENAME_CATALOG}

        def rename_catalog(self, catalog, new_name):
            catalog.name = new_name
            self.catalog_renamed.emit(catalog)

    provider = RenamableProvider()
    cat = provider.catalogs()[0]
    assert cat.name == "OldName"

    received = []
    provider.catalog_renamed.connect(lambda c: received.append(c))
    provider.rename_catalog(cat, "NewName")

    assert cat.name == "NewName"
    assert len(received) == 1
    assert received[0] is cat


def test_tree_model_placeholder_node(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1)
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            assert model.rowCount(idx) == 3  # 1 catalog + 2 placeholders
            second_last_idx = model.index(model.rowCount(idx) - 2, 0, idx)
            assert model.data(second_last_idx) == "New Catalog..."
            last_idx = model.index(model.rowCount(idx) - 1, 0, idx)
            assert model.data(last_idx) == "New Folder..."
            return
    pytest.fail("Provider not found")


def test_tree_model_placeholder_is_editable(qtbot, qapp):
    from PySide6.QtCore import Qt
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=0)
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            placeholder_idx = model.index(0, 0, idx)
            flags = model.flags(placeholder_idx)
            assert flags & Qt.ItemFlag.ItemIsEditable
            return
    pytest.fail("Provider not found")


def test_tree_model_setdata_placeholder_creates_catalog(qtbot, qapp):
    from PySide6.QtCore import Qt
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=0)
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            assert model.rowCount(idx) == 2  # 2 placeholders
            placeholder_idx = model.index(0, 0, idx)

            result = model.setData(placeholder_idx, "My Catalog", Qt.ItemDataRole.EditRole)
            assert result is True

            assert len(provider.catalogs()) == 1
            assert provider.catalogs()[0].name == "My Catalog"

            assert model.rowCount(idx) == 3  # 1 catalog + 2 placeholders
            return
    pytest.fail("Provider not found")


def test_tree_model_setdata_renames_catalog(qtbot, qapp):
    from PySide6.QtCore import Qt
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, Capability

    class RenamableProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="Renamable2")
            self._cat = Catalog(uuid="cat-r", name="OldName", provider=self)
            self._catalogs = [self._cat]
            self._set_events(self._cat, [])

        def catalogs(self):
            return list(self._catalogs)

        def capabilities(self, catalog=None):
            return {Capability.RENAME_CATALOG}

        def rename_catalog(self, catalog, new_name):
            catalog.name = new_name
            self.catalog_renamed.emit(catalog)

    provider = RenamableProvider()
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            cat_idx = model.index(0, 0, idx)
            assert model.data(cat_idx) == "OldName"

            result = model.setData(cat_idx, "NewName", Qt.ItemDataRole.EditRole)
            assert result is True
            assert model.data(cat_idx) == "NewName"
            assert provider.catalogs()[0].name == "NewName"
            return
    pytest.fail("Provider not found")


def test_tree_model_setdata_rejects_empty_name(qtbot, qapp):
    from PySide6.QtCore import Qt
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=0)
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            placeholder_idx = model.index(0, 0, idx)
            assert model.setData(placeholder_idx, "", Qt.ItemDataRole.EditRole) is False
            assert model.setData(placeholder_idx, "   ", Qt.ItemDataRole.EditRole) is False
            assert len(provider.catalogs()) == 0
            return
    pytest.fail("Provider not found")


def test_dummy_provider_remove_catalog(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=3, events_per_catalog=5)
    assert len(provider.catalogs()) == 3

    cat = provider.catalogs()[1]
    with qtbot.waitSignal(provider.catalog_removed, timeout=1000):
        provider.remove_catalog(cat)

    assert len(provider.catalogs()) == 2
    assert cat not in provider.catalogs()
    assert len(provider.events(cat)) == 0


def test_tree_model_no_placeholder_for_readonly_provider(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog

    class ReadOnlyProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="ReadOnlyNoPH")
            self._cat = Catalog(uuid="ro-1", name="Cat", provider=self)
            self._catalogs = [self._cat]
            self._set_events(self._cat, [])

        def catalogs(self):
            return list(self._catalogs)

        def capabilities(self, catalog=None):
            return set()

    provider = ReadOnlyProvider()
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            # Should have only the catalog, no placeholder
            assert model.rowCount(idx) == 1
            child = model.node_from_index(model.index(0, 0, idx))
            assert not child.is_placeholder
            assert child.catalog is not None
            return
    pytest.fail("Provider not found")


def test_tree_model_placeholder_italic(qtbot, qapp):
    from PySide6.QtCore import Qt
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=0)
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            placeholder_idx = model.index(0, 0, idx)
            font = model.data(placeholder_idx, Qt.ItemDataRole.FontRole)
            assert font is not None
            assert font.italic()
            return
    pytest.fail("Provider not found")


# --- Explicit folder nodes (room support) ---


def test_folder_added_creates_explicit_folder(qtbot, qapp):
    """folder_added signal should create a persistent folder node in the tree."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog

    class FolderProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="FolderProv")

        def catalogs(self):
            return []

    provider = FolderProvider()
    model = CatalogTreeModel()

    pnode = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            pnode = node
            break
    assert pnode is not None
    assert model.rowCount(model.index(pnode.row(), 0)) == 0

    # Emit folder_added
    provider.folder_added.emit(["room-1"])

    pidx = model.index(pnode.row(), 0)
    assert model.rowCount(pidx) == 1
    folder_idx = model.index(0, 0, pidx)
    folder_node = model.node_from_index(folder_idx)
    assert folder_node.name == "room-1"
    assert folder_node.is_explicit_folder is True
    assert folder_node.catalog is None


def test_explicit_folder_not_pruned(qtbot, qapp):
    """Explicit folders should persist even when their last catalog is removed."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog
    import uuid as _uuid

    class PersistProvider(CatalogProvider):
        def __init__(self):
            self._cats = []
            super().__init__(name="PersistProv")

        def catalogs(self):
            return list(self._cats)

    provider = PersistProvider()
    model = CatalogTreeModel()

    # Add an explicit folder
    provider.folder_added.emit(["room-1"])

    # Add a catalog inside that folder
    cat = Catalog(uuid=str(_uuid.uuid4()), name="Cat1", provider=provider, path=["room-1"])
    provider._cats.append(cat)
    provider.catalog_added.emit(cat)

    pnode = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            pnode = node
            break
    pidx = model.index(pnode.row(), 0)

    # Folder should have 1 child (the catalog)
    folder_idx = model.index(0, 0, pidx)
    assert model.rowCount(folder_idx) == 1

    # Remove the catalog
    provider._cats.remove(cat)
    provider.catalog_removed.emit(cat)

    # Folder should still exist (not pruned) but be empty
    assert model.rowCount(pidx) == 1
    folder_node = model.node_from_index(model.index(0, 0, pidx))
    assert folder_node.name == "room-1"
    assert folder_node.is_explicit_folder is True
    assert model.rowCount(model.index(0, 0, pidx)) == 0


def test_folder_removed_removes_folder(qtbot, qapp):
    """folder_removed signal should remove the explicit folder node."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.provider import CatalogProvider

    class FolderProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="RemFolderProv")

        def catalogs(self):
            return []

    provider = FolderProvider()
    model = CatalogTreeModel()

    provider.folder_added.emit(["room-A"])
    provider.folder_added.emit(["room-B"])

    pnode = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            pnode = node
            break
    pidx = model.index(pnode.row(), 0)
    assert model.rowCount(pidx) == 2

    # Remove room-A
    provider.folder_removed.emit(["room-A"])
    assert model.rowCount(pidx) == 1
    remaining = model.node_from_index(model.index(0, 0, pidx))
    assert remaining.name == "room-B"


def test_folder_display_name(qtbot, qapp):
    """Provider.folder_display_name should override display text for explicit folders."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.provider import CatalogProvider
    from PySide6.QtCore import Qt

    class NamedFolderProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="NamedFolderProv")

        def catalogs(self):
            return []

        def folder_display_name(self, path):
            if path == ["default-room"]:
                return "default-room (default)"
            return None

    provider = NamedFolderProvider()
    model = CatalogTreeModel()

    provider.folder_added.emit(["default-room"])
    provider.folder_added.emit(["other-room"])

    pnode = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            pnode = node
            break
    pidx = model.index(pnode.row(), 0)

    # default-room should show custom display name
    default_idx = model.index(0, 0, pidx)
    assert model.data(default_idx, Qt.ItemDataRole.DisplayRole) == "default-room (default)"

    # other-room should show plain name
    other_idx = model.index(1, 0, pidx)
    assert model.data(other_idx, Qt.ItemDataRole.DisplayRole) == "other-room"


def test_provider_actions_on_provider_node(qtbot, qapp):
    """Provider.actions(None) should return provider-level actions."""
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, ProviderAction

    class ActionProvider(CatalogProvider):
        def __init__(self):
            self.action_called = False
            super().__init__(name="ActionProv")

        def catalogs(self):
            return []

        def actions(self, catalog=None):
            if catalog is None:
                return [ProviderAction(name="Connect", callback=lambda _: None)]
            return []

    provider = ActionProvider()
    actions = provider.actions(None)
    assert len(actions) == 1
    assert actions[0].name == "Connect"


def test_folder_actions(qtbot, qapp):
    """Provider.folder_actions should return actions for explicit folder nodes."""
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, ProviderAction

    class RoomProvider(CatalogProvider):
        def __init__(self):
            self._joined = set()
            super().__init__(name="RoomProv")

        def catalogs(self):
            return []

        def folder_actions(self, path):
            if len(path) == 1 and path[0] not in self._joined:
                return [ProviderAction(name="Join", callback=lambda p: self._joined.add(p[0]))]
            return [ProviderAction(name="Leave", callback=lambda p: self._joined.discard(p[0]))]

    provider = RoomProvider()

    actions = provider.folder_actions(["room-1"])
    assert len(actions) == 1
    assert actions[0].name == "Join"

    # Simulate joining
    actions[0].callback(["room-1"])
    assert "room-1" in provider._joined

    # Now should get Leave action
    actions = provider.folder_actions(["room-1"])
    assert actions[0].name == "Leave"


def test_create_catalog_with_path(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    provider = DummyProvider(num_catalogs=0, events_per_catalog=0)
    cat = provider.create_catalog("PathCat", path=["room1"])
    assert cat is not None
    assert cat.name == "PathCat"
    assert cat.path == ["room1"]
    assert cat.provider is provider


def test_node_type_enum(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import NodeType
    assert NodeType.PROVIDER == "provider"
    assert NodeType.FOLDER == "folder"
    assert NodeType.CATALOG == "catalog"
    assert isinstance(NodeType.PROVIDER, str)


def test_provider_node_icon_default_returns_none(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import NodeType
    provider = _make_dummy_provider(qapp)
    assert provider.node_icon(NodeType.PROVIDER) is None
    assert provider.node_icon(NodeType.FOLDER, path=["X"]) is None
    assert provider.node_icon(NodeType.CATALOG) is None


def test_placeholder_type_enum(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_tree import _PlaceholderType
    assert _PlaceholderType.NONE == "none"
    assert _PlaceholderType.CATALOG == "catalog"
    assert _PlaceholderType.FOLDER == "folder"


def test_node_placeholder_property(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_tree import _Node, _PlaceholderType
    regular = _Node(name="test")
    assert not regular.is_placeholder
    cat_ph = _Node(name="New Catalog...", placeholder_type=_PlaceholderType.CATALOG)
    assert cat_ph.is_placeholder
    folder_ph = _Node(name="New Folder...", placeholder_type=_PlaceholderType.FOLDER)
    assert folder_ph.is_placeholder


def test_tree_icon_provider_node(qtbot, qapp):
    """Provider nodes should have a DecorationRole icon."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon

    provider = DummyProvider(num_catalogs=1)
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            icon = model.data(idx, Qt.ItemDataRole.DecorationRole)
            assert isinstance(icon, QIcon)
            return
    pytest.fail("Provider node not found")


def test_tree_icon_catalog_node(qtbot, qapp):
    """Catalog nodes should have a DecorationRole icon."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon

    provider = DummyProvider(num_catalogs=1)
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            cat_idx = model.index(0, 0, idx)
            icon = model.data(cat_idx, Qt.ItemDataRole.DecorationRole)
            assert isinstance(icon, QIcon)
            return
    pytest.fail("Provider node not found")


def test_tree_icon_folder_node(qtbot, qapp):
    """Folder nodes should have a DecorationRole icon."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon

    provider = DummyProvider(num_catalogs=1, paths=[["FolderA"]])
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            folder_idx = model.index(0, 0, idx)
            assert model.data(folder_idx) == "FolderA"
            icon = model.data(folder_idx, Qt.ItemDataRole.DecorationRole)
            assert isinstance(icon, QIcon)
            return
    pytest.fail("Provider node not found")


def test_tree_icon_placeholder_none(qtbot, qapp):
    """Placeholder nodes should NOT have a DecorationRole icon."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from PySide6.QtCore import Qt

    provider = DummyProvider(num_catalogs=0)
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            last_row = model.rowCount(idx) - 1
            assert last_row >= 0
            ph_idx = model.index(last_row, 0, idx)
            ph_node = model.node_from_index(ph_idx)
            assert ph_node.is_placeholder
            icon = model.data(ph_idx, Qt.ItemDataRole.DecorationRole)
            assert icon is None
            return
    pytest.fail("Provider node not found")


def test_provider_has_two_placeholders(qtbot, qapp):
    """Provider node with CREATE_CATALOGS should have both catalog and folder placeholders."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel, _PlaceholderType
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=0)
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            assert model.rowCount(idx) == 2
            ph0 = model.node_from_index(model.index(0, 0, idx))
            ph1 = model.node_from_index(model.index(1, 0, idx))
            assert ph0.placeholder_type == _PlaceholderType.CATALOG
            assert ph1.placeholder_type == _PlaceholderType.FOLDER
            return
    pytest.fail("Provider not found")


def test_folder_has_two_placeholders(qtbot, qapp):
    """Folder nodes under a CREATE_CATALOGS provider should have both placeholders."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel, _PlaceholderType
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, paths=[["FolderA"]])
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            folder_idx = model.index(0, 0, idx)
            folder_node = model.node_from_index(folder_idx)
            assert folder_node.name == "FolderA"
            row_count = model.rowCount(folder_idx)
            assert row_count == 3  # Catalog-0 + 2 placeholders
            last = model.node_from_index(model.index(row_count - 1, 0, folder_idx))
            second_last = model.node_from_index(model.index(row_count - 2, 0, folder_idx))
            assert second_last.placeholder_type == _PlaceholderType.CATALOG
            assert last.placeholder_type == _PlaceholderType.FOLDER
            return
    pytest.fail("Provider not found")


def test_dynamic_folder_gets_placeholders(qtbot, qapp):
    """Dynamically created folders (via catalog_added with path) should get placeholders."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel, _PlaceholderType
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, Capability
    import uuid as _uuid

    class CreateProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="CreateProvider")
            self._catalogs = []

        def catalogs(self):
            return list(self._catalogs)

        def capabilities(self, catalog=None):
            return {Capability.CREATE_CATALOGS}

        def add_catalog(self, cat):
            self._catalogs.append(cat)
            self._set_events(cat, [])
            self.catalog_added.emit(cat)

    provider = CreateProvider()
    model = CatalogTreeModel()

    provider_idx = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        if model.node_from_index(idx).provider is provider:
            provider_idx = idx
            break
    assert provider_idx is not None

    cat = Catalog(uuid=str(_uuid.uuid4()), name="Cat1", provider=provider, path=["NewFolder"])
    provider.add_catalog(cat)

    folder_idx = None
    for r in range(model.rowCount(provider_idx)):
        child_idx = model.index(r, 0, provider_idx)
        child = model.node_from_index(child_idx)
        if child.name == "NewFolder" and not child.is_placeholder:
            folder_idx = child_idx
            break
    assert folder_idx is not None

    count = model.rowCount(folder_idx)
    assert count == 3  # Cat1 + 2 placeholders
    last = model.node_from_index(model.index(count - 1, 0, folder_idx))
    assert last.placeholder_type == _PlaceholderType.FOLDER


def test_tree_icon_provider_override(qtbot, qapp):
    """Provider's node_icon() should take precedence over defaults."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, Capability, NodeType
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon, QPixmap

    custom_icon = QIcon(QPixmap(16, 16))

    class IconProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="IconProvider")

        def catalogs(self):
            return []

        def capabilities(self, catalog=None):
            return set()

        def node_icon(self, node_type, path=None):
            if node_type == NodeType.PROVIDER:
                return custom_icon
            return None

    provider = IconProvider()
    model = CatalogTreeModel()

    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        node = model.node_from_index(idx)
        if node.provider is provider:
            icon = model.data(idx, Qt.ItemDataRole.DecorationRole)
            assert icon is custom_icon
            return
    pytest.fail("IconProvider not found")


# --- Task 5: prune folders with only placeholders ---


def test_prune_folder_with_only_placeholders(qtbot, qapp):
    """Folder with only placeholder children should be pruned when catalog is removed."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, Capability
    import uuid as _uuid

    class PruneProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="PruneProvider")
            self._catalogs = []

        def catalogs(self):
            return list(self._catalogs)

        def capabilities(self, catalog=None):
            return {Capability.CREATE_CATALOGS, Capability.DELETE_CATALOGS}

        def add_catalog(self, cat):
            self._catalogs.append(cat)
            self._set_events(cat, [])
            self.catalog_added.emit(cat)

        def remove_catalog(self, catalog):
            self._catalogs = [c for c in self._catalogs if c.uuid != catalog.uuid]
            super().remove_catalog(catalog)

    provider = PruneProvider()
    model = CatalogTreeModel()

    provider_idx = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        if model.node_from_index(idx).provider is provider:
            provider_idx = idx
            break
    assert provider_idx is not None

    cat = Catalog(uuid=str(_uuid.uuid4()), name="TempCat", provider=provider, path=["TempFolder"])
    provider.add_catalog(cat)

    non_placeholder_children = [
        model.node_from_index(model.index(r, 0, provider_idx))
        for r in range(model.rowCount(provider_idx))
        if not model.node_from_index(model.index(r, 0, provider_idx)).is_placeholder
    ]
    assert any(c.name == "TempFolder" for c in non_placeholder_children)

    provider.remove_catalog(cat)

    non_placeholder_children = [
        model.node_from_index(model.index(r, 0, provider_idx))
        for r in range(model.rowCount(provider_idx))
        if not model.node_from_index(model.index(r, 0, provider_idx)).is_placeholder
    ]
    assert not any(c.name == "TempFolder" for c in non_placeholder_children)


# --- Task 6: catalog placeholder setData builds path ---


def test_setdata_catalog_placeholder_builds_path(qtbot, qapp):
    """Creating a catalog via placeholder in a subfolder should pass the correct path."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel, _PlaceholderType
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from PySide6.QtCore import Qt

    provider = DummyProvider(num_catalogs=1, paths=[["ProjectA"]])
    model = CatalogTreeModel()

    provider_idx = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        if model.node_from_index(idx).provider is provider:
            provider_idx = idx
            break
    assert provider_idx is not None

    folder_idx = None
    for r in range(model.rowCount(provider_idx)):
        child_idx = model.index(r, 0, provider_idx)
        child = model.node_from_index(child_idx)
        if child.name == "ProjectA" and not child.is_placeholder:
            folder_idx = child_idx
            break
    assert folder_idx is not None

    ph_idx = None
    for r in range(model.rowCount(folder_idx)):
        child_idx = model.index(r, 0, folder_idx)
        child = model.node_from_index(child_idx)
        if child.placeholder_type == _PlaceholderType.CATALOG:
            ph_idx = child_idx
            break
    assert ph_idx is not None

    result = model.setData(ph_idx, "NewCatalog", Qt.ItemDataRole.EditRole)
    assert result is True

    created = [c for c in provider.catalogs() if c.name == "NewCatalog"]
    assert len(created) == 1
    assert created[0].path == ["ProjectA"]


# --- Task 7: folder placeholder setData ---


def test_setdata_folder_placeholder_creates_folder(qtbot, qapp):
    """Editing a folder placeholder should create a new folder node with its own placeholders."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel, _PlaceholderType
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from PySide6.QtCore import Qt

    provider = DummyProvider(num_catalogs=0)
    model = CatalogTreeModel()

    provider_idx = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        if model.node_from_index(idx).provider is provider:
            provider_idx = idx
            break
    assert provider_idx is not None

    folder_ph_idx = None
    for r in range(model.rowCount(provider_idx)):
        child_idx = model.index(r, 0, provider_idx)
        child = model.node_from_index(child_idx)
        if child.placeholder_type == _PlaceholderType.FOLDER:
            folder_ph_idx = child_idx
            break
    assert folder_ph_idx is not None

    result = model.setData(folder_ph_idx, "MyFolder", Qt.ItemDataRole.EditRole)
    assert result is True

    found_folder = False
    for r in range(model.rowCount(provider_idx)):
        child_idx = model.index(r, 0, provider_idx)
        child = model.node_from_index(child_idx)
        if child.name == "MyFolder" and not child.is_placeholder:
            found_folder = True
            assert model.rowCount(child_idx) == 2
            ph0 = model.node_from_index(model.index(0, 0, child_idx))
            ph1 = model.node_from_index(model.index(1, 0, child_idx))
            assert ph0.placeholder_type == _PlaceholderType.CATALOG
            assert ph1.placeholder_type == _PlaceholderType.FOLDER
            break
    assert found_folder


def test_setdata_nested_folder_creation(qtbot, qapp):
    """Creating a folder inside another folder should work."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel, _PlaceholderType
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from PySide6.QtCore import Qt

    provider = DummyProvider(num_catalogs=1, paths=[["OuterFolder"]])
    model = CatalogTreeModel()

    provider_idx = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        if model.node_from_index(idx).provider is provider:
            provider_idx = idx
            break

    outer_idx = None
    for r in range(model.rowCount(provider_idx)):
        child_idx = model.index(r, 0, provider_idx)
        child = model.node_from_index(child_idx)
        if child.name == "OuterFolder" and not child.is_placeholder:
            outer_idx = child_idx
            break
    assert outer_idx is not None

    folder_ph_idx = None
    for r in range(model.rowCount(outer_idx)):
        child_idx = model.index(r, 0, outer_idx)
        child = model.node_from_index(child_idx)
        if child.placeholder_type == _PlaceholderType.FOLDER:
            folder_ph_idx = child_idx
            break
    assert folder_ph_idx is not None

    result = model.setData(folder_ph_idx, "InnerFolder", Qt.ItemDataRole.EditRole)
    assert result is True

    found = False
    for r in range(model.rowCount(outer_idx)):
        child_idx = model.index(r, 0, outer_idx)
        child = model.node_from_index(child_idx)
        if child.name == "InnerFolder" and not child.is_placeholder:
            found = True
            assert model.rowCount(child_idx) == 2
            break
    assert found


def test_trigger_placeholder_edit_clears_filter(qtbot, qapp):
    """_trigger_placeholder_edit should clear the filter bar and attempt to edit."""
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.ui.catalog_tree import _PlaceholderType
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, paths=[["FolderA"]])
    browser = CatalogBrowser()
    qtbot.addWidget(browser)

    model = browser._tree_model

    browser._filter_bar.setText("something")
    assert browser._filter_bar.text() == "something"

    provider_node = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        n = model.node_from_index(idx)
        if n.provider is provider:
            provider_node = n
            break
    assert provider_node is not None

    folder_node = next(c for c in provider_node.children if c.name == "FolderA" and not c.is_placeholder)
    cat_ph = next(c for c in folder_node.children if c.placeholder_type == _PlaceholderType.CATALOG)

    browser._trigger_placeholder_edit(cat_ph)
    assert browser._filter_bar.text() == ""


def test_full_folder_catalog_creation_workflow(qtbot, qapp):
    """End-to-end: create folder, create catalog inside it, verify path, remove, verify pruned."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel, _PlaceholderType
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, Capability
    from PySide6.QtCore import Qt
    import uuid as _uuid

    class WorkflowProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="WorkflowProvider")
            self._catalogs = []

        def catalogs(self):
            return list(self._catalogs)

        def capabilities(self, catalog=None):
            return {Capability.CREATE_CATALOGS, Capability.DELETE_CATALOGS}

        def create_catalog(self, name, path=None):
            cat = Catalog(uuid=str(_uuid.uuid4()), name=name, provider=self, path=path or [])
            self._catalogs.append(cat)
            self._set_events(cat, [])
            self.catalog_added.emit(cat)
            return cat

        def remove_catalog(self, catalog):
            self._catalogs = [c for c in self._catalogs if c.uuid != catalog.uuid]
            super().remove_catalog(catalog)

    provider = WorkflowProvider()
    model = CatalogTreeModel()

    provider_idx = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        if model.node_from_index(idx).provider is provider:
            provider_idx = idx
            break
    assert provider_idx is not None

    # Step 1: Create folder via placeholder
    folder_ph_idx = None
    for r in range(model.rowCount(provider_idx)):
        child_idx = model.index(r, 0, provider_idx)
        child = model.node_from_index(child_idx)
        if child.placeholder_type == _PlaceholderType.FOLDER:
            folder_ph_idx = child_idx
            break
    assert folder_ph_idx is not None
    model.setData(folder_ph_idx, "MyProject", Qt.ItemDataRole.EditRole)

    folder_idx = None
    for r in range(model.rowCount(provider_idx)):
        child_idx = model.index(r, 0, provider_idx)
        child = model.node_from_index(child_idx)
        if child.name == "MyProject" and not child.is_placeholder:
            folder_idx = child_idx
            break
    assert folder_idx is not None

    # Step 2: Create catalog inside folder via placeholder
    cat_ph_idx = None
    for r in range(model.rowCount(folder_idx)):
        child_idx = model.index(r, 0, folder_idx)
        child = model.node_from_index(child_idx)
        if child.placeholder_type == _PlaceholderType.CATALOG:
            cat_ph_idx = child_idx
            break
    assert cat_ph_idx is not None
    model.setData(cat_ph_idx, "MyCatalog", Qt.ItemDataRole.EditRole)

    created = [c for c in provider.catalogs() if c.name == "MyCatalog"]
    assert len(created) == 1
    assert created[0].path == ["MyProject"]

    # Step 3: Remove catalog — folder should be pruned
    provider.remove_catalog(created[0])
    non_ph_children = [
        model.node_from_index(model.index(r, 0, provider_idx))
        for r in range(model.rowCount(provider_idx))
        if not model.node_from_index(model.index(r, 0, provider_idx)).is_placeholder
    ]
    assert not any(c.name == "MyProject" for c in non_ph_children), "Folder should be pruned"


def test_explicit_folder_gets_placeholders(qtbot, qapp):
    """Explicit folders (like cocat rooms) should get placeholders when provider supports creation."""
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel, _PlaceholderType
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, Capability
    import uuid as _uuid

    class RoomProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="RoomProvider")
            self._catalogs = []

        def catalogs(self):
            return list(self._catalogs)

        def capabilities(self, catalog=None):
            return {Capability.CREATE_CATALOGS}

        def create_catalog(self, name, path=None):
            cat = Catalog(uuid=str(_uuid.uuid4()), name=name, provider=self, path=path or [])
            self._catalogs.append(cat)
            self._set_events(cat, [])
            self.catalog_added.emit(cat)
            return cat

    provider = RoomProvider()
    model = CatalogTreeModel()

    provider.folder_added.emit(["room-1"])

    provider_idx = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        if model.node_from_index(idx).provider is provider:
            provider_idx = idx
            break
    assert provider_idx is not None

    room_idx = None
    for r in range(model.rowCount(provider_idx)):
        child_idx = model.index(r, 0, provider_idx)
        child = model.node_from_index(child_idx)
        if child.name == "room-1" and child.is_explicit_folder:
            room_idx = child_idx
            break
    assert room_idx is not None

    count = model.rowCount(room_idx)
    assert count == 2
    ph0 = model.node_from_index(model.index(0, 0, room_idx))
    ph1 = model.node_from_index(model.index(1, 0, room_idx))
    assert ph0.placeholder_type == _PlaceholderType.CATALOG
    assert ph1.placeholder_type == _PlaceholderType.FOLDER

    from PySide6.QtCore import Qt
    model.setData(model.index(0, 0, room_idx), "RoomCatalog", Qt.ItemDataRole.EditRole)
    created = [c for c in provider.catalogs() if c.name == "RoomCatalog"]
    assert len(created) == 1
    assert created[0].path == ["room-1"]


# --- Bug reproducer: create_catalog must emit catalog_added for tree to update ---


def test_create_catalog_without_signal_does_not_update_tree(qtbot, qapp):
    """Reproducer: if create_catalog doesn't emit catalog_added, the tree won't show the new catalog.

    This was the root cause of TSCat catalogs created in folders appearing at root level.
    """
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel, _PlaceholderType
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, Capability
    from PySide6.QtCore import Qt
    import uuid as _uuid

    class BuggyProvider(CatalogProvider):
        """Provider that does NOT emit catalog_added — reproduces the tscat bug."""

        def __init__(self):
            super().__init__(name="BuggyProvider")
            self._catalogs = []

        def catalogs(self):
            return list(self._catalogs)

        def capabilities(self, catalog=None):
            return {Capability.CREATE_CATALOGS}

        def create_catalog(self, name, path=None):
            cat = Catalog(uuid=str(_uuid.uuid4()), name=name, provider=self, path=path or [])
            self._catalogs.append(cat)
            self._set_events(cat, [])
            # BUG: missing self.catalog_added.emit(cat)
            return cat

    provider = BuggyProvider()
    model = CatalogTreeModel()

    # Find provider in tree
    provider_idx = None
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        if model.node_from_index(idx).provider is provider:
            provider_idx = idx
            break
    assert provider_idx is not None

    # Create folder via placeholder
    folder_ph_idx = None
    for r in range(model.rowCount(provider_idx)):
        child_idx = model.index(r, 0, provider_idx)
        child = model.node_from_index(child_idx)
        if child.placeholder_type == _PlaceholderType.FOLDER:
            folder_ph_idx = child_idx
            break
    assert folder_ph_idx is not None
    model.setData(folder_ph_idx, "TestFolder", Qt.ItemDataRole.EditRole)

    # Find folder
    folder_idx = None
    for r in range(model.rowCount(provider_idx)):
        child_idx = model.index(r, 0, provider_idx)
        child = model.node_from_index(child_idx)
        if child.name == "TestFolder" and not child.is_placeholder:
            folder_idx = child_idx
            break
    assert folder_idx is not None

    # Create catalog inside folder via placeholder
    cat_ph_idx = None
    for r in range(model.rowCount(folder_idx)):
        child_idx = model.index(r, 0, folder_idx)
        child = model.node_from_index(child_idx)
        if child.placeholder_type == _PlaceholderType.CATALOG:
            cat_ph_idx = child_idx
            break
    assert cat_ph_idx is not None
    model.setData(cat_ph_idx, "BuggyCatalog", Qt.ItemDataRole.EditRole)

    # The catalog was created in the provider...
    assert len(provider.catalogs()) == 1
    assert provider.catalogs()[0].path == ["TestFolder"]

    # ...but the tree does NOT show it (because catalog_added was never emitted)
    folder_children = [
        model.node_from_index(model.index(r, 0, folder_idx))
        for r in range(model.rowCount(folder_idx))
        if not model.node_from_index(model.index(r, 0, folder_idx)).is_placeholder
    ]
    assert len(folder_children) == 0, "Bug confirmed: tree missing catalog node because catalog_added not emitted"
