# Catalog Deferred Save Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add dirty-state tracking and explicit save to the catalog provider API, with UI indicators and save actions in the catalog tree.

**Architecture:** Add `SAVE`/`SAVE_CATALOG` capabilities, dirty tracking (`_dirty_catalogs` set + `dirty_changed` signal), and `save()`/`_do_save()` methods to `CatalogProvider` base class. Auto-mark dirty on mutations. `TscatCatalogProvider` implements `_do_save()` via `tscat.save()`. Tree UI shows asterisk on dirty nodes and a save button/context menu on dirty providers.

**Tech Stack:** PySide6, tscat, existing provider/tree/browser abstractions

---

### Task 1: Add SAVE capabilities to provider API

**Files:**
- Modify: `SciQLop/components/catalogs/backend/provider.py:53-61`
- Test: `tests/test_catalog_dirty_state.py`

**Step 1: Write the failing test**

```python
# tests/test_catalog_dirty_state.py
from .fixtures import *
import pytest
from datetime import datetime, timezone, timedelta
from SciQLop.components.catalogs.backend.provider import Capability


def test_save_capability_exists(qapp):
    assert hasattr(Capability, "SAVE")
    assert hasattr(Capability, "SAVE_CATALOG")
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_dirty_state.py::test_save_capability_exists -v`
Expected: FAIL with `AttributeError`

**Step 3: Write minimal implementation**

Add to `Capability` enum in `SciQLop/components/catalogs/backend/provider.py:53-61`:

```python
class Capability(str, Enum):
    EDIT_EVENTS = "edit_events"
    CREATE_EVENTS = "create_events"
    DELETE_EVENTS = "delete_events"
    CREATE_CATALOGS = "create_catalogs"
    DELETE_CATALOGS = "delete_catalogs"
    EXPORT_EVENTS = "export_events"
    IMPORT_EVENTS = "import_events"
    IMPORT_FILES = "import_files"
    SAVE = "save"
    SAVE_CATALOG = "save_catalog"
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_catalog_dirty_state.py::test_save_capability_exists -v`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/components/catalogs/backend/provider.py tests/test_catalog_dirty_state.py
git commit -m "feat(catalogs): add SAVE and SAVE_CATALOG capabilities"
```

---

### Task 2: Add dirty tracking state and signals to CatalogProvider

**Files:**
- Modify: `SciQLop/components/catalogs/backend/provider.py:79-146`
- Test: `tests/test_catalog_dirty_state.py`

**Step 1: Write the failing test**

```python
# Append to tests/test_catalog_dirty_state.py
def test_provider_dirty_signal_and_state(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]

    assert not provider.is_dirty()
    assert not provider.is_dirty(cat)

    # mark dirty and check signal
    with qtbot.waitSignal(provider.dirty_changed, timeout=1000) as blocker:
        provider.mark_dirty(cat)

    assert blocker.args[0].uuid == cat.uuid
    assert blocker.args[1] is True
    assert provider.is_dirty()
    assert provider.is_dirty(cat)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_dirty_state.py::test_provider_dirty_signal_and_state -v`
Expected: FAIL with `AttributeError: 'DummyProvider' object has no attribute 'is_dirty'`

**Step 3: Write minimal implementation**

In `CatalogProvider` class in `provider.py`:

Add signal after line 85:
```python
dirty_changed = Signal(object, bool)  # (catalog, is_dirty)
```

Add to `__init__` after `self._events` (line 90):
```python
self._dirty_catalogs: set[str] = set()
```

Add new methods after `remove_catalog`:
```python
def mark_dirty(self, catalog: Catalog) -> None:
    if catalog.uuid not in self._dirty_catalogs:
        self._dirty_catalogs.add(catalog.uuid)
        self.dirty_changed.emit(catalog, True)

def is_dirty(self, catalog: Catalog | None = None) -> bool:
    if catalog is None:
        return len(self._dirty_catalogs) > 0
    return catalog.uuid in self._dirty_catalogs

def save(self) -> None:
    self._do_save()
    dirty_uuids = set(self._dirty_catalogs)
    self._dirty_catalogs.clear()
    for cat in self.catalogs():
        if cat.uuid in dirty_uuids:
            self.dirty_changed.emit(cat, False)

def save_catalog(self, catalog: Catalog) -> None:
    self._do_save_catalog(catalog)
    if catalog.uuid in self._dirty_catalogs:
        self._dirty_catalogs.discard(catalog.uuid)
        self.dirty_changed.emit(catalog, False)

def _do_save(self) -> None:
    pass

def _do_save_catalog(self, catalog: Catalog) -> None:
    pass
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_catalog_dirty_state.py::test_provider_dirty_signal_and_state -v`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/components/catalogs/backend/provider.py tests/test_catalog_dirty_state.py
git commit -m "feat(catalogs): add dirty tracking and save methods to CatalogProvider"
```

---

### Task 3: Auto-mark dirty on event mutations

**Files:**
- Modify: `SciQLop/components/catalogs/backend/provider.py`
- Test: `tests/test_catalog_dirty_state.py`

**Step 1: Write the failing tests**

```python
# Append to tests/test_catalog_dirty_state.py
def test_add_event_marks_dirty(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    import uuid as _uuid

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0)
    cat = provider.catalogs()[0]

    event = CatalogEvent(
        uuid=str(_uuid.uuid4()),
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 12, tzinfo=timezone.utc),
    )

    with qtbot.waitSignal(provider.dirty_changed, timeout=1000):
        provider.add_event(cat, event)

    assert provider.is_dirty(cat)


def test_remove_event_marks_dirty(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    event = provider.events(cat)[0]

    with qtbot.waitSignal(provider.dirty_changed, timeout=1000):
        provider.remove_event(cat, event)

    assert provider.is_dirty(cat)


def test_event_range_change_marks_dirty(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    event = provider.events(cat)[0]

    with qtbot.waitSignal(provider.dirty_changed, timeout=1000):
        event.start = datetime(2025, 6, 1, tzinfo=timezone.utc)

    assert provider.is_dirty(cat)
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_catalog_dirty_state.py::test_add_event_marks_dirty tests/test_catalog_dirty_state.py::test_remove_event_marks_dirty tests/test_catalog_dirty_state.py::test_event_range_change_marks_dirty -v`
Expected: FAIL (dirty_changed signal not emitted on these operations)

**Step 3: Write minimal implementation**

Modify `add_event` and `remove_event` in `CatalogProvider` to call `mark_dirty`:

```python
def add_event(self, catalog: Catalog, event: CatalogEvent) -> None:
    """Public API: add an event to a catalog. Override for backend persistence."""
    self._add_event(catalog, event)
    self.mark_dirty(catalog)

def remove_event(self, catalog: Catalog, event: CatalogEvent) -> None:
    """Public API: remove an event from a catalog. Override for backend persistence."""
    self._remove_event(catalog, event)
    self.mark_dirty(catalog)
```

For event range changes, we need to track which catalog an event belongs to. Add a `_event_catalog_map` to `CatalogProvider.__init__`:

```python
self._event_catalog_map: dict[str, Catalog] = {}  # event uuid -> catalog
```

Update `_add_event` to register the mapping and connect to `range_changed`:

```python
def _add_event(self, catalog: Catalog, event: CatalogEvent) -> None:
    if catalog.uuid not in self._events:
        self._events[catalog.uuid] = []
    bisect.insort(self._events[catalog.uuid], event, key=lambda e: e.start)
    self._event_catalog_map[event.uuid] = catalog
    event.range_changed.connect(lambda cat=catalog: self.mark_dirty(cat))
    self.events_changed.emit(catalog)
```

Update `_set_events` to do the same for bulk loads:

```python
def _set_events(self, catalog: Catalog, events: list[CatalogEvent]) -> None:
    self._events[catalog.uuid] = sorted(events, key=lambda e: e.start)
    for event in events:
        self._event_catalog_map[event.uuid] = catalog
        event.range_changed.connect(lambda cat=catalog: self.mark_dirty(cat))
```

Update `_remove_event` to clean up:

```python
def _remove_event(self, catalog: Catalog, event: CatalogEvent) -> None:
    event_list = self._events.get(catalog.uuid, [])
    try:
        event_list.remove(event)
    except ValueError:
        pass
    self._event_catalog_map.pop(event.uuid, None)
    self.events_changed.emit(catalog)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_catalog_dirty_state.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add SciQLop/components/catalogs/backend/provider.py tests/test_catalog_dirty_state.py
git commit -m "feat(catalogs): auto-mark catalogs dirty on event mutations"
```

---

### Task 4: Add save() clearing dirty state

**Files:**
- Test: `tests/test_catalog_dirty_state.py`

**Step 1: Write the failing test**

```python
# Append to tests/test_catalog_dirty_state.py
def test_save_clears_dirty(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=2, events_per_catalog=3)
    cats = provider.catalogs()
    event0 = provider.events(cats[0])[0]
    event1 = provider.events(cats[1])[0]

    event0.start = datetime(2025, 6, 1, tzinfo=timezone.utc)
    event1.start = datetime(2025, 6, 1, tzinfo=timezone.utc)

    assert provider.is_dirty(cats[0])
    assert provider.is_dirty(cats[1])

    signals = []
    provider.dirty_changed.connect(lambda cat, dirty: signals.append((cat.uuid, dirty)))

    provider.save()

    assert not provider.is_dirty(cats[0])
    assert not provider.is_dirty(cats[1])
    assert not provider.is_dirty()
    # Should have emitted dirty_changed(cat, False) for each dirty catalog
    false_signals = [(uuid, d) for uuid, d in signals if not d]
    assert len(false_signals) == 2
```

**Step 2: Run test to verify it passes** (implementation already in Task 2)

Run: `uv run pytest tests/test_catalog_dirty_state.py::test_save_clears_dirty -v`
Expected: PASS (save logic was already implemented in Task 2)

**Step 3: Commit**

```bash
git add tests/test_catalog_dirty_state.py
git commit -m "test(catalogs): add save-clears-dirty test"
```

---

### Task 5: Implement TscatCatalogProvider._do_save()

**Files:**
- Modify: `SciQLop/plugins/tscat_catalogs/tscat_provider.py:93-221`

**Step 1: Add SAVE capability and _do_save implementation**

In `TscatCatalogProvider.capabilities()`, add `Capability.SAVE`:

```python
def capabilities(self, catalog: Catalog | None = None) -> set[str]:
    return {
        Capability.EDIT_EVENTS,
        Capability.CREATE_EVENTS,
        Capability.DELETE_EVENTS,
        Capability.CREATE_CATALOGS,
        Capability.SAVE,
    }
```

Add `_do_save` method to `TscatCatalogProvider`:

```python
def _do_save(self) -> None:
    import tscat
    tscat.save()
```

Also fix `add_event` — it currently doesn't call `super().add_event()`, so the base class dirty tracking is bypassed. The tscat provider manages its own event cache via `_on_action_done`, but we still need dirty marking. Add `mark_dirty` call:

```python
def add_event(self, catalog: Catalog, event: CatalogEvent) -> None:
    def _link_to_catalog(action):
        tscat_model.do(AddEventsToCatalogueAction(
            user_callback=None,
            uuids=[action.entity.uuid],
            catalogue_uuid=catalog.uuid,
        ))

    tscat_model.do(CreateEntityAction(
        user_callback=_link_to_catalog,
        cls=tscat._Event,
        args=dict(start=event.start, stop=event.stop, author="SciQLop",
                  uuid=event.uuid),
    ))
    self.mark_dirty(catalog)
```

**Step 2: Run existing tests to verify nothing breaks**

Run: `uv run pytest tests/test_panel_catalog_manager.py -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add SciQLop/plugins/tscat_catalogs/tscat_provider.py
git commit -m "feat(catalogs): implement _do_save() in TscatCatalogProvider"
```

---

### Task 6: Update __init__.py exports

**Files:**
- Modify: `SciQLop/components/catalogs/__init__.py`

**Step 1: Check current exports**

Read `SciQLop/components/catalogs/__init__.py` and ensure `SAVE`, `SAVE_CATALOG` are accessible if the file re-exports `Capability`.

**Step 2: Verify imports work**

Run: `uv run python -c "from SciQLop.components.catalogs import Capability; print(Capability.SAVE)"`
Expected: `save`

**Step 3: Commit if changes were needed**

```bash
git add SciQLop/components/catalogs/__init__.py
git commit -m "chore(catalogs): update exports for new capabilities"
```

---

### Task 7: Add dirty indicator to catalog tree display

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_tree.py:35-213`
- Test: `tests/test_catalog_dirty_state.py`

**Step 1: Write the failing test**

```python
# Append to tests/test_catalog_dirty_state.py
def test_tree_shows_dirty_indicator(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from PySide6.QtCore import Qt

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    model = CatalogTreeModel()

    # Find the catalog node
    provider_idx = model.index(model.rowCount() - 1, 0)  # last provider added
    cat_idx = model.index(0, 0, provider_idx)

    # Before marking dirty
    name_before = model.data(cat_idx, Qt.ItemDataRole.DisplayRole)
    assert not name_before.endswith(" *")

    # Mark dirty
    provider.mark_dirty(cat)

    name_after = model.data(cat_idx, Qt.ItemDataRole.DisplayRole)
    assert name_after.endswith(" *")

    # Provider node should also show dirty
    provider_name = model.data(provider_idx, Qt.ItemDataRole.DisplayRole)
    assert provider_name.endswith(" *")


def test_tree_clears_dirty_on_save(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from PySide6.QtCore import Qt

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    model = CatalogTreeModel()

    provider_idx = model.index(model.rowCount() - 1, 0)
    cat_idx = model.index(0, 0, provider_idx)

    provider.mark_dirty(cat)
    provider.save()

    name_after_save = model.data(cat_idx, Qt.ItemDataRole.DisplayRole)
    assert not name_after_save.endswith(" *")

    provider_name = model.data(provider_idx, Qt.ItemDataRole.DisplayRole)
    assert not provider_name.endswith(" *")
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_catalog_dirty_state.py::test_tree_shows_dirty_indicator tests/test_catalog_dirty_state.py::test_tree_clears_dirty_on_save -v`
Expected: FAIL

**Step 3: Write minimal implementation**

In `CatalogTreeModel`, connect to `provider.dirty_changed` in `_add_provider_node` (after line 77):

```python
provider.dirty_changed.connect(lambda cat, dirty, p=provider, n=node: self._on_dirty_changed(p, n, cat, dirty))
```

Add `_on_dirty_changed` method:

```python
def _on_dirty_changed(self, provider: CatalogProvider, pnode: _Node, catalog: object, is_dirty: bool) -> None:
    # Emit dataChanged for the catalog node
    cat_node = self._find_catalog_node(pnode, catalog)
    if cat_node is not None:
        idx = self.createIndex(cat_node.row(), 0, cat_node)
        self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole])
    # Emit dataChanged for the provider node too
    pnode_idx = self.createIndex(pnode.row(), 0, pnode)
    self.dataChanged.emit(pnode_idx, pnode_idx, [Qt.ItemDataRole.DisplayRole])

def _find_catalog_node(self, node: _Node, catalog: object) -> _Node | None:
    for child in node.children:
        if child.catalog is not None and child.catalog.uuid == catalog.uuid:
            return child
        found = self._find_catalog_node(child, catalog)
        if found is not None:
            return found
    return None
```

Modify `data()` to append " *" when dirty:

```python
def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> Any:
    if not index.isValid():
        return None
    if role == Qt.ItemDataRole.DisplayRole:
        node = index.internalPointer()
        name = node.name
        if node.provider is not None:
            if node.catalog is not None:
                # Catalog node: dirty if this catalog is dirty
                if node.provider.is_dirty(node.catalog):
                    name += " *"
            elif node.parent is self._root:
                # Provider node: dirty if any catalog is dirty
                if node.provider.is_dirty():
                    name += " *"
        return name
    return None
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_catalog_dirty_state.py -v`
Expected: ALL PASS

**Step 5: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_tree.py tests/test_catalog_dirty_state.py
git commit -m "feat(catalogs): show dirty indicator on catalog tree nodes"
```

---

### Task 8: Add save button to tree via delegate

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_tree.py`
- Modify: `SciQLop/components/catalogs/ui/catalog_browser.py`

**Step 1: Implement a custom delegate for save button on provider nodes**

Add to `catalog_tree.py`, a method to expose save-ability and a custom role:

```python
DIRTY_PROVIDER_ROLE = Qt.ItemDataRole.UserRole + 1
```

Update `data()` to support the new role:

```python
if role == DIRTY_PROVIDER_ROLE:
    node = index.internalPointer()
    if node.provider is not None and node.parent is self._root:
        from ..backend.provider import Capability
        has_save = Capability.SAVE in node.provider.capabilities()
        return has_save and node.provider.is_dirty()
    return False
```

In `catalog_browser.py`, create a delegate that renders a save icon button for dirty provider nodes:

```python
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle, QApplication
from PySide6.QtCore import QRect, QSize, QEvent, QPoint
from PySide6.QtGui import QIcon

class _SaveButtonDelegate(QStyledItemDelegate):
    """Renders a clickable save icon next to dirty provider nodes."""

    save_clicked = Signal(QModelIndex)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._icon = QIcon.fromTheme("document-save")
        self._icon_size = 16

    def paint(self, painter, option, index):
        super().paint(painter, option, index)
        from .catalog_tree import DIRTY_PROVIDER_ROLE
        if index.data(DIRTY_PROVIDER_ROLE):
            icon_rect = self._icon_rect(option)
            self._icon.paint(painter, icon_rect)

    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        from .catalog_tree import DIRTY_PROVIDER_ROLE
        if index.data(DIRTY_PROVIDER_ROLE):
            size.setWidth(size.width() + self._icon_size + 4)
        return size

    def _icon_rect(self, option):
        return QRect(
            option.rect.right() - self._icon_size - 2,
            option.rect.top() + (option.rect.height() - self._icon_size) // 2,
            self._icon_size,
            self._icon_size,
        )

    def editorEvent(self, event, model, option, index):
        from .catalog_tree import DIRTY_PROVIDER_ROLE
        if index.data(DIRTY_PROVIDER_ROLE):
            if event.type() == QEvent.Type.MouseButtonRelease:
                if self._icon_rect(option).contains(event.pos()):
                    self.save_clicked.emit(index)
                    return True
        return super().editorEvent(event, model, option, index)
```

Wire the delegate in `CatalogBrowser.__init__` after creating the tree view:

```python
self._save_delegate = _SaveButtonDelegate(self._catalog_tree)
self._save_delegate.save_clicked.connect(self._on_save_clicked)
self._catalog_tree.setItemDelegate(self._save_delegate)
```

Add handler:

```python
def _on_save_clicked(self, proxy_index: QModelIndex) -> None:
    source_index = self._proxy_model.mapToSource(proxy_index)
    node = self._tree_model.node_from_index(source_index)
    if node.provider is not None:
        node.provider.save()
```

**Step 2: Run existing tests**

Run: `uv run pytest tests/test_catalog_dirty_state.py tests/test_panel_catalog_manager.py -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_tree.py SciQLop/components/catalogs/ui/catalog_browser.py
git commit -m "feat(catalogs): add save button delegate to dirty provider nodes"
```

---

### Task 9: Add save action to context menu

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_browser.py`

**Step 1: Add context menu to tree view**

In `CatalogBrowser.__init__`, enable custom context menu on the tree:

```python
self._catalog_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
self._catalog_tree.customContextMenuRequested.connect(self._on_tree_context_menu)
```

Add handler:

```python
def _on_tree_context_menu(self, pos) -> None:
    proxy_index = self._catalog_tree.indexAt(pos)
    if not proxy_index.isValid():
        return
    source_index = self._proxy_model.mapToSource(proxy_index)
    node = self._tree_model.node_from_index(source_index)
    if node.provider is None:
        return

    from ..backend.provider import Capability
    has_save = Capability.SAVE in node.provider.capabilities()

    menu = QMenu(self)

    if has_save and node.provider.is_dirty():
        if node.catalog is not None and Capability.SAVE_CATALOG in node.provider.capabilities():
            save_action = menu.addAction("Save Catalog")
            save_action.triggered.connect(lambda: node.provider.save_catalog(node.catalog))
        else:
            save_action = menu.addAction("Save")
            save_action.triggered.connect(lambda: node.provider.save())

    if menu.isEmpty():
        return
    menu.exec(self._catalog_tree.viewport().mapToGlobal(pos))
```

**Step 2: Run existing tests**

Run: `uv run pytest tests/test_catalog_dirty_state.py tests/test_panel_catalog_manager.py -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_browser.py
git commit -m "feat(catalogs): add save action to tree context menu"
```

---

### Task 10: Final integration test

**Files:**
- Test: `tests/test_catalog_dirty_state.py`

**Step 1: Write an end-to-end test**

```python
# Append to tests/test_catalog_dirty_state.py
def test_full_dirty_save_cycle(qtbot, qapp):
    """End-to-end: edit event -> dirty -> save -> clean."""
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    event = provider.events(cat)[0]

    # Initially clean
    assert not provider.is_dirty()

    # Edit event -> dirty
    event.start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    assert provider.is_dirty(cat)

    # Add event -> still dirty
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    import uuid as _uuid
    new_event = CatalogEvent(
        uuid=str(_uuid.uuid4()),
        start=datetime(2025, 2, 1, tzinfo=timezone.utc),
        stop=datetime(2025, 2, 2, tzinfo=timezone.utc),
    )
    provider.add_event(cat, new_event)
    assert provider.is_dirty(cat)

    # Save -> clean
    provider.save()
    assert not provider.is_dirty()
    assert not provider.is_dirty(cat)
```

**Step 2: Run all tests**

Run: `uv run pytest tests/test_catalog_dirty_state.py -v`
Expected: ALL PASS

**Step 3: Run full test suite**

Run: `uv run pytest -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add tests/test_catalog_dirty_state.py
git commit -m "test(catalogs): add full dirty-save cycle integration test"
```
