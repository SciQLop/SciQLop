# Catalog Code Cleanup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix signal connection leaks, re-entrancy bugs, and missing cleanup in the catalog feature code.

**Architecture:** Seven independent fixes targeting provider signal lifecycle, action filtering, browser state tracking, tree model cleanup, panel lifecycle, deferred load guards, and minor cleanups.

**Tech Stack:** PySide6/Qt signals, Python dataclasses, tscat

---

### Task 1: Fix `_set_events` signal accumulation in CatalogProvider

The base `_set_events` connects `range_changed` on every call without disconnecting old connections. With event reuse, events accumulate N connections after N reloads. Track connections per event UUID and disconnect before reconnecting.

**Files:**
- Modify: `SciQLop/components/catalogs/backend/provider.py:90-124`

**Step 1: Add `_range_connections` dict to `__init__`**

In `CatalogProvider.__init__` (line 90), add a dict to track per-event range_changed connections:

```python
def __init__(self, name: str, parent: QObject | None = None):
    super().__init__(parent)
    self._name = name
    self._events: dict[str, list[CatalogEvent]] = {}
    self._dirty_catalogs: set[str] = set()
    self._range_connections: dict[str, list[tuple]] = {}  # catalog_uuid -> [(event, slot), ...]
    from .registry import CatalogRegistry
    CatalogRegistry.instance().register(self)
```

**Step 2: Disconnect old connections in `_set_events`**

Replace `_set_events` (lines 121-124) with:

```python
def _set_events(self, catalog: Catalog, events: list[CatalogEvent]) -> None:
    # Disconnect old range_changed connections
    for event, slot in self._range_connections.pop(catalog.uuid, []):
        try:
            event.range_changed.disconnect(slot)
        except RuntimeError:
            pass
    self._events[catalog.uuid] = sorted(events, key=lambda e: e.start)
    connections = []
    for event in self._events[catalog.uuid]:
        slot = lambda ev=event, cat=catalog: self._on_event_range_changed(ev, cat)
        event.range_changed.connect(slot)
        connections.append((event, slot))
    self._range_connections[catalog.uuid] = connections
```

**Step 3: Update `_add_event` to track its connection too**

Replace `_add_event` (lines 126-131) with:

```python
def _add_event(self, catalog: Catalog, event: CatalogEvent) -> None:
    if catalog.uuid not in self._events:
        self._events[catalog.uuid] = []
    bisect.insort(self._events[catalog.uuid], event, key=lambda e: e.start)
    slot = lambda ev=event, cat=catalog: self._on_event_range_changed(ev, cat)
    event.range_changed.connect(slot)
    if catalog.uuid not in self._range_connections:
        self._range_connections[catalog.uuid] = []
    self._range_connections[catalog.uuid].append((event, slot))
    self.events_changed.emit(catalog)
```

**Step 4: Disconnect in `_remove_event`**

Replace `_remove_event` (lines 133-139) with:

```python
def _remove_event(self, catalog: Catalog, event: CatalogEvent) -> None:
    event_list = self._events.get(catalog.uuid, [])
    try:
        event_list.remove(event)
    except ValueError:
        pass
    # Disconnect this event's range_changed slot
    conns = self._range_connections.get(catalog.uuid, [])
    self._range_connections[catalog.uuid] = [
        (e, s) for e, s in conns if e is not event
    ]
    for e, s in conns:
        if e is event:
            try:
                e.range_changed.disconnect(s)
            except RuntimeError:
                pass
    self.events_changed.emit(catalog)
```

**Step 5: Clean up connections in `remove_catalog`**

Replace `remove_catalog` (lines 151-155) with:

```python
def remove_catalog(self, catalog: Catalog) -> None:
    """Public API: remove a catalog. Override for backend persistence."""
    for event, slot in self._range_connections.pop(catalog.uuid, []):
        try:
            event.range_changed.disconnect(slot)
        except RuntimeError:
            pass
    self._events.pop(catalog.uuid, None)
    self._dirty_catalogs.discard(catalog.uuid)
    self.catalog_removed.emit(catalog)
```

**Step 6: Run tests**

Run: `uv run pytest tests/ -x -q`

**Step 7: Commit**

```
fix(catalogs): track and disconnect range_changed connections in CatalogProvider
```

---

### Task 2: Filter `_on_action_done` to skip `SetAttributeAction`

Every drag step triggers `_apply_changes` → `SetAttributeAction` → `_on_action_done` → full catalog event reload. This is wasteful and compounds the signal accumulation. `SetAttributeAction` only updates individual event attributes — no need to reload the entire event list.

**Files:**
- Modify: `SciQLop/plugins/tscat_catalogs/tscat_provider.py:228-234`

**Step 1: Filter by action type**

Replace `_on_action_done` (lines 228-234) with:

```python
@Slot()
def _on_action_done(self, action) -> None:
    # SetAttributeAction only updates existing event fields (start/stop);
    # the TscatEvent objects already reflect those changes locally.
    # No need to reload the entire event list.
    if isinstance(action, SetAttributeAction):
        return
    self._catalog_cache = None
    for catalog in self.catalogs():
        if catalog.uuid in self._events:
            self._stale_events[catalog.uuid] = self._events.pop(catalog.uuid)
            self.events_changed.emit(catalog)
```

**Step 2: Run tests**

Run: `uv run pytest tests/ -x -q`

**Step 3: Commit**

```
perf(catalogs): skip full event reload on SetAttributeAction in _on_action_done
```

---

### Task 3: Fix `events_changed` leak when switching catalogs in browser

When the user selects a non-catalog node (folder/provider), `_current_provider` is updated but no signal was connected. The next catalog selection disconnects from the wrong provider, leaking the real connection.

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_browser.py:97-214`

**Step 1: Add dedicated tracking field**

In `CatalogBrowser.__init__` (around line 101), add:

```python
self._events_changed_provider: CatalogProvider | None = None
```

**Step 2: Replace disconnect/connect logic in `_on_catalog_selected`**

Replace `_on_catalog_selected` (lines 182-202) with:

```python
def _on_catalog_selected(self, current: QModelIndex, previous: QModelIndex) -> None:
    source_index = self._proxy_model.mapToSource(current)
    node = self._tree_model.node_from_index(source_index)
    if node is self._tree_model._root:
        return
    # Disconnect from previously connected provider
    if self._events_changed_provider is not None:
        try:
            self._events_changed_provider.events_changed.disconnect(self._on_events_changed)
        except RuntimeError:
            pass
        self._events_changed_provider = None
    if node.catalog is not None:
        self._current_provider = node.provider
        self._current_catalog = node.catalog
        events = node.provider.events(node.catalog)
        self._event_model.set_events(events)
        node.provider.events_changed.connect(self._on_events_changed)
        self._events_changed_provider = node.provider
    else:
        self._current_provider = node.provider
        self._current_catalog = None
        self._event_model.clear()
    self._update_toolbar()
```

**Step 3: Run tests**

Run: `uv run pytest tests/ -x -q`

**Step 4: Commit**

```
fix(catalogs): track actually-connected provider to prevent events_changed signal leak
```

---

### Task 4: Disconnect provider signals on unregister in tree model

When a provider is unregistered, the lambdas connected to `catalog_added`, `catalog_removed`, and `dirty_changed` remain active. If the provider later emits, handlers crash on detached nodes.

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_tree.py:67-109`

**Step 1: Store provider signal connections**

In `_add_provider_node` (lines 67-81), store the lambdas and return them alongside the node. Add a dict to track them:

Add to `CatalogTreeModel.__init__` (after line 42):

```python
self._provider_connections: dict[int, list[tuple]] = {}  # id(provider) -> [(signal, slot), ...]
```

Replace lines 77-81 of `_add_provider_node`:

```python
    # Connect to provider signals for dynamic updates
    on_added = lambda cat, p=provider, n=node: self._on_catalog_added(p, n, cat)
    on_removed = lambda cat, p=provider, n=node: self._on_catalog_removed(p, n, cat)
    on_dirty = lambda cat, dirty, p=provider, n=node: self._on_dirty_changed(p, n, cat, dirty)
    provider.catalog_added.connect(on_added)
    provider.catalog_removed.connect(on_removed)
    provider.dirty_changed.connect(on_dirty)
    self._provider_connections[id(provider)] = [
        (provider.catalog_added, on_added),
        (provider.catalog_removed, on_removed),
        (provider.dirty_changed, on_dirty),
    ]
    return node
```

**Step 2: Disconnect in `_on_provider_unregistered`**

Replace `_on_provider_unregistered` (lines 102-109) with:

```python
def _on_provider_unregistered(self, provider: object) -> None:
    node = self._provider_node(provider)
    if node is None:
        return
    for signal, slot in self._provider_connections.pop(id(provider), []):
        try:
            signal.disconnect(slot)
        except RuntimeError:
            pass
    row = node.row()
    self.beginRemoveRows(QModelIndex(), row, row)
    self._root.children.remove(node)
    self.endRemoveRows()
```

**Step 3: Emit correct role in `_on_dirty_changed`**

Replace the `dataChanged` emit calls in `_on_dirty_changed` (lines 111-117) to include `DIRTY_PROVIDER_ROLE`:

```python
def _on_dirty_changed(self, provider: CatalogProvider, pnode: _Node, catalog: object, is_dirty: bool) -> None:
    cat_node = self._find_catalog_node(pnode, catalog)
    if cat_node is not None:
        idx = self.createIndex(cat_node.row(), 0, cat_node)
        self.dataChanged.emit(idx, idx, [Qt.ItemDataRole.DisplayRole])
    pnode_idx = self.createIndex(pnode.row(), 0, pnode)
    self.dataChanged.emit(pnode_idx, pnode_idx, [Qt.ItemDataRole.DisplayRole, DIRTY_PROVIDER_ROLE])
```

**Step 4: Run tests**

Run: `uv run pytest tests/ -x -q`

**Step 5: Commit**

```
fix(catalogs): disconnect provider signals on unregister and emit correct dirty role
```

---

### Task 5: Add panel-destroyed handler and double-registration guard

If a panel is destroyed without `disconnect_from_panel`, accessing `_panels[0].time_range` crashes. Also, `connect_to_panel` has no guard against connecting the same panel twice.

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_browser.py:248-261`

**Step 1: Replace `connect_to_panel` and `disconnect_from_panel`**

```python
def connect_to_panel(self, panel) -> None:
    """Wire bidirectional event selection between this browser and a panel."""
    if panel in self._panels:
        return
    self._panels.append(panel)
    manager = panel.catalog_manager
    self.event_selected.connect(manager.select_event)
    manager.event_clicked.connect(self.highlight_event)
    panel.destroyed.connect(lambda: self._on_panel_destroyed(panel))

def _on_panel_destroyed(self, panel) -> None:
    if panel in self._panels:
        self._panels.remove(panel)

def disconnect_from_panel(self, panel) -> None:
    """Remove bidirectional event selection wiring for a panel."""
    if panel not in self._panels:
        return
    self._panels.remove(panel)
    manager = panel.catalog_manager
    try:
        self.event_selected.disconnect(manager.select_event)
    except RuntimeError:
        pass
    try:
        manager.event_clicked.disconnect(self.highlight_event)
    except RuntimeError:
        pass
```

**Step 2: Run tests**

Run: `uv run pytest tests/ -x -q`

**Step 3: Commit**

```
fix(catalogs): add panel-destroyed handler and double-registration guard
```

---

### Task 6: Guard `_deferred_load` against concurrent chains

If `_on_action_done` fires while a `_deferred_load` is already polling, a second chain starts. Track in-flight loads and skip duplicates.

**Files:**
- Modify: `SciQLop/plugins/tscat_catalogs/tscat_provider.py:96-189`

**Step 1: Add `_loading_uuids` set to `__init__`**

In `TscatCatalogProvider.__init__` (line 96), add:

```python
self._loading_uuids: set[str] = set()
```

**Step 2: Guard `_deferred_load`**

Replace `_deferred_load` (lines 181-189) with:

```python
def _deferred_load(self, catalog: Catalog, catalog_model, retries: int) -> None:
    if catalog.uuid in self._loading_uuids and retries == 50:
        return  # already loading
    self._loading_uuids.add(catalog.uuid)
    if catalog_model.rowCount() > 0:
        self._loading_uuids.discard(catalog.uuid)
        self._read_events_from_model(catalog, catalog_model)
    elif retries > 0:
        QTimer.singleShot(100, lambda: self._deferred_load(catalog, catalog_model, retries - 1))
    else:
        self._loading_uuids.discard(catalog.uuid)
        self.error_occurred.emit(f"Timeout loading events for {catalog.name}")
        self._set_events(catalog, [])
        self.events_changed.emit(catalog)
```

**Step 3: Run tests**

Run: `uv run pytest tests/ -x -q`

**Step 4: Commit**

```
fix(catalogs): guard _deferred_load against concurrent retry chains
```

---

### Task 7: Minor cleanups

**Files:**
- Modify: `SciQLop/components/catalogs/backend/overlay.py:146-149`
- Modify: `SciQLop/components/catalogs/ui/catalog_browser.py:1-17,243`
- Modify: `SciQLop/plugins/tscat_catalogs/catalogs.py:1`

**Step 1: Use property setters in `_on_span_range_changed`**

Replace overlay.py lines 146-149:

```python
def _on_span_range_changed(self, new_range: TimeRange, event: CatalogEvent) -> None:
    event.start = make_utc_datetime(new_range.datetime_start())
    event.stop = make_utc_datetime(new_range.datetime_stop())
```

The `sync_source` guard in `_add_span` already prevents the feedback loop. Using setters respects the equality check, avoiding spurious `range_changed` emissions. The setters emit `range_changed` individually per property, so this emits up to 2 signals instead of the old 1, but the debounce timer absorbs them.

**Step 2: Move inline import to module level**

In catalog_browser.py, add `QItemSelectionModel` to the top-level import (line 3):

```python
from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Signal, QRect, QEvent, QItemSelectionModel
```

Remove the inline import at line 243 (`from PySide6.QtCore import QItemSelectionModel`).

**Step 3: Modernize typing in catalogs.py**

Replace line 1 of `catalogs.py`:

```python
from __future__ import annotations
```

Remove `from typing import List, Tuple` (line 1) and replace `List[str]` with `list[str]` and `List[Tuple[datetime, datetime]]` with `list[tuple[datetime, datetime]]` in the type annotations on lines 52 and 55.

**Step 4: Run tests**

Run: `uv run pytest tests/ -x -q`

**Step 5: Commit**

```
refactor(catalogs): use property setters in overlay, move inline imports, modernize typing
```
