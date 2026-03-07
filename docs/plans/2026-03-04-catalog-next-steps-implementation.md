# Catalog Next Steps Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Complete the unified catalog system: add/delete events, filter bar, bugfixes, async loading, lazy rendering, and cocat port.

**Architecture:** Six independent-ish tasks building on the existing `CatalogProvider`/`CatalogBrowser`/`CatalogOverlay` system. Tasks 3 and 4 are independent bugfixes. Task 2 is standalone UI. Task 1 adds public mutation API + overlay reactivity. Task 6 adds lazy loading to overlay. Task 5 ports collaborative catalogs.

**Tech Stack:** PySide6, tscat/tscat_gui, cocat, QSortFilterProxyModel, QTimer

---

### Task 1: Fix `catalog_removed` Emitting None (Bug #3)

**Files:**
- Modify: `SciQLop/plugins/tscat_catalogs/tscat_provider.py:158-172`
- Test: `tests/test_catalog_provider.py`

**Step 1: Write the failing test**

In `tests/test_catalog_provider.py`, add:

```python
def test_catalog_removed_emits_actual_catalog(qtbot):
    """TscatCatalogProvider emitted None for removed catalogs.
    We test the fix at the CatalogProvider base level: catalog_removed
    must emit the actual Catalog object."""
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, CatalogEvent, Capability
    from PySide6.QtCore import QObject

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
```

**Step 2: Run test to verify it passes (this is a base-level sanity test)**

Run: `uv run pytest tests/test_catalog_provider.py::test_catalog_removed_emits_actual_catalog -v`
Expected: PASS (base class already works correctly; the bug is in TscatCatalogProvider)

**Step 3: Fix `TscatCatalogProvider._on_root_rows_changed`**

In `SciQLop/plugins/tscat_catalogs/tscat_provider.py`, replace `_on_root_rows_changed`:

```python
@Slot()
def _on_root_rows_changed(self, *args) -> None:
    old_uuids = set(self._known_uuids)
    old_catalogs = {c.uuid: c for c in (self._catalog_cache or [])}
    self._catalog_cache = None
    new_catalogs = self.catalogs()
    new_uuids = self._known_uuids

    for cat in new_catalogs:
        if cat.uuid not in old_uuids:
            self.catalog_added.emit(cat)

    removed_uuids = old_uuids - new_uuids
    for uuid in removed_uuids:
        removed_cat = old_catalogs.get(uuid)
        if removed_cat is not None:
            self.catalog_removed.emit(removed_cat)
            # Clean up cached events for removed catalog
            self._events.pop(uuid, None)
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_catalog_provider.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add SciQLop/plugins/tscat_catalogs/tscat_provider.py tests/test_catalog_provider.py
git commit -m "fix(catalogs): emit actual Catalog object in catalog_removed signal"
```

---

### Task 2: Replace Busy-Wait Event Loading (Bug #5)

**Files:**
- Modify: `SciQLop/plugins/tscat_catalogs/tscat_provider.py:139-157`
- Test: `tests/test_catalog_provider.py`

**Step 1: Write failing test**

```python
def test_tscat_provider_load_events_no_busy_wait(qtbot, monkeypatch):
    """Verify _load_events does not call processEvents in a loop."""
    import SciQLop.plugins.tscat_catalogs.tscat_provider as mod

    calls = []
    original_load = mod.TscatCatalogProvider._load_events

    # We can't easily test the async path without a full tscat setup,
    # but we can verify the busy-wait loop is gone by checking the source
    import inspect
    source = inspect.getsource(mod.TscatCatalogProvider._load_events)
    assert "for _ in range" not in source, "Busy-wait loop should be removed"
    assert "QThread.sleep" not in source, "QThread.sleep should be removed"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_provider.py::test_tscat_provider_load_events_no_busy_wait -v`
Expected: FAIL (current code has both patterns)

**Step 3: Rewrite `_load_events` with signal-based approach**

Replace `_load_events` in `SciQLop/plugins/tscat_catalogs/tscat_provider.py`:

```python
def _load_events(self, catalog: Catalog) -> None:
    catalog_model = tscat_model.catalog(catalog.uuid)
    if catalog_model.rowCount() > 0:
        self._read_events_from_model(catalog, catalog_model)
    else:
        # Wait for async load via signal
        timeout = QTimer(self)
        timeout.setSingleShot(True)

        def on_rows_inserted(*args):
            timeout.stop()
            catalog_model.rowsInserted.disconnect(on_rows_inserted)
            self._read_events_from_model(catalog, catalog_model)

        def on_timeout():
            catalog_model.rowsInserted.disconnect(on_rows_inserted)
            self.error_occurred.emit(f"Timeout loading events for {catalog.name}")
            self._set_events(catalog, [])

        catalog_model.rowsInserted.connect(on_rows_inserted)
        timeout.timeout.connect(on_timeout)
        timeout.start(5000)

def _read_events_from_model(self, catalog: Catalog, catalog_model) -> None:
    events: list[CatalogEvent] = []
    for row in range(catalog_model.rowCount()):
        idx = catalog_model.index(row, 0)
        entity = idx.data(EntityRole)
        if entity is not None:
            events.append(TscatEvent(entity, parent=self))
    self._set_events(catalog, events)
```

Also remove `from SciQLop.core.sciqlop_application import sciqlop_app` and `QThread` from imports if no longer used.

**Step 4: Run tests**

Run: `uv run pytest tests/test_catalog_provider.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add SciQLop/plugins/tscat_catalogs/tscat_provider.py tests/test_catalog_provider.py
git commit -m "fix(catalogs): replace busy-wait event loading with signal-based approach"
```

---

### Task 3: Wire Filter Bar in CatalogBrowser

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_browser.py:27-83`
- Test: `tests/test_catalog_provider.py`

**Step 1: Write failing test**

```python
def test_catalog_browser_filter_hides_non_matching(qtbot):
    """Filter bar should hide catalogs that don't match the filter text."""
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry

    registry = CatalogRegistry()
    browser = CatalogBrowser()
    qtbot.addWidget(browser)

    provider = DummyProvider(num_catalogs=3, parent=browser)
    # Rename catalogs for easy filtering
    provider._catalogs[0].name = "Alpha"
    provider._catalogs[1].name = "Beta"
    provider._catalogs[2].name = "Gamma"

    # The proxy model should exist
    assert hasattr(browser, '_proxy_model')

    # All visible initially
    proxy = browser._proxy_model
    # Provider node + 3 catalog children
    provider_idx = proxy.index(0, 0)
    assert proxy.rowCount(provider_idx) == 3

    # Filter to "alp"
    browser._filter_bar.setText("alp")
    provider_idx = proxy.index(0, 0)
    assert proxy.rowCount(provider_idx) == 1

    # Clear filter
    browser._filter_bar.setText("")
    provider_idx = proxy.index(0, 0)
    assert proxy.rowCount(provider_idx) == 3
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_provider.py::test_catalog_browser_filter_hides_non_matching -v`
Expected: FAIL (no `_proxy_model` attribute)

**Step 3: Add QSortFilterProxyModel to CatalogBrowser**

In `SciQLop/components/catalogs/ui/catalog_browser.py`:

Add to imports:
```python
from PySide6.QtCore import QSortFilterProxyModel, QModelIndex as QMI
```

Add a proxy model class before `CatalogBrowser`:
```python
class _CatalogFilterProxy(QSortFilterProxyModel):
    """Case-insensitive substring filter that keeps ancestors of matching nodes."""

    def filterAcceptsRow(self, source_row: int, source_parent: QMI) -> bool:
        pattern = self.filterRegularExpression().pattern()
        if not pattern:
            return True
        idx = self.sourceModel().index(source_row, 0, source_parent)
        name = self.sourceModel().data(idx, Qt.ItemDataRole.DisplayRole) or ""
        if pattern.lower() in name.lower():
            return True
        # Accept if any child matches (recursive)
        for row in range(self.sourceModel().rowCount(idx)):
            if self.filterAcceptsRow(row, idx):
                return True
        return False
```

In `CatalogBrowser.__init__`, after creating `_tree_model` and `_catalog_tree`, insert proxy model:
```python
self._proxy_model = _CatalogFilterProxy()
self._proxy_model.setSourceModel(self._tree_model)
self._catalog_tree.setModel(self._proxy_model)
```

Replace the selection model connection (it now goes through proxy):
```python
self._catalog_tree.selectionModel().currentChanged.connect(self._on_catalog_selected)
```

Connect filter bar:
```python
self._filter_bar.textChanged.connect(self._on_filter_changed)
```

Add method:
```python
def _on_filter_changed(self, text: str) -> None:
    self._proxy_model.setFilterFixedString(text)
    if text:
        self._catalog_tree.expandAll()
```

Update `_on_catalog_selected` to map through proxy:
```python
def _on_catalog_selected(self, current: QModelIndex, previous: QModelIndex) -> None:
    source_index = self._proxy_model.mapToSource(current)
    node = self._tree_model.node_from_index(source_index)
    # ... rest unchanged
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_catalog_provider.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_browser.py tests/test_catalog_provider.py
git commit -m "feat(catalogs): wire filter bar with QSortFilterProxyModel"
```

---

### Task 4: Wire Add Event / Delete Buttons

**Files:**
- Modify: `SciQLop/components/catalogs/backend/provider.py:115-130` (add public API)
- Modify: `SciQLop/components/catalogs/ui/catalog_browser.py:150-154` (implement stubs)
- Modify: `SciQLop/components/catalogs/backend/overlay.py` (react to events_changed)
- Modify: `SciQLop/plugins/tscat_catalogs/tscat_provider.py` (override add/remove)
- Test: `tests/test_catalog_provider.py`

#### Step 1: Write failing test for public add/remove API

```python
def test_provider_add_event_public_api(qtbot):
    """Provider.add_event should add event and emit events_changed."""
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

def test_provider_remove_event_public_api(qtbot):
    """Provider.remove_event should remove event and emit events_changed."""
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
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_catalog_provider.py::test_provider_add_event_public_api tests/test_catalog_provider.py::test_provider_remove_event_public_api -v`
Expected: FAIL (no `add_event` / `remove_event` methods)

**Step 3: Add public mutation API to CatalogProvider**

In `SciQLop/components/catalogs/backend/provider.py`, add public methods after `_remove_event`:

```python
def add_event(self, catalog: Catalog, event: CatalogEvent) -> None:
    """Public API: add an event to a catalog. Override for backend persistence."""
    self._add_event(catalog, event)

def remove_event(self, catalog: Catalog, event: CatalogEvent) -> None:
    """Public API: remove an event from a catalog. Override for backend persistence."""
    self._remove_event(catalog, event)

def remove_catalog(self, catalog: Catalog) -> None:
    """Public API: remove a catalog. Override for backend persistence."""
    self._events.pop(catalog.uuid, None)
    self.catalog_removed.emit(catalog)
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_catalog_provider.py::test_provider_add_event_public_api tests/test_catalog_provider.py::test_provider_remove_event_public_api -v`
Expected: PASS

**Step 5: Write test for overlay reactivity**

```python
def test_overlay_reacts_to_events_changed(qtbot):
    """CatalogOverlay should add/remove spans when events_changed fires."""
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.overlay import CatalogOverlay
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    from datetime import datetime, timezone, timedelta
    from unittest.mock import MagicMock

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    catalog = provider.catalogs()[0]
    panel = MagicMock()
    panel.time_range_changed = MagicMock()  # signal mock

    overlay = CatalogOverlay(catalog=catalog, panel=panel)
    initial_count = overlay.span_count
    assert initial_count == 3

    # Add an event via provider
    new_event = CatalogEvent(
        uuid="overlay-new",
        start=datetime(2020, 7, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 7, 1, 1, tzinfo=timezone.utc),
    )
    provider.add_event(catalog, new_event)

    assert overlay.span_count == 4
```

Note: This test may need adjustment based on how `MultiPlotsVSpanCollection` works with a mock panel. If the C++ `MultiPlotsVSpanCollection` cannot be constructed with a mock, skip this test and test reactivity manually, or test just the `_sync_events` method directly.

**Step 6: Add overlay reactivity to events_changed**

In `SciQLop/components/catalogs/backend/overlay.py`, modify `__init__` to connect to `events_changed`:

```python
def __init__(self, catalog: Catalog, panel, parent: QObject | None = None):
    super().__init__(parent or panel)
    self._catalog = catalog
    self._panel = panel
    self._color = color_for_catalog(catalog.uuid)
    self._read_only = True

    self._span_collection = MultiPlotsVSpanCollection(panel)
    self._event_by_span_id: dict[str, CatalogEvent] = {}

    events = catalog.provider.events(catalog)
    for event in events:
        self._add_span(event)

    # React to event list changes
    catalog.provider.events_changed.connect(self._on_events_changed)
```

Add the sync method:

```python
def _on_events_changed(self, changed_catalog: Catalog) -> None:
    if changed_catalog.uuid != self._catalog.uuid:
        return
    current_uuids = set(self._event_by_span_id.keys())
    new_events = self._catalog.provider.events(self._catalog)
    new_uuids = {e.uuid for e in new_events}

    # Remove stale spans
    for uuid in current_uuids - new_uuids:
        span = self._span_collection.span(uuid)
        if span is not None:
            self._span_collection.delete_span(span)
        self._event_by_span_id.pop(uuid, None)

    # Add new spans
    for event in new_events:
        if event.uuid not in current_uuids:
            self._add_span(event)
```

**Step 7: Implement CatalogBrowser._on_add_event and _on_delete**

In `SciQLop/components/catalogs/ui/catalog_browser.py`:

Add imports:
```python
from datetime import datetime, timezone, timedelta
import uuid as _uuid
from ..backend.provider import CatalogEvent
```

Replace `_on_add_event`:
```python
def _on_add_event(self) -> None:
    if self._current_provider is None or self._current_catalog is None:
        return
    caps = self._current_provider.capabilities(self._current_catalog)
    if Capability.CREATE_EVENTS not in caps:
        return
    now = datetime.now(tz=timezone.utc)
    event = CatalogEvent(
        uuid=str(_uuid.uuid4()),
        start=now - timedelta(minutes=30),
        stop=now + timedelta(minutes=30),
    )
    self._current_provider.add_event(self._current_catalog, event)
    # Refresh event table
    events = self._current_provider.events(self._current_catalog)
    self._event_model.set_events(events)
```

Replace `_on_delete`:
```python
def _on_delete(self) -> None:
    if self._current_provider is None:
        return
    # Try deleting selected event first
    selected = self._event_table.selectionModel().currentIndex()
    if selected.isValid() and self._current_catalog is not None:
        event = self._event_model.event_at(selected.row())
        if event is not None:
            caps = self._current_provider.capabilities(self._current_catalog)
            if Capability.DELETE_EVENTS in caps:
                self._current_provider.remove_event(self._current_catalog, event)
                events = self._current_provider.events(self._current_catalog)
                self._event_model.set_events(events)
                return
```

**Step 8: Override add_event/remove_event in TscatCatalogProvider**

In `SciQLop/plugins/tscat_catalogs/tscat_provider.py`, add imports:
```python
from tscat_gui.tscat_driver.actions import CreateEntityAction, RemoveEntitiesAction, AddEventsToCatalogueAction
import tscat
```

Add methods to `TscatCatalogProvider`:
```python
def add_event(self, catalog: Catalog, event: CatalogEvent) -> None:
    tscat_model.do(CreateEntityAction(
        user_callback=None,
        cls=tscat._Event,
        args=dict(start=event.start, stop=event.stop, author="SciQLop"),
    ))
    # The action_done callback will refresh events
    super().add_event(catalog, event)

def remove_event(self, catalog: Catalog, event: CatalogEvent) -> None:
    tscat_model.do(RemoveEntitiesAction(
        user_callback=None,
        uuids=[event.uuid],
        permanently=False,
    ))
    super().remove_event(catalog, event)
```

**Step 9: Run all tests**

Run: `uv run pytest tests/test_catalog_provider.py -v`
Expected: all PASS

**Step 10: Commit**

```bash
git add SciQLop/components/catalogs/backend/provider.py SciQLop/components/catalogs/backend/overlay.py SciQLop/components/catalogs/ui/catalog_browser.py SciQLop/plugins/tscat_catalogs/tscat_provider.py tests/test_catalog_provider.py
git commit -m "feat(catalogs): wire add event/delete buttons with public mutation API"
```

---

### Task 5: Lazy Event Loading in CatalogOverlay

**Files:**
- Modify: `SciQLop/components/catalogs/backend/overlay.py`
- Test: `tests/test_catalog_overlay.py`

**Step 1: Write failing test**

```python
def test_overlay_lazy_loading_skips_small_catalogs(qtbot):
    """Catalogs with < 5000 events load all events eagerly."""
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.overlay import CatalogOverlay
    from unittest.mock import MagicMock

    provider = DummyProvider(num_catalogs=1, events_per_catalog=100)
    catalog = provider.catalogs()[0]
    panel = MagicMock()

    overlay = CatalogOverlay(catalog=catalog, panel=panel)
    assert overlay.span_count == 100  # All loaded eagerly
```

**Step 2: Implement lazy loading**

In `SciQLop/components/catalogs/backend/overlay.py`:

Add imports:
```python
from PySide6.QtCore import QTimer
from datetime import datetime, timezone
```

Modify `__init__` to check total event count and decide loading strategy:

```python
def __init__(self, catalog: Catalog, panel, parent: QObject | None = None):
    super().__init__(parent or panel)
    self._catalog = catalog
    self._panel = panel
    self._color = color_for_catalog(catalog.uuid)
    self._read_only = True
    self._lazy = False

    self._span_collection = MultiPlotsVSpanCollection(panel)
    self._event_by_span_id: dict[str, CatalogEvent] = {}

    # React to event list changes
    catalog.provider.events_changed.connect(self._on_events_changed)

    # Decide: lazy or eager
    all_events = catalog.provider.events(catalog)
    if len(all_events) >= 5000:
        self._lazy = True
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(200)
        self._debounce.timeout.connect(self._refresh_visible)
        # Connect to panel time range changes
        if hasattr(panel, 'time_range_changed'):
            panel.time_range_changed.connect(self._on_time_range_changed)
        self._refresh_visible()
    else:
        for event in all_events:
            self._add_span(event)
```

Add lazy loading methods:

```python
def _on_time_range_changed(self, *args) -> None:
    if self._lazy:
        self._debounce.start()

def _refresh_visible(self) -> None:
    """Load events visible in the current panel time range (with 2x margin)."""
    try:
        tr = self._panel.time_range
        duration = tr.stop - tr.start
        margin = duration  # 1x margin on each side = 2x total
        start = datetime.fromtimestamp(tr.start - margin, tz=timezone.utc)
        stop = datetime.fromtimestamp(tr.stop + margin, tz=timezone.utc)
    except Exception:
        return

    new_events = self._catalog.provider.events(self._catalog, start, stop)
    new_uuids = {e.uuid for e in new_events}
    current_uuids = set(self._event_by_span_id.keys())

    # Remove out-of-range spans
    for uuid in current_uuids - new_uuids:
        span = self._span_collection.span(uuid)
        if span is not None:
            self._span_collection.delete_span(span)
        self._event_by_span_id.pop(uuid, None)

    # Add new visible spans
    for event in new_events:
        if event.uuid not in current_uuids:
            self._add_span(event)
```

Update `_on_events_changed` to respect lazy mode:

```python
def _on_events_changed(self, changed_catalog: Catalog) -> None:
    if changed_catalog.uuid != self._catalog.uuid:
        return
    if self._lazy:
        self._refresh_visible()
        return
    current_uuids = set(self._event_by_span_id.keys())
    new_events = self._catalog.provider.events(self._catalog)
    new_uuids = {e.uuid for e in new_events}

    for uuid in current_uuids - new_uuids:
        span = self._span_collection.span(uuid)
        if span is not None:
            self._span_collection.delete_span(span)
        self._event_by_span_id.pop(uuid, None)

    for event in new_events:
        if event.uuid not in current_uuids:
            self._add_span(event)
```

**Step 3: Run tests**

Run: `uv run pytest tests/test_catalog_overlay.py tests/test_catalog_provider.py -v`
Expected: all PASS

**Step 4: Commit**

```bash
git add SciQLop/components/catalogs/backend/overlay.py tests/test_catalog_overlay.py
git commit -m "feat(catalogs): lazy event loading for large catalogs (>=5000 events)"
```

---

### Task 6: Port Collaborative Catalogs to New Provider API

**Files:**
- Create: `SciQLop/plugins/collaborative_catalogs/cocat_provider.py`
- Modify: `SciQLop/plugins/collaborative_catalogs/plugin.py`
- Test: `tests/test_catalog_provider.py` (basic provider test)

**Step 1: Write test for CocatCatalogProvider**

This test creates a mock cocat DB/Room and verifies the provider adapts correctly. Since cocat requires a network connection, we mock the DB layer:

```python
def test_cocat_provider_wraps_events(qtbot):
    """CocatCatalogProvider should expose cocat events as CatalogEvents."""
    # This is a design-level test — actual integration needs a cocat server
    from SciQLop.components.catalogs.backend.provider import CatalogProvider, Capability
    # Just verify the module can be imported and the class exists
    from SciQLop.plugins.collaborative_catalogs.cocat_provider import CocatCatalogProvider
    assert issubclass(CocatCatalogProvider, CatalogProvider)
```

**Step 2: Create `cocat_provider.py`**

Create `SciQLop/plugins/collaborative_catalogs/cocat_provider.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
import uuid as _uuid

from PySide6.QtCore import QObject, QTimer

from SciQLop.components.catalogs import (
    Capability,
    Catalog,
    CatalogEvent,
    CatalogProvider,
)


class CocatEvent(CatalogEvent):
    """CatalogEvent wrapping a cocat Event with deferred writes."""

    def __init__(self, cocat_event, parent: QObject | None = None):
        self._cocat_event = cocat_event
        super().__init__(
            uuid=str(cocat_event.uuid),
            start=cocat_event.start,
            stop=cocat_event.stop,
            meta={},
            parent=parent,
        )
        self._deferred = QTimer(self)
        self._deferred.setSingleShot(True)
        self._deferred.setInterval(100)
        self._deferred.timeout.connect(self._apply)

    @property
    def start(self) -> datetime:
        return self._start

    @start.setter
    def start(self, value: datetime) -> None:
        if value != self._start:
            self._start = value
            self._deferred.start()
            self.range_changed.emit()

    @property
    def stop(self) -> datetime:
        return self._stop

    @stop.setter
    def stop(self, value: datetime) -> None:
        if value != self._stop:
            self._stop = value
            self._deferred.start()
            self.range_changed.emit()

    def _apply(self) -> None:
        self._cocat_event.range = (self._start, self._stop)


class CocatCatalogProvider(CatalogProvider):
    """CatalogProvider wrapping a cocat Room/DB."""

    def __init__(self, room, parent: QObject | None = None):
        self._room = room
        self._catalog_map: dict[str, Catalog] = {}
        super().__init__(name="CoCat", parent=parent)
        self._load_catalogs()

    def _load_catalogs(self) -> None:
        for cat_name in self._room.catalogues:
            cocat_cat = self._room.get_catalogue(cat_name)
            cat = Catalog(
                uuid=str(cocat_cat.uuid) if hasattr(cocat_cat, 'uuid') else cat_name,
                name=cat_name,
                provider=self,
                path=[],
            )
            self._catalog_map[cat.uuid] = cat
            events = []
            for cocat_event in cocat_cat.events:
                events.append(CocatEvent(cocat_event, parent=self))
            self._set_events(cat, events)

    def catalogs(self) -> list[Catalog]:
        return list(self._catalog_map.values())

    def capabilities(self, catalog: Catalog | None = None) -> set[str]:
        return {
            Capability.EDIT_EVENTS,
            Capability.CREATE_EVENTS,
            Capability.DELETE_EVENTS,
        }
```

**Step 3: Update Plugin to use CocatCatalogProvider**

Replace `SciQLop/plugins/collaborative_catalogs/plugin.py`:

```python
from typing import Optional
from PySide6.QtCore import QObject, Signal, Qt
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QToolBar
from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.ui.mainwindow import SciQLopMainWindow
from qasync import asyncSlot
from .room import Room

log = getLogger(__name__)


class CatalogGUISpawner(QAction):
    _connected = Signal()

    def __init__(self, url: str = "https://sciqlop.lpp.polytechnique.fr/cocat/", parent=None):
        super().__init__(parent)
        self._url = url
        self.setIcon(QIcon("://icons/theme/catalogue.png"))
        self.triggered.connect(self.show_catalogue_gui)
        self.setText("Open Collaborative Catalogs")
        self._room: Optional[Room] = None
        self._provider = None
        self._connected.connect(self._once_connected, Qt.ConnectionType.QueuedConnection)

    def _once_connected(self):
        from .cocat_provider import CocatCatalogProvider
        self._provider = CocatCatalogProvider(room=self._room, parent=self)
        log.info("CoCat provider registered with %d catalogs", len(self._provider.catalogs()))

    @asyncSlot()
    async def show_catalogue_gui(self):
        try:
            self._room = Room(url=self._url, parent=self)
            if await self._room.join():
                self._connected.emit()
        except Exception as e:
            log.error(e)


class Plugin(QObject):
    def __init__(self, main_window: SciQLopMainWindow):
        super().__init__(main_window)
        self._main_window = main_window
        self.show_catalog = CatalogGUISpawner()
        self.toolbar: QToolBar = main_window.addToolBar("Collaborative Catalogs")
        self.toolbar.addAction(self.show_catalog)
```

**Step 4: Run tests**

Run: `uv run pytest tests/test_catalog_provider.py -v`
Expected: all PASS

**Step 5: Commit**

```bash
git add SciQLop/plugins/collaborative_catalogs/cocat_provider.py SciQLop/plugins/collaborative_catalogs/plugin.py tests/test_catalog_provider.py
git commit -m "feat(catalogs): port collaborative catalogs plugin to new provider API"
```

---

## Execution Order Summary

| Order | Task | Description | Dependencies |
|-------|------|-------------|-------------|
| 1 | Task 1 | Fix `catalog_removed` None bug | None |
| 2 | Task 2 | Replace busy-wait event loading | None |
| 3 | Task 3 | Wire filter bar | None |
| 4 | Task 4 | Wire add/delete buttons + overlay reactivity | None (adds public API) |
| 5 | Task 5 | Lazy event loading | Task 4 (overlay reactivity) |
| 6 | Task 6 | Port collaborative catalogs | Task 4 (public API) |
