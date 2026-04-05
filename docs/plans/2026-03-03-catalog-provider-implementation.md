# Catalog Provider API Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a central catalog provider abstraction layer so any backend (TSCat, CoCat, CSV) can expose catalogs/events through a common API with a unified UI.

**Architecture:** QObject-based provider classes with auto-registration into a singleton registry. Sorted event storage with bisect-based range queries in the base class. Capability enum system (str, Enum) for open-ended feature declaration. New unified catalog browser dock widget that coexists with the existing TSCat LightweightManager.

**Tech Stack:** PySide6, stdlib bisect, dataclasses, pytest + pytestqt

---

### Task 1: Create the CatalogEvent class

**Files:**
- Create: `SciQLop/components/catalogs/__init__.py` (empty)
- Create: `SciQLop/components/catalogs/backend/__init__.py` (empty)
- Create: `SciQLop/components/catalogs/backend/provider.py`
- Create: `tests/test_catalog_provider.py`

**Step 1: Write the failing test**

```python
# tests/test_catalog_provider.py
from .fixtures import *
import pytest
from datetime import datetime, timezone


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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_catalog_provider.py -v -x`
Expected: FAIL — `ModuleNotFoundError: No module named 'SciQLop.components.catalogs'`

**Step 3: Write minimal implementation**

```python
# SciQLop/components/catalogs/__init__.py
# empty

# SciQLop/components/catalogs/backend/__init__.py
# empty

# SciQLop/components/catalogs/backend/provider.py
from __future__ import annotations
from datetime import datetime
from typing import Any
from PySide6.QtCore import QObject, Signal


class CatalogEvent(QObject):
    """Minimal event: uuid + time interval + optional metadata."""
    range_changed = Signal()

    def __init__(self, uuid: str, start: datetime, stop: datetime,
                 meta: dict[str, Any] | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._uuid = uuid
        self._start = start
        self._stop = stop
        self._meta = meta or {}

    @property
    def uuid(self) -> str:
        return self._uuid

    @property
    def start(self) -> datetime:
        return self._start

    @start.setter
    def start(self, value: datetime) -> None:
        if value != self._start:
            self._start = value
            self.range_changed.emit()

    @property
    def stop(self) -> datetime:
        return self._stop

    @stop.setter
    def stop(self, value: datetime) -> None:
        if value != self._stop:
            self._stop = value
            self.range_changed.emit()

    @property
    def meta(self) -> dict[str, Any]:
        return self._meta
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_catalog_provider.py -v -x`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/components/catalogs/ tests/test_catalog_provider.py
git commit -m "feat(catalogs): add CatalogEvent base class"
```

---

### Task 2: Create the Catalog descriptor and Capability enum

**Files:**
- Modify: `SciQLop/components/catalogs/backend/provider.py`
- Modify: `tests/test_catalog_provider.py`

**Step 1: Write the failing test**

```python
# append to tests/test_catalog_provider.py

def test_catalog_descriptor(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import Catalog
    cat = Catalog(uuid="cat-1", name="My Catalog")
    assert cat.uuid == "cat-1"
    assert cat.name == "My Catalog"
    assert cat.provider is None


def test_capability_enum(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import Capability
    assert Capability.EDIT_EVENTS == "edit_events"
    assert isinstance(Capability.EDIT_EVENTS, str)
    # Custom str enum values work in the same set
    caps = {Capability.EDIT_EVENTS, "custom_capability"}
    assert "edit_events" in caps
    assert "custom_capability" in caps
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_catalog_provider.py::test_catalog_descriptor tests/test_catalog_provider.py::test_capability_enum -v -x`
Expected: FAIL — `ImportError`

**Step 3: Write minimal implementation**

Append to `SciQLop/components/catalogs/backend/provider.py`:

```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtGui import QIcon


class Capability(str, Enum):
    EDIT_EVENTS = "edit_events"
    CREATE_EVENTS = "create_events"
    DELETE_EVENTS = "delete_events"
    CREATE_CATALOGS = "create_catalogs"
    DELETE_CATALOGS = "delete_catalogs"
    EXPORT_EVENTS = "export_events"
    IMPORT_EVENTS = "import_events"
    IMPORT_FILES = "import_files"


@dataclass
class ProviderAction:
    name: str
    callback: Callable[[Catalog], None]
    icon: QIcon | None = None


@dataclass
class Catalog:
    uuid: str
    name: str
    provider: CatalogProvider | None = None
```

Note: `CatalogProvider` is not yet defined; use a forward reference string in the dataclass. The actual field type annotation should be `"CatalogProvider" | None` or handled via `from __future__ import annotations`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_catalog_provider.py -v -x`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/components/catalogs/backend/provider.py tests/test_catalog_provider.py
git commit -m "feat(catalogs): add Catalog descriptor and Capability enum"
```

---

### Task 3: Create the CatalogProvider base class with sorted event storage

**Files:**
- Modify: `SciQLop/components/catalogs/backend/provider.py`
- Modify: `tests/test_catalog_provider.py`

**Step 1: Write the failing test**

```python
# append to tests/test_catalog_provider.py
from datetime import timedelta


class DummyProvider:
    """Helper: will subclass CatalogProvider once it exists."""
    pass


def _make_dummy_provider(qapp):
    """Create a concrete subclass of CatalogProvider for testing."""
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

        def catalogs(self) -> list:
            return self._catalogs

        def capabilities(self, catalog=None) -> set[str]:
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
    # Events 9..19 have start in [Jan 10 .. Jan 20)
    # bisect_left on Jan 10 = index 9, bisect_right on Jan 20 = index 20
    # So events with start >= Jan 10 and start <= Jan 20
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
    # Verify sorted order maintained
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_catalog_provider.py::test_provider_catalogs -v -x`
Expected: FAIL — `ImportError: cannot import name 'CatalogProvider'`

**Step 3: Write minimal implementation**

Add to `SciQLop/components/catalogs/backend/provider.py`:

```python
import bisect


class CatalogProvider(QObject):
    """Base class for catalog providers. Instantiating auto-registers with the
    central CatalogRegistry. Maintains sorted event lists per catalog with
    bisect-based range queries."""

    catalog_added = Signal(object)    # Catalog
    catalog_removed = Signal(object)  # Catalog
    events_changed = Signal(object)   # Catalog
    error_occurred = Signal(str)

    def __init__(self, name: str, parent: QObject | None = None):
        super().__init__(parent)
        self._name = name
        self._event_lists: dict[str, list[CatalogEvent]] = {}  # catalog uuid -> sorted events

    @property
    def name(self) -> str:
        return self._name

    def catalogs(self) -> list[Catalog]:
        raise NotImplementedError

    def events(self, catalog: Catalog,
               start: datetime | None = None,
               stop: datetime | None = None) -> list[CatalogEvent]:
        events = self._event_lists.get(catalog.uuid, [])
        if start is None and stop is None:
            return list(events)
        lo = 0
        hi = len(events)
        if start is not None:
            lo = bisect.bisect_left(events, start, key=lambda e: e.start)
        if stop is not None:
            hi = bisect.bisect_right(events, stop, key=lambda e: e.start)
        return events[lo:hi]

    def capabilities(self, catalog: Catalog | None = None) -> set[str]:
        return set()

    def actions(self, catalog: Catalog | None = None) -> list[ProviderAction]:
        return []

    # -- Protected API for subclasses --

    def _set_events(self, catalog: Catalog, events: list[CatalogEvent]) -> None:
        sorted_events = sorted(events, key=lambda e: e.start)
        self._event_lists[catalog.uuid] = sorted_events
        self.events_changed.emit(catalog)

    def _add_event(self, catalog: Catalog, event: CatalogEvent) -> None:
        events = self._event_lists.setdefault(catalog.uuid, [])
        bisect.insort(events, event, key=lambda e: e.start)
        self.events_changed.emit(catalog)

    def _remove_event(self, catalog: Catalog, event: CatalogEvent) -> None:
        events = self._event_lists.get(catalog.uuid, [])
        events.remove(event)
        self.events_changed.emit(catalog)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_catalog_provider.py -v -x`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/components/catalogs/backend/provider.py tests/test_catalog_provider.py
git commit -m "feat(catalogs): add CatalogProvider base class with sorted event storage"
```

---

### Task 4: Create the CatalogRegistry singleton with auto-registration

**Files:**
- Create: `SciQLop/components/catalogs/backend/registry.py`
- Modify: `SciQLop/components/catalogs/backend/provider.py` (wire auto-registration)
- Modify: `tests/test_catalog_provider.py`

**Step 1: Write the failing test**

```python
# append to tests/test_catalog_provider.py

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
    qapp.processEvents()

    assert len(registry.providers()) == initial_count - 1


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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_catalog_provider.py::test_registry_singleton -v -x`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# SciQLop/components/catalogs/backend/registry.py
from __future__ import annotations
from typing import TYPE_CHECKING
from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from .provider import CatalogProvider, Catalog


class CatalogRegistry(QObject):
    """Singleton registry for all catalog providers."""

    provider_registered = Signal(object)    # CatalogProvider
    provider_unregistered = Signal(object)  # CatalogProvider

    _instance: CatalogRegistry | None = None

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._providers: list[CatalogProvider] = []

    @classmethod
    def instance(cls) -> CatalogRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, provider: CatalogProvider) -> None:
        if provider not in self._providers:
            self._providers.append(provider)
            provider.destroyed.connect(lambda: self.unregister(provider))
            self.provider_registered.emit(provider)

    def unregister(self, provider: CatalogProvider) -> None:
        if provider in self._providers:
            self._providers.remove(provider)
            self.provider_unregistered.emit(provider)

    def providers(self) -> list[CatalogProvider]:
        return list(self._providers)

    def all_catalogs(self) -> list[Catalog]:
        result = []
        for provider in self._providers:
            result.extend(provider.catalogs())
        return result
```

Then modify `CatalogProvider.__init__` in `provider.py` to auto-register:

```python
def __init__(self, name: str, parent: QObject | None = None):
    super().__init__(parent)
    self._name = name
    self._event_lists: dict[str, list[CatalogEvent]] = {}
    from .registry import CatalogRegistry
    CatalogRegistry.instance().register(self)
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_catalog_provider.py -v -x`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/components/catalogs/backend/registry.py SciQLop/components/catalogs/backend/provider.py tests/test_catalog_provider.py
git commit -m "feat(catalogs): add CatalogRegistry singleton with auto-registration"
```

---

### Task 5: Create a DummyProvider for testing and as reference implementation

**Files:**
- Create: `SciQLop/components/catalogs/backend/dummy_provider.py`
- Modify: `tests/test_catalog_provider.py` (refactor to use DummyProvider)

**Step 1: Write the failing test**

```python
# append to tests/test_catalog_provider.py

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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_catalog_provider.py::test_dummy_provider_full_capabilities -v -x`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# SciQLop/components/catalogs/backend/dummy_provider.py
from __future__ import annotations
from datetime import datetime, timezone, timedelta
from .provider import CatalogProvider, Catalog, CatalogEvent, Capability


class DummyProvider(CatalogProvider):
    """Full-capability in-memory provider for testing and as reference."""

    def __init__(self, num_catalogs: int = 1, events_per_catalog: int = 100,
                 parent=None):
        super().__init__(name="DummyProvider", parent=parent)
        self._catalogs: list[Catalog] = []
        base = datetime(2020, 1, 1, tzinfo=timezone.utc)

        for c in range(num_catalogs):
            cat = Catalog(uuid=f"dummy-cat-{c}", name=f"Dummy Catalog {c}",
                          provider=self)
            self._catalogs.append(cat)
            events = []
            for i in range(events_per_catalog):
                events.append(CatalogEvent(
                    uuid=f"dummy-evt-{c}-{i}",
                    start=base + timedelta(days=i),
                    stop=base + timedelta(days=i, hours=1),
                    meta={"index": i, "catalog": c},
                ))
            self._set_events(cat, events)

    def catalogs(self) -> list[Catalog]:
        return list(self._catalogs)

    def capabilities(self, catalog: Catalog | None = None) -> set[str]:
        return {
            Capability.EDIT_EVENTS,
            Capability.CREATE_EVENTS,
            Capability.DELETE_EVENTS,
            Capability.CREATE_CATALOGS,
            Capability.DELETE_CATALOGS,
            Capability.EXPORT_EVENTS,
            Capability.IMPORT_EVENTS,
        }

    def import_events(self, catalog_name: str,
                      events: list[CatalogEvent]) -> Catalog:
        cat = Catalog(uuid=f"dummy-imported-{len(self._catalogs)}",
                      name=catalog_name, provider=self)
        self._catalogs.append(cat)
        self._set_events(cat, events)
        self.catalog_added.emit(cat)
        return cat
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_catalog_provider.py -v -x`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/components/catalogs/backend/dummy_provider.py tests/test_catalog_provider.py
git commit -m "feat(catalogs): add DummyProvider reference implementation"
```

---

### Task 6: Create the catalog tree model

**Files:**
- Create: `SciQLop/components/catalogs/ui/__init__.py` (empty)
- Create: `SciQLop/components/catalogs/ui/catalog_tree.py`
- Modify: `tests/test_catalog_provider.py`

**Step 1: Write the failing test**

```python
# append to tests/test_catalog_provider.py

def test_catalog_tree_model_structure(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=3)
    model = CatalogTreeModel()

    # Root has 1 child (the provider)
    assert model.rowCount() == 1
    provider_index = model.index(0, 0)
    assert model.data(provider_index) == "DummyProvider"

    # Provider has 3 children (catalogs)
    assert model.rowCount(provider_index) == 3
    cat_index = model.index(0, 0, provider_index)
    assert model.data(cat_index) == "Dummy Catalog 0"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_catalog_provider.py::test_catalog_tree_model_structure -v -x`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# SciQLop/components/catalogs/ui/__init__.py
# empty

# SciQLop/components/catalogs/ui/catalog_tree.py
from __future__ import annotations
from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt, QSortFilterProxyModel
from PySide6.QtGui import QIcon
from SciQLop.components.catalogs.backend.registry import CatalogRegistry
from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog


class _Node:
    __slots__ = ("name", "parent", "children", "provider", "catalog")

    def __init__(self, name: str, parent: _Node | None = None,
                 provider: CatalogProvider | None = None,
                 catalog: Catalog | None = None):
        self.name = name
        self.parent = parent
        self.children: list[_Node] = []
        self.provider = provider
        self.catalog = catalog

    def row(self) -> int:
        if self.parent is not None:
            return self.parent.children.index(self)
        return 0

    def append(self, child: _Node) -> _Node:
        child.parent = self
        self.children.append(child)
        return child


class CatalogTreeModel(QAbstractItemModel):
    """Tree model: root -> provider -> catalog. Fed from CatalogRegistry."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._root = _Node(name="root")
        self._registry = CatalogRegistry.instance()
        self._registry.provider_registered.connect(self._on_provider_registered)
        self._registry.provider_unregistered.connect(self._on_provider_unregistered)
        # Build initial tree
        for provider in self._registry.providers():
            self._add_provider_node(provider)

    def _add_provider_node(self, provider: CatalogProvider) -> None:
        pnode = _Node(name=provider.name, provider=provider)
        for cat in provider.catalogs():
            pnode.append(_Node(name=cat.name, catalog=cat, provider=provider))
        provider.catalog_added.connect(lambda cat, p=provider: self._on_catalog_added(p, cat))
        provider.catalog_removed.connect(lambda cat, p=provider: self._on_catalog_removed(p, cat))
        self.beginInsertRows(QModelIndex(), len(self._root.children), len(self._root.children))
        self._root.append(pnode)
        self.endInsertRows()

    def _on_provider_registered(self, provider: CatalogProvider) -> None:
        self._add_provider_node(provider)

    def _on_provider_unregistered(self, provider: CatalogProvider) -> None:
        for i, node in enumerate(self._root.children):
            if node.provider is provider:
                self.beginRemoveRows(QModelIndex(), i, i)
                self._root.children.pop(i)
                self.endRemoveRows()
                return

    def _on_catalog_added(self, provider: CatalogProvider, catalog: Catalog) -> None:
        for pnode in self._root.children:
            if pnode.provider is provider:
                parent_index = self.createIndex(pnode.row(), 0, pnode)
                row = len(pnode.children)
                self.beginInsertRows(parent_index, row, row)
                pnode.append(_Node(name=catalog.name, catalog=catalog, provider=provider))
                self.endInsertRows()
                return

    def _on_catalog_removed(self, provider: CatalogProvider, catalog: Catalog) -> None:
        for pnode in self._root.children:
            if pnode.provider is provider:
                for i, cnode in enumerate(pnode.children):
                    if cnode.catalog is catalog:
                        parent_index = self.createIndex(pnode.row(), 0, pnode)
                        self.beginRemoveRows(parent_index, i, i)
                        pnode.children.pop(i)
                        self.endRemoveRows()
                        return

    def node_from_index(self, index: QModelIndex) -> _Node:
        if not index.isValid():
            return self._root
        return index.internalPointer()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self.node_from_index(parent).children)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 1

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        parent_node = self.node_from_index(parent)
        if row < 0 or row >= len(parent_node.children):
            return QModelIndex()
        return self.createIndex(row, column, parent_node.children[row])

    def parent(self, index: QModelIndex) -> QModelIndex:
        if not index.isValid():
            return QModelIndex()
        node: _Node = index.internalPointer()
        if node.parent is None or node.parent is self._root:
            return QModelIndex()
        return self.createIndex(node.parent.row(), 0, node.parent)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return index.internalPointer().name
        return None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_catalog_provider.py -v -x`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/components/catalogs/ui/ tests/test_catalog_provider.py
git commit -m "feat(catalogs): add CatalogTreeModel for provider->catalog tree"
```

---

### Task 7: Create the event table model

**Files:**
- Create: `SciQLop/components/catalogs/ui/event_table.py`
- Modify: `tests/test_catalog_provider.py`

**Step 1: Write the failing test**

```python
# append to tests/test_catalog_provider.py

def test_event_table_model(qtbot, qapp):
    from SciQLop.components.catalogs.ui.event_table import EventTableModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=10)
    cat = provider.catalogs()[0]
    events = provider.events(cat)

    model = EventTableModel()
    model.set_events(events)

    # Columns: start, stop, + meta keys (index, catalog)
    assert model.rowCount() == 10
    assert model.columnCount() >= 2  # at least start and stop

    # First row start
    from PySide6.QtCore import Qt
    index = model.index(0, 0)
    assert index.isValid()
    value = model.data(index, Qt.ItemDataRole.DisplayRole)
    assert value is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_catalog_provider.py::test_event_table_model -v -x`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# SciQLop/components/catalogs/ui/event_table.py
from __future__ import annotations
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from SciQLop.components.catalogs.backend.provider import CatalogEvent


class EventTableModel(QAbstractTableModel):
    """Table model for events in a single catalog."""

    _FIXED_COLUMNS = ["start", "stop"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._events: list[CatalogEvent] = []
        self._meta_keys: list[str] = []

    def set_events(self, events: list[CatalogEvent]) -> None:
        self.beginResetModel()
        self._events = list(events)
        # Collect all meta keys across events
        keys: set[str] = set()
        for e in self._events:
            keys.update(e.meta.keys())
        self._meta_keys = sorted(keys)
        self.endResetModel()

    def clear(self) -> None:
        self.beginResetModel()
        self._events = []
        self._meta_keys = []
        self.endResetModel()

    def event_at(self, row: int) -> CatalogEvent | None:
        if 0 <= row < len(self._events):
            return self._events[row]
        return None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._events)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return len(self._FIXED_COLUMNS) + len(self._meta_keys)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        event = self._events[index.row()]
        col = index.column()
        if col == 0:
            return str(event.start)
        elif col == 1:
            return str(event.stop)
        else:
            key = self._meta_keys[col - 2]
            return str(event.meta.get(key, ""))

    def headerData(self, section: int, orientation: Qt.Orientation,
                   role: int = Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole or orientation != Qt.Orientation.Horizontal:
            return None
        if section < len(self._FIXED_COLUMNS):
            return self._FIXED_COLUMNS[section]
        return self._meta_keys[section - len(self._FIXED_COLUMNS)]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_catalog_provider.py -v -x`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/components/catalogs/ui/event_table.py tests/test_catalog_provider.py
git commit -m "feat(catalogs): add EventTableModel for displaying catalog events"
```

---

### Task 8: Create the CatalogBrowser dock widget

**Files:**
- Create: `SciQLop/components/catalogs/ui/catalog_browser.py`
- Modify: `tests/test_catalog_provider.py`

**Step 1: Write the failing test**

```python
# append to tests/test_catalog_provider.py

def test_catalog_browser_widget(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=2, events_per_catalog=10)
    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    browser.show()

    # Should have the tree on the left with provider + catalogs
    tree = browser._catalog_tree
    model = tree.model()
    assert model.rowCount() >= 1  # at least one provider
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_catalog_provider.py::test_catalog_browser_widget -v -x`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write minimal implementation**

```python
# SciQLop/components/catalogs/ui/catalog_browser.py
from __future__ import annotations
from PySide6.QtCore import Slot, QModelIndex, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QTreeView,
    QTableView, QLineEdit, QToolButton, QPushButton, QMenu,
)
from PySide6.QtGui import Qt
from SciQLop.components.catalogs.backend.provider import (
    CatalogProvider, Catalog, CatalogEvent, Capability,
)
from SciQLop.components.catalogs.backend.registry import CatalogRegistry
from .catalog_tree import CatalogTreeModel, _Node
from .event_table import EventTableModel


class CatalogBrowser(QWidget):
    """Unified catalog browser: tree of providers/catalogs + event table."""

    event_selected = Signal(object)  # CatalogEvent

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Filter bar
        self._filter = QLineEdit()
        self._filter.setPlaceholderText("Filter catalogs...")
        layout.addWidget(self._filter)

        # Splitter: tree | table
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)

        # Left: catalog tree
        self._catalog_tree = QTreeView()
        self._tree_model = CatalogTreeModel(self)
        self._catalog_tree.setModel(self._tree_model)
        self._catalog_tree.setMaximumWidth(250)
        self._catalog_tree.setHeaderHidden(True)
        self._catalog_tree.selectionModel().currentChanged.connect(self._on_catalog_selected)
        splitter.addWidget(self._catalog_tree)

        # Right: event table
        self._event_table = QTableView()
        self._event_model = EventTableModel(self)
        self._event_table.setModel(self._event_model)
        self._event_table.setSortingEnabled(True)
        self._event_table.selectionModel().currentChanged.connect(self._on_event_selected)
        splitter.addWidget(self._event_table)

        # Bottom toolbar
        toolbar = QHBoxLayout()
        layout.addLayout(toolbar)

        self._add_event_btn = QPushButton("+ Add Event")
        self._add_event_btn.setVisible(False)
        self._add_event_btn.clicked.connect(self._on_add_event)
        toolbar.addWidget(self._add_event_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setVisible(False)
        self._delete_btn.clicked.connect(self._on_delete)
        toolbar.addWidget(self._delete_btn)

        self._actions_btn = QToolButton()
        self._actions_btn.setText("Actions")
        self._actions_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self._actions_btn.setVisible(False)
        toolbar.addWidget(self._actions_btn)

        toolbar.addStretch()

        # State
        self._current_provider: CatalogProvider | None = None
        self._current_catalog: Catalog | None = None

    @Slot(QModelIndex, QModelIndex)
    def _on_catalog_selected(self, current: QModelIndex, previous: QModelIndex):
        node: _Node = self._tree_model.node_from_index(current)
        if node.catalog is not None and node.provider is not None:
            self._current_provider = node.provider
            self._current_catalog = node.catalog
            events = node.provider.events(node.catalog)
            self._event_model.set_events(events)
            self._update_toolbar()
        else:
            self._current_provider = None
            self._current_catalog = None
            self._event_model.clear()
            self._update_toolbar()

    @Slot(QModelIndex, QModelIndex)
    def _on_event_selected(self, current: QModelIndex, previous: QModelIndex):
        event = self._event_model.event_at(current.row())
        if event is not None:
            self.event_selected.emit(event)

    def _update_toolbar(self):
        if self._current_provider is None or self._current_catalog is None:
            self._add_event_btn.setVisible(False)
            self._delete_btn.setVisible(False)
            self._actions_btn.setVisible(False)
            return

        caps = self._current_provider.capabilities(self._current_catalog)
        self._add_event_btn.setVisible(Capability.CREATE_EVENTS in caps)
        self._delete_btn.setVisible(Capability.DELETE_EVENTS in caps)

        actions = self._current_provider.actions(self._current_catalog)
        if actions:
            menu = QMenu(self)
            for action in actions:
                cat = self._current_catalog
                menu.addAction(action.name, lambda a=action, c=cat: a.callback(c))
            self._actions_btn.setMenu(menu)
            self._actions_btn.setVisible(True)
        else:
            self._actions_btn.setVisible(False)

    @Slot()
    def _on_add_event(self):
        pass  # Will be implemented when wiring to providers

    @Slot()
    def _on_delete(self):
        pass  # Will be implemented when wiring to providers
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_catalog_provider.py -v -x`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_browser.py tests/test_catalog_provider.py
git commit -m "feat(catalogs): add CatalogBrowser unified dock widget"
```

---

### Task 9: Wire CatalogBrowser toolbar buttons to capability-driven actions

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_browser.py`
- Modify: `tests/test_catalog_provider.py`

**Step 1: Write the failing test**

```python
# append to tests/test_catalog_provider.py

def test_catalog_browser_toolbar_visibility(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, Capability

    # Read-only provider
    class ReadOnlyProvider(CatalogProvider):
        def __init__(self):
            super().__init__(name="ReadOnly")
            cat = Catalog(uuid="ro-1", name="ReadOnly Cat", provider=self)
            self._cats = [cat]
            self._set_events(cat, [])

        def catalogs(self):
            return self._cats

        def capabilities(self, catalog=None):
            return set()  # no capabilities

    provider = ReadOnlyProvider()
    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    browser.show()

    # Select the catalog in the tree
    tree = browser._catalog_tree
    provider_index = tree.model().index(0, 0)  # may not be first if other providers exist
    # Find the ReadOnly provider
    model = tree.model()
    for i in range(model.rowCount()):
        idx = model.index(i, 0)
        if model.data(idx) == "ReadOnly":
            provider_index = idx
            break
    cat_index = model.index(0, 0, provider_index)
    tree.setCurrentIndex(cat_index)

    # Toolbar buttons should be hidden for read-only
    assert not browser._add_event_btn.isVisible()
    assert not browser._delete_btn.isVisible()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_catalog_provider.py::test_catalog_browser_toolbar_visibility -v -x`
Expected: This should already PASS with the current implementation (toolbar updates on selection). If it does, this task is a verification step.

**Step 3: If passes, commit**

```bash
git add tests/test_catalog_provider.py
git commit -m "test(catalogs): verify capability-driven toolbar visibility"
```

---

### Task 10: Export the public API from `SciQLop/components/catalogs/__init__.py`

**Files:**
- Modify: `SciQLop/components/catalogs/__init__.py`

**Step 1: Write the failing test**

```python
# append to tests/test_catalog_provider.py

def test_public_api_imports(qtbot, qapp):
    from SciQLop.components.catalogs import (
        CatalogEvent, Catalog, CatalogProvider,
        Capability, ProviderAction,
        CatalogRegistry,
    )
    assert CatalogEvent is not None
    assert CatalogRegistry is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_catalog_provider.py::test_public_api_imports -v -x`
Expected: FAIL — `ImportError`

**Step 3: Write minimal implementation**

```python
# SciQLop/components/catalogs/__init__.py
from .backend.provider import CatalogEvent, Catalog, CatalogProvider, Capability, ProviderAction
from .backend.registry import CatalogRegistry

__all__ = [
    "CatalogEvent",
    "Catalog",
    "CatalogProvider",
    "Capability",
    "ProviderAction",
    "CatalogRegistry",
]
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_catalog_provider.py -v -x`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/components/catalogs/__init__.py tests/test_catalog_provider.py
git commit -m "feat(catalogs): export public API from catalogs package"
```

---

## Summary

Tasks 1-10 deliver the complete backend + basic UI:

| Task | What | Key Files |
|------|------|-----------|
| 1 | CatalogEvent class | `backend/provider.py` |
| 2 | Catalog + Capability enum | `backend/provider.py` |
| 3 | CatalogProvider with sorted storage | `backend/provider.py` |
| 4 | CatalogRegistry + auto-registration | `backend/registry.py` |
| 5 | DummyProvider reference impl | `backend/dummy_provider.py` |
| 6 | CatalogTreeModel | `ui/catalog_tree.py` |
| 7 | EventTableModel | `ui/event_table.py` |
| 8 | CatalogBrowser dock widget | `ui/catalog_browser.py` |
| 9 | Toolbar capability tests | tests |
| 10 | Public API exports | `__init__.py` |

**Not yet covered (future tasks):**
- Plot integration (vertical spans from selected catalog)
- Drag and drop between providers
- Cross-provider copy/import flow
- Filter proxy on the catalog tree
- Wiring the CatalogBrowser into SciQLop's main window as a dock
