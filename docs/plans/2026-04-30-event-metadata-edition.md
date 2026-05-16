# Event Metadata Display & Edition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the event table the primary surface for inspecting *and* editing per-event metadata, with multi-row bulk edit, type-aware editor widgets, and a discoverable column show/hide menu. Closes backlog items #22 (event metadata display/edition) and #21 (event multi-selection & bulk-edition).

**Architecture:** The `EventTableModel` becomes editable; `setData` dispatches through a new `CatalogProvider.set_event_meta` API gated by `Capability.EDIT_EVENTS`. Editor widgets are produced by reusing the existing `settings_delegates` registry — one delegate system, two surfaces. Per-cell edits inside a multi-row selection propagate to all selected rows in the same column (bulk edit). Column visibility/order is persisted in a new `EventTableViewState` `ConfigEntry` keyed by `catalog.uuid` — pure UI concern, lives in settings, not in the catalog backend. Discoverability comes from a "Columns" toolbar button that opens a popover with a search box, drag-reorderable checklist, and Show all / Hide all / Reset actions; the same menu is also reachable by right-clicking the header row.

**Tech Stack:** PySide6 (QAbstractTableModel, QStyledItemDelegate, QTableView), Pydantic (ConfigEntry), pytest-qt, existing `SciQLop.components.settings.ui.settings_delegates` registry.

---

## File Structure

**New files:**
- `SciQLop/components/catalogs/ui/event_table_delegate.py` — `EventTableDelegate(QStyledItemDelegate)`, type inference per column, bridges to settings delegates
- `SciQLop/components/catalogs/ui/column_visibility_popover.py` — popover widget (search + checklist + drag-reorder + Show/Hide all)
- `SciQLop/components/catalogs/backend/event_table_view_state.py` — `EventTableViewState(ConfigEntry)` Pydantic model, helpers `get_view_state(catalog)` / `save_view_state(catalog, state)`
- `tests/test_event_meta_edition.py` — provider-level tests for `set_event_meta` / signals
- `tests/test_event_table_editing.py` — UI tests: setData, multi-row bulk edit, capability gating
- `tests/test_event_table_view_state.py` — column visibility persistence

**Modified files:**
- `SciQLop/components/catalogs/backend/provider.py` — add `event_meta_changed` signal, `set_event_meta` / `remove_event_meta` / `set_events_meta` API; `CatalogEvent.set_meta(...)`
- `SciQLop/components/catalogs/backend/dummy_provider.py` — no override needed (default impl works), used as test reference
- `SciQLop/plugins/tscat_catalogs/tscat_provider.py` — override `set_event_meta` / `remove_event_meta` (tscat `SetAttributeAction`)
- `SciQLop/plugins/collaborative_catalogs/cocat_provider.py` — override `set_event_meta` (CRDT `event.set_attributes`)
- `SciQLop/components/catalogs/ui/event_table.py` — `flags()` editable when capable; `setData()`; provider-level signal wiring; column-visibility / order helpers
- `SciQLop/components/catalogs/ui/catalog_browser.py` — install delegate; ExtendedSelection; bulk-edit propagation; "Columns" toolbar button; header context menu; apply view-state on catalog change

---

## Task 1: Add `meta_changed` signal to `CatalogEvent`

**Files:**
- Modify: `SciQLop/components/catalogs/backend/provider.py`
- Test: `tests/test_event_meta_edition.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_event_meta_edition.py`:

```python
from datetime import datetime, timezone
from SciQLop.components.catalogs.backend.provider import CatalogEvent


def test_event_meta_changed_signal_emits_on_set_meta(qtbot, qapp):
    event = CatalogEvent(
        uuid="e1",
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
        meta={"score": 0.5},
    )
    with qtbot.waitSignal(event.meta_changed, timeout=1000) as blocker:
        event.set_meta("score", 0.9)
    assert blocker.args == ["score"]
    assert event.meta["score"] == 0.9


def test_event_meta_changed_not_emitted_when_value_unchanged(qtbot, qapp):
    event = CatalogEvent(
        uuid="e1",
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
        meta={"score": 0.5},
    )
    received = []
    event.meta_changed.connect(received.append)
    event.set_meta("score", 0.5)
    assert received == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_event_meta_edition.py::test_event_meta_changed_signal_emits_on_set_meta -v`
Expected: FAIL with `AttributeError: 'CatalogEvent' object has no attribute 'meta_changed'`.

- [ ] **Step 3: Add the signal and `set_meta` method**

In `SciQLop/components/catalogs/backend/provider.py`, modify `CatalogEvent`:

```python
class CatalogEvent(QObject):
    """Minimal event: uuid + time interval + optional metadata."""
    range_changed = Signal()
    meta_changed = Signal(str)  # key

    def __init__(self, uuid: str, start: datetime, stop: datetime,
                 meta: dict[str, Any] | None = None, parent: QObject | None = None):
        super().__init__(parent)
        self._uuid = uuid
        self._start = make_utc_datetime(start)
        self._stop = make_utc_datetime(stop)
        self._meta = dict(meta or {})

    # ... existing properties unchanged ...

    def set_meta(self, key: str, value: Any) -> None:
        """Update one metadata key in place, emitting meta_changed if it changed."""
        if self._meta.get(key, _SENTINEL) == value:
            return
        self._meta[key] = value
        self.meta_changed.emit(key)

    def remove_meta(self, key: str) -> None:
        if key in self._meta:
            del self._meta[key]
            self.meta_changed.emit(key)
```

Add a module-level sentinel near the top of the file:

```python
_SENTINEL = object()
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_event_meta_edition.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/catalogs/backend/provider.py tests/test_event_meta_edition.py
git commit -m "feat(catalogs): CatalogEvent.set_meta + meta_changed signal"
```

---

## Task 2: Add provider-level `set_event_meta` API and `event_meta_changed` signal

**Files:**
- Modify: `SciQLop/components/catalogs/backend/provider.py`
- Test: `tests/test_event_meta_edition.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_event_meta_edition.py`:

```python
def test_provider_set_event_meta_marks_dirty_and_emits(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    event = provider.events(cat)[0]

    received = []
    provider.event_meta_changed.connect(lambda c, e, k: received.append((c.uuid, e.uuid, k)))

    with qtbot.waitSignal(provider.dirty_changed, timeout=1000):
        provider.set_event_meta(cat, event, "score", 0.42)

    assert event.meta["score"] == 0.42
    assert received == [(cat.uuid, event.uuid, "score")]
    assert provider.is_dirty(cat)


def test_provider_set_events_meta_bulk(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, events_per_catalog=5)
    cat = provider.catalogs()[0]
    events = provider.events(cat)[:3]

    provider.set_events_meta(cat, events, "class", "boundary")

    for e in events:
        assert e.meta["class"] == "boundary"
    assert provider.is_dirty(cat)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_event_meta_edition.py::test_provider_set_event_meta_marks_dirty_and_emits -v`
Expected: FAIL — provider has no `set_event_meta`.

- [ ] **Step 3: Add provider API**

In `SciQLop/components/catalogs/backend/provider.py`, add to the signal list of `CatalogProvider`:

```python
    event_meta_changed = Signal(object, object, str)  # (catalog, event, key)
```

Add these methods on `CatalogProvider` (default implementation, after `remove_event`):

```python
    def set_event_meta(self, catalog: Catalog, event: CatalogEvent, key: str, value: Any) -> None:
        """Public API: set one metadata key on an event. Override for backend persistence."""
        if event.meta.get(key, _SENTINEL) == value:
            return
        event.set_meta(key, value)
        self.event_meta_changed.emit(catalog, event, key)
        self.mark_dirty(catalog)

    def remove_event_meta(self, catalog: Catalog, event: CatalogEvent, key: str) -> None:
        if key not in event.meta:
            return
        event.remove_meta(key)
        self.event_meta_changed.emit(catalog, event, key)
        self.mark_dirty(catalog)

    def set_events_meta(self, catalog: Catalog, events: list[CatalogEvent],
                        key: str, value: Any) -> None:
        """Public API: bulk variant. Default loops; override for batch backends."""
        any_changed = False
        for event in events:
            if event.meta.get(key, _SENTINEL) == value:
                continue
            event.set_meta(key, value)
            self.event_meta_changed.emit(catalog, event, key)
            any_changed = True
        if any_changed:
            self.mark_dirty(catalog)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_event_meta_edition.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/catalogs/backend/provider.py tests/test_event_meta_edition.py
git commit -m "feat(catalogs): provider set_event_meta / set_events_meta API"
```

---

## Task 3: Override `set_event_meta` in `TscatCatalogProvider`

**Files:**
- Modify: `SciQLop/plugins/tscat_catalogs/tscat_provider.py`
- Test: `tests/test_catalog_tscat_integration.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_catalog_tscat_integration.py` (use existing test fixtures):

```python
def test_tscat_set_event_meta_persists(qtbot, qapp, tmp_path):
    from SciQLop.plugins.tscat_catalogs.tscat_provider import TscatCatalogProvider
    import tscat

    tscat.discard()
    provider = TscatCatalogProvider()
    cat = provider.create_catalog("c1")
    qtbot.wait(20)
    from datetime import datetime, timezone
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    import uuid as _uuid
    ev = CatalogEvent(
        uuid=str(_uuid.uuid4()),
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
        meta={},
    )
    provider.add_event(cat, ev)
    qtbot.wait(20)

    provider.set_event_meta(cat, ev, "rating", 4)
    qtbot.wait(20)

    refreshed = next(e for e in provider.events(cat) if e.uuid == ev.uuid)
    assert refreshed.meta.get("rating") == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_tscat_integration.py::test_tscat_set_event_meta_persists -v`
Expected: FAIL — value not persisted into tscat (the in-memory event sees the value, but reload from `provider.events(cat)` returns the cached event without backend round-trip; in any case the tscat entity attribute won't be updated).

- [ ] **Step 3: Override `set_event_meta` in `TscatCatalogProvider`**

In `SciQLop/plugins/tscat_catalogs/tscat_provider.py`, add to the class:

```python
    _STANDARD_ATTRS = ("author", "tags", "rating")

    def set_event_meta(self, catalog: Catalog, event: CatalogEvent, key: str, value: Any) -> None:
        if event.meta.get(key, None) == value and key in event.meta:
            return
        with self._tracked_action():
            tscat_model.do(SetAttributeAction(
                user_callback=None,
                uuids=[event.uuid],
                name=key,
                values=[value],
            ))
        event.set_meta(key, value)
        self.event_meta_changed.emit(catalog, event, key)
        self.mark_dirty(catalog)

    def remove_event_meta(self, catalog: Catalog, event: CatalogEvent, key: str) -> None:
        if key not in event.meta:
            return
        if key in self._STANDARD_ATTRS:
            return
        from tscat_gui.tscat_driver.actions import DeleteAttributeAction
        with self._tracked_action():
            tscat_model.do(DeleteAttributeAction(
                user_callback=None,
                uuids=[event.uuid],
                name=key,
            ))
        event.remove_meta(key)
        self.event_meta_changed.emit(catalog, event, key)
        self.mark_dirty(catalog)

    def set_events_meta(self, catalog: Catalog, events: list[CatalogEvent],
                        key: str, value: Any) -> None:
        targets = [e for e in events
                   if e.meta.get(key, None) != value or key not in e.meta]
        if not targets:
            return
        with self._tracked_action():
            tscat_model.do(SetAttributeAction(
                user_callback=None,
                uuids=[e.uuid for e in targets],
                name=key,
                values=[value] * len(targets),
            ))
        for e in targets:
            e.set_meta(key, value)
            self.event_meta_changed.emit(catalog, e, key)
        self.mark_dirty(catalog)
```

If `DeleteAttributeAction` does not exist in the installed `tscat_gui` version, fall back to setting the value to `None` and document the limitation in the test (`pytest.skip` if missing).

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_catalog_tscat_integration.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/plugins/tscat_catalogs/tscat_provider.py tests/test_catalog_tscat_integration.py
git commit -m "feat(tscat): set_event_meta / remove_event_meta / set_events_meta"
```

---

## Task 4: Override `set_event_meta` in `CocatCatalogProvider`

**Files:**
- Modify: `SciQLop/plugins/collaborative_catalogs/cocat_provider.py`
- Test: `tests/test_cocat_event_meta.py` (new)

- [ ] **Step 1: Read existing cocat plumbing**

Open `SciQLop/plugins/collaborative_catalogs/cocat_provider.py` and locate:
- the per-event wrapper (find the class with `_cocat_event` or analogous)
- how event attributes are read (`cocat_event.attributes`)
- how attributes are written remotely (look for `set_attributes` calls on cocat events; if none, look in the cocat library — see `/home/jeandet/.claude/memory/cocat-library.md`)

This task assumes there is a `cocat_event.set_attributes(**kwargs)` and an `on_set_attributes` observer (mirror of catalog-level wiring at lines 241-244 for catalogs in the existing file). If not, add the equivalent to the event wrapper before continuing.

- [ ] **Step 2: Write the failing test**

Create `tests/test_cocat_event_meta.py`:

```python
import pytest
from datetime import datetime, timezone
from SciQLop.components.catalogs.backend.provider import CatalogEvent


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("cocat"),
    reason="cocat library not installed",
)
def test_cocat_set_event_meta_routes_through_crdt(qtbot, qapp, monkeypatch):
    from SciQLop.plugins.collaborative_catalogs.cocat_provider import CocatCatalogProvider

    provider = CocatCatalogProvider()
    # Use the in-memory test harness (no real server) — see existing cocat tests
    # for the pattern used to spin up a local room.
    pytest.skip("Requires live cocat room — covered by manual smoke test")
```

The real verification for cocat is end-to-end and lives in the manual smoke checklist; this file documents the expectation and gates on import.

- [ ] **Step 3: Override `set_event_meta` in `CocatCatalogProvider`**

In `SciQLop/plugins/collaborative_catalogs/cocat_provider.py`, locate the per-event wiring and add:

```python
    def set_event_meta(self, catalog: Catalog, event: CatalogEvent, key: str, value: Any) -> None:
        cocat_event = self._cocat_event_for(event)
        if cocat_event is None:
            return  # event not in a joined room
        if cocat_event.attributes.get(key, _SENTINEL) == value:
            return
        cocat_event.set_attributes(**{key: value})
        # Local mirror is updated via the on_set_attributes observer; emit signal once
        # the round-trip has happened. See _on_remote_event_attributes_set below.

    def remove_event_meta(self, catalog: Catalog, event: CatalogEvent, key: str) -> None:
        cocat_event = self._cocat_event_for(event)
        if cocat_event is None or key not in cocat_event.attributes:
            return
        cocat_event.remove_attributes([key])
```

Wire `_on_remote_event_attributes_set(event, attrs)` to call `event.set_meta(...)` for each changed key and emit `event_meta_changed`. Mirror the catalog-level pattern at lines 275-286 of the existing file.

`_cocat_event_for(event)` returns the cocat event handle for a given local `CatalogEvent` (look up by uuid). If no such helper exists, add it.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_cocat_event_meta.py -v`
Expected: SKIPPED (requires live server) — that's intentional. The full check is a manual smoke test against a cocat server.

- [ ] **Step 5: Document the smoke-test step**

Append to `docs/plans/2026-04-30-event-metadata-edition.md` (this file) under a new section at the bottom titled "Manual smoke tests":

```
### Cocat event metadata round-trip
1. Start a local cocat server (see cocat library README).
2. Open SciQLop, join a room with at least one catalog and one event.
3. Edit the `tags` cell in the event table; confirm the value persists after rejoining.
4. From a second client joined to the same room, verify the change appears within ~1s.
```

- [ ] **Step 6: Commit**

```bash
git add SciQLop/plugins/collaborative_catalogs/cocat_provider.py tests/test_cocat_event_meta.py docs/plans/2026-04-30-event-metadata-edition.md
git commit -m "feat(cocat): set_event_meta routes through CRDT attribute mutation"
```

---

## Task 5: Make `EventTableModel` editable (flags + setData)

**Files:**
- Modify: `SciQLop/components/catalogs/ui/event_table.py`
- Test: `tests/test_event_table_editing.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_event_table_editing.py`:

```python
from PySide6.QtCore import Qt, QModelIndex
from SciQLop.components.catalogs.ui.event_table import EventTableModel
from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
from SciQLop.components.catalogs.backend.provider import Capability


def test_event_model_flags_editable_when_provider_has_edit_capability(qapp):
    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    idx = model.index(0, 0)
    assert model.flags(idx) & Qt.ItemFlag.ItemIsEditable
    idx_meta = model.index(0, 2)
    assert model.flags(idx_meta) & Qt.ItemFlag.ItemIsEditable


def test_event_model_flags_not_editable_without_capability(qapp):
    class ReadOnlyProvider(DummyProvider):
        def capabilities(self, catalog=None):
            return set()  # no EDIT_EVENTS

    provider = ReadOnlyProvider(num_catalogs=1, events_per_catalog=2)
    cat = provider.catalogs()[0]
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    idx = model.index(0, 0)
    assert not (model.flags(idx) & Qt.ItemFlag.ItemIsEditable)


def test_event_model_setdata_meta_routes_to_provider(qtbot, qapp):
    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    score_col = model._FIXED_COLUMNS.__len__() + model._meta_keys.index("score")
    idx = model.index(0, score_col)

    with qtbot.waitSignal(provider.event_meta_changed, timeout=1000):
        ok = model.setData(idx, 0.99, Qt.ItemDataRole.EditRole)

    assert ok is True
    event = provider.events(cat)[0]
    assert event.meta["score"] == 0.99
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_event_table_editing.py -v`
Expected: FAIL on `set_context` (does not exist).

- [ ] **Step 3: Modify `EventTableModel`**

Edit `SciQLop/components/catalogs/ui/event_table.py`. Add to the class:

```python
    def __init__(self, parent=None):
        super().__init__(parent)
        self._events: list[CatalogEvent] = []
        self._meta_keys: list[str] = []
        self._provider = None
        self._catalog = None

    def set_context(self, provider, catalog) -> None:
        """Bind the model to a provider/catalog so setData can route through them."""
        self._provider = provider
        self._catalog = catalog

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        base = super().flags(index)
        if not index.isValid() or self._provider is None or self._catalog is None:
            return base
        from ..backend.provider import Capability
        if Capability.EDIT_EVENTS not in self._provider.capabilities(self._catalog):
            return base
        return base | Qt.ItemFlag.ItemIsEditable

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if role != Qt.ItemDataRole.EditRole or not index.isValid():
            return False
        if self._provider is None or self._catalog is None:
            return False
        event = self._events[index.row()]
        col = index.column()
        if col == 0:
            event.start = value
            return True
        if col == 1:
            event.stop = value
            return True
        key = self._meta_keys[col - len(self._FIXED_COLUMNS)]
        self._provider.set_event_meta(self._catalog, event, key, value)
        return True
```

- [ ] **Step 4: Wire `event_meta_changed` to `dataChanged`**

Add to `set_events`:

```python
    def set_events(self, events: list[CatalogEvent]) -> None:
        self.beginResetModel()
        self._disconnect_events()
        self._events = list(events)
        keys: set[str] = set()
        for e in self._events:
            keys.update(e.meta.keys())
        self._meta_keys = sorted(keys)
        self._connect_events()
        self._connect_provider_meta_signal()
        self.endResetModel()

    def _connect_provider_meta_signal(self) -> None:
        if getattr(self, "_meta_signal_provider", None) is not None:
            try:
                self._meta_signal_provider.event_meta_changed.disconnect(self._on_event_meta_changed)
            except RuntimeError:
                pass
        if self._provider is not None:
            self._provider.event_meta_changed.connect(self._on_event_meta_changed)
            self._meta_signal_provider = self._provider
        else:
            self._meta_signal_provider = None

    def _on_event_meta_changed(self, catalog, event, key: str) -> None:
        if self._catalog is None or catalog.uuid != self._catalog.uuid:
            return
        row = self.row_for_event(event)
        if row < 0:
            return
        if key not in self._meta_keys:
            self.beginResetModel()
            keys = set(self._meta_keys) | {key}
            self._meta_keys = sorted(keys)
            self.endResetModel()
            return
        col = len(self._FIXED_COLUMNS) + self._meta_keys.index(key)
        idx = self.index(row, col)
        self.dataChanged.emit(idx, idx, [int(Qt.ItemDataRole.DisplayRole)])
```

- [ ] **Step 5: Update `clear()` to also clear context**

```python
    def clear(self) -> None:
        self.beginResetModel()
        self._disconnect_events()
        if getattr(self, "_meta_signal_provider", None) is not None:
            try:
                self._meta_signal_provider.event_meta_changed.disconnect(self._on_event_meta_changed)
            except RuntimeError:
                pass
            self._meta_signal_provider = None
        self._events = []
        self._meta_keys = []
        self.endResetModel()
```

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_event_table_editing.py -v`
Expected: 3 passed.

- [ ] **Step 7: Wire `set_context` in `CatalogBrowser._on_catalog_selected`**

In `SciQLop/components/catalogs/ui/catalog_browser.py`, in `_on_catalog_selected`, before `self._event_model.set_events(events)`:

```python
            self._event_model.set_context(node.provider, node.catalog)
            self._event_model.set_events(events)
```

And in the `else:` branch (no catalog selected), call `self._event_model.set_context(None, None)` before `clear()`.

- [ ] **Step 8: Commit**

```bash
git add SciQLop/components/catalogs/ui/event_table.py SciQLop/components/catalogs/ui/catalog_browser.py tests/test_event_table_editing.py
git commit -m "feat(catalogs): editable EventTableModel with capability gating"
```

---

## Task 6: Type-aware `EventTableDelegate` reusing settings delegates

**Files:**
- Create: `SciQLop/components/catalogs/ui/event_table_delegate.py`
- Modify: `SciQLop/components/catalogs/ui/catalog_browser.py`
- Test: `tests/test_event_table_editing.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_event_table_editing.py`:

```python
def test_event_table_delegate_creates_int_editor_for_int_column(qapp):
    from PySide6.QtCore import QModelIndex
    from PySide6.QtWidgets import QSpinBox, QStyleOptionViewItem
    from SciQLop.components.catalogs.ui.event_table_delegate import EventTableDelegate

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(provider.events(cat))

    delegate = EventTableDelegate(model)
    index_col = len(model._FIXED_COLUMNS) + model._meta_keys.index("index")
    idx = model.index(0, index_col)
    editor = delegate.createEditor(None, QStyleOptionViewItem(), idx)
    assert editor is not None
    # SettingDelegate wrapper hosts a QSpinBox for ints
    spinboxes = editor.findChildren(QSpinBox)
    assert len(spinboxes) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_event_table_editing.py::test_event_table_delegate_creates_int_editor_for_int_column -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Create the delegate**

Create `SciQLop/components/catalogs/ui/event_table_delegate.py`:

```python
from __future__ import annotations

from datetime import datetime
from typing import Any

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QStyledItemDelegate, QWidget, QDateTimeEdit

from SciQLop.components.settings.ui.settings_delegates import (
    SettingDelegate,
    BoolDelegate,
    IntDelegate,
    FloatDelegate,
    StrDelegate,
)


def _infer_column_type(values: list[Any]) -> type:
    """Return the most specific type covering all non-None values; default str."""
    types = {type(v) for v in values if v is not None and v != ""}
    if not types:
        return str
    if types == {bool}:
        return bool
    if types <= {bool, int}:
        return int
    if types <= {bool, int, float}:
        return float
    return str


_DELEGATE_FOR_TYPE = {
    bool: BoolDelegate,
    int: IntDelegate,
    float: FloatDelegate,
    str: StrDelegate,
}


class EventTableDelegate(QStyledItemDelegate):
    """Picks an editor widget per column by inferring the value type."""

    _DATETIME_FORMAT = "yyyy-MM-dd HH:mm:ss"

    def __init__(self, source_model, parent=None):
        super().__init__(parent)
        self._source_model = source_model
        self._column_types: dict[int, type] = {}
        source_model.modelReset.connect(self._column_types.clear)

    def _column_type(self, source_col: int) -> type:
        if source_col in self._column_types:
            return self._column_types[source_col]
        meta_offset = len(self._source_model._FIXED_COLUMNS)
        if source_col < meta_offset:
            t = datetime
        else:
            key = self._source_model._meta_keys[source_col - meta_offset]
            values = [e.meta.get(key) for e in self._source_model._events]
            t = _infer_column_type(values)
        self._column_types[source_col] = t
        return t

    def createEditor(self, parent: QWidget, option, index: QModelIndex) -> QWidget:
        source_index = self._to_source(index)
        col_type = self._column_type(source_index.column())
        if col_type is datetime:
            edit = QDateTimeEdit(parent)
            edit.setDisplayFormat(self._DATETIME_FORMAT)
            edit.setCalendarPopup(True)
            return edit
        delegate_cls = _DELEGATE_FOR_TYPE.get(col_type, StrDelegate)
        widget = delegate_cls(parent)
        return widget

    def setEditorData(self, editor: QWidget, index: QModelIndex) -> None:
        source_index = self._to_source(index)
        col_type = self._column_type(source_index.column())
        if col_type is datetime:
            event = self._source_model._events[source_index.row()]
            value = event.start if source_index.column() == 0 else event.stop
            from PySide6.QtCore import QDateTime
            editor.setDateTime(QDateTime.fromSecsSinceEpoch(int(value.timestamp())))
            return
        if isinstance(editor, SettingDelegate):
            event = self._source_model._events[source_index.row()]
            key = self._source_model._meta_keys[source_index.column() - len(self._source_model._FIXED_COLUMNS)]
            editor.set_value(event.meta.get(key))

    def setModelData(self, editor: QWidget, model, index: QModelIndex) -> None:
        source_index = self._to_source(index)
        col_type = self._column_type(source_index.column())
        if col_type is datetime:
            from datetime import timezone
            qdt = editor.dateTime()
            value = datetime.fromtimestamp(qdt.toSecsSinceEpoch(), tz=timezone.utc)
            model.setData(index, value, Qt.ItemDataRole.EditRole)
            return
        if isinstance(editor, SettingDelegate):
            model.setData(index, editor.get_value(), Qt.ItemDataRole.EditRole)

    def _to_source(self, index: QModelIndex) -> QModelIndex:
        m = index.model()
        if hasattr(m, "mapToSource"):
            return m.mapToSource(index)
        return index
```

- [ ] **Step 4: Install the delegate in `CatalogBrowser`**

In `SciQLop/components/catalogs/ui/catalog_browser.py`, after `self._event_table = QTableView()`:

```python
        from .event_table_delegate import EventTableDelegate
        self._event_delegate = EventTableDelegate(self._event_model, self._event_table)
        self._event_table.setItemDelegate(self._event_delegate)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_event_table_editing.py -v`
Expected: 4 passed.

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/catalogs/ui/event_table_delegate.py SciQLop/components/catalogs/ui/catalog_browser.py tests/test_event_table_editing.py
git commit -m "feat(catalogs): EventTableDelegate reuses settings delegates"
```

---

## Task 7: Multi-row selection + bulk-edit propagation

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_browser.py`
- Test: `tests/test_event_table_editing.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_event_table_editing.py`:

```python
def test_bulk_edit_propagates_to_selected_rows(qtbot, qapp):
    from PySide6.QtCore import Qt, QItemSelectionModel
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser

    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    provider = DummyProvider(num_catalogs=1, events_per_catalog=5)
    cat = provider.catalogs()[0]
    browser._current_provider = provider
    browser._current_catalog = cat
    browser._event_model.set_context(provider, cat)
    browser._event_model.set_events(provider.events(cat))

    sm = browser._event_table.selectionModel()
    sm.clear()
    for row in (0, 1, 2):
        sm.select(
            browser._sort_proxy.index(row, 0),
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
        )
    sm.setCurrentIndex(
        browser._sort_proxy.index(0, len(browser._event_model._FIXED_COLUMNS)
                                  + browser._event_model._meta_keys.index("class")),
        QItemSelectionModel.SelectionFlag.NoUpdate,
    )

    score_col = len(browser._event_model._FIXED_COLUMNS) + browser._event_model._meta_keys.index("class")
    idx = browser._sort_proxy.index(0, score_col)
    browser._sort_proxy.setData(idx, "boundary", Qt.ItemDataRole.EditRole)

    # Bulk-edit hook propagates to other selected rows
    browser._propagate_bulk_edit(idx, "boundary")

    for row in (0, 1, 2):
        proxy_idx = browser._sort_proxy.index(row, score_col)
        assert browser._sort_proxy.data(proxy_idx) == "boundary"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_event_table_editing.py::test_bulk_edit_propagates_to_selected_rows -v`
Expected: FAIL — `_propagate_bulk_edit` does not exist.

- [ ] **Step 3: Add bulk-edit propagation**

In `SciQLop/components/catalogs/ui/catalog_browser.py`, add to `__init__` after the table is built:

```python
        self._event_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._event_table.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self._event_model.dataChanged.connect(self._on_event_data_changed)
```

Add the method:

```python
    def _on_event_data_changed(self, top_left, bottom_right, roles=None) -> None:
        if top_left != bottom_right:
            return
        proxy_idx = self._sort_proxy.mapFromSource(top_left)
        if not proxy_idx.isValid():
            return
        value = self._event_model.data(top_left, Qt.ItemDataRole.EditRole) \
            if hasattr(self._event_model, "_events") else None
        # Read the actual stored value for free-form types
        event = self._event_model.event_at(top_left.row())
        col = top_left.column()
        if event is None:
            return
        if col >= len(self._event_model._FIXED_COLUMNS):
            key = self._event_model._meta_keys[col - len(self._event_model._FIXED_COLUMNS)]
            value = event.meta.get(key)
        elif col == 0:
            value = event.start
        else:
            value = event.stop
        self._propagate_bulk_edit(proxy_idx, value)

    def _propagate_bulk_edit(self, proxy_idx, value) -> None:
        sm = self._event_table.selectionModel()
        if sm is None:
            return
        selected_rows = {idx.row() for idx in sm.selectedRows()}
        if proxy_idx.row() not in selected_rows or len(selected_rows) <= 1:
            return
        col = proxy_idx.column()
        source_origin = self._sort_proxy.mapToSource(proxy_idx)
        origin_event = self._event_model.event_at(source_origin.row())
        if origin_event is None:
            return
        targets = []
        for row in selected_rows:
            if row == proxy_idx.row():
                continue
            source_idx = self._sort_proxy.mapToSource(self._sort_proxy.index(row, col))
            ev = self._event_model.event_at(source_idx.row())
            if ev is not None and ev is not origin_event:
                targets.append(ev)
        if not targets:
            return
        if col == 0 or col == 1:
            for ev in targets:
                if col == 0:
                    ev.start = value
                else:
                    ev.stop = value
            return
        key = self._event_model._meta_keys[col - len(self._event_model._FIXED_COLUMNS)]
        self._current_provider.set_events_meta(self._current_catalog, targets, key, value)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_event_table_editing.py -v`
Expected: 5 passed.

- [ ] **Step 5: Update Delete to act on multi-selection**

Locate `_on_delete` (around line 411) and replace its body to delete every selected row, not just the current one:

```python
    def _on_delete(self) -> None:
        if self._current_provider is None or self._current_catalog is None:
            return
        sm = self._event_table.selectionModel()
        if sm is None:
            return
        events = []
        for proxy_idx in sm.selectedRows():
            source_idx = self._sort_proxy.mapToSource(proxy_idx)
            ev = self._event_model.event_at(source_idx.row())
            if ev is not None:
                events.append(ev)
        for ev in events:
            self._current_provider.remove_event(self._current_catalog, ev)
```

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_browser.py tests/test_event_table_editing.py
git commit -m "feat(catalogs): multi-row selection + bulk edit + bulk delete"
```

---

## Task 8: `EventTableViewState` ConfigEntry (column visibility persistence)

**Files:**
- Create: `SciQLop/components/catalogs/backend/event_table_view_state.py`
- Test: `tests/test_event_table_view_state.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_event_table_view_state.py`:

```python
from SciQLop.components.catalogs.backend.event_table_view_state import (
    EventTableViewState,
    CatalogViewState,
    get_view_state,
    save_view_state,
)


def test_view_state_default_empty(tmp_path, monkeypatch):
    state = get_view_state("cat-uuid-1")
    assert state.hidden_columns == []
    assert state.column_order == []


def test_view_state_save_and_reload(tmp_path, monkeypatch):
    cat_uid = "cat-uuid-2"
    state = CatalogViewState(hidden_columns=["author", "rating"], column_order=["start", "stop", "class"])
    save_view_state(cat_uid, state)
    reloaded = get_view_state(cat_uid)
    assert reloaded.hidden_columns == ["author", "rating"]
    assert reloaded.column_order == ["start", "stop", "class"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_event_table_view_state.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the ConfigEntry**

Create `SciQLop/components/catalogs/backend/event_table_view_state.py`:

```python
from __future__ import annotations

from typing import ClassVar
from pydantic import BaseModel

from SciQLop.components.settings.backend.entry import ConfigEntry, SettingsCategory


class CatalogViewState(BaseModel):
    hidden_columns: list[str] = []
    column_order: list[str] = []


class EventTableViewState(ConfigEntry):
    category: ClassVar[str] = SettingsCategory.CATALOGS
    subcategory: ClassVar[str] = "Event Table"
    states: dict[str, CatalogViewState] = {}


def get_view_state(catalog_uid: str) -> CatalogViewState:
    with EventTableViewState() as settings:
        return settings.states.get(catalog_uid) or CatalogViewState()


def save_view_state(catalog_uid: str, state: CatalogViewState) -> None:
    with EventTableViewState() as settings:
        settings.states[catalog_uid] = state
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_event_table_view_state.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/catalogs/backend/event_table_view_state.py tests/test_event_table_view_state.py
git commit -m "feat(catalogs): EventTableViewState ConfigEntry for per-catalog UI state"
```

---

## Task 9: Apply view state on catalog selection + persist on column move/hide

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_browser.py`
- Test: `tests/test_event_table_view_state.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_event_table_view_state.py`:

```python
def test_browser_applies_hidden_columns_on_catalog_select(qtbot, qapp, tmp_path, monkeypatch):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.event_table_view_state import (
        CatalogViewState, save_view_state,
    )
    from PySide6.QtCore import QModelIndex

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    save_view_state(cat.uuid, CatalogViewState(hidden_columns=["score"], column_order=[]))

    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    # Manually drive selection because the tree is not populated in this test
    browser._current_provider = provider
    browser._current_catalog = cat
    browser._event_model.set_context(provider, cat)
    browser._event_model.set_events(provider.events(cat))
    browser._apply_view_state(cat)

    score_col = len(browser._event_model._FIXED_COLUMNS) + browser._event_model._meta_keys.index("score")
    assert browser._event_table.isColumnHidden(score_col)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_event_table_view_state.py::test_browser_applies_hidden_columns_on_catalog_select -v`
Expected: FAIL.

- [ ] **Step 3: Add view-state methods to `CatalogBrowser`**

In `SciQLop/components/catalogs/ui/catalog_browser.py`, add:

```python
    def _apply_view_state(self, catalog) -> None:
        from ..backend.event_table_view_state import get_view_state
        state = get_view_state(catalog.uuid)
        self._event_table.horizontalHeader().blockSignals(True)
        try:
            for col in range(self._event_model.columnCount()):
                key = self._column_key(col)
                self._event_table.setColumnHidden(col, key in state.hidden_columns)
            self._reorder_columns(state.column_order)
        finally:
            self._event_table.horizontalHeader().blockSignals(False)

    def _save_view_state(self) -> None:
        if self._current_catalog is None:
            return
        from ..backend.event_table_view_state import CatalogViewState, save_view_state
        hidden = [
            self._column_key(col)
            for col in range(self._event_model.columnCount())
            if self._event_table.isColumnHidden(col)
        ]
        header = self._event_table.horizontalHeader()
        order = [
            self._column_key(header.logicalIndex(visual))
            for visual in range(self._event_model.columnCount())
        ]
        save_view_state(self._current_catalog.uuid,
                        CatalogViewState(hidden_columns=hidden, column_order=order))

    def _column_key(self, col: int) -> str:
        if col < len(self._event_model._FIXED_COLUMNS):
            return self._event_model._FIXED_COLUMNS[col]
        return self._event_model._meta_keys[col - len(self._event_model._FIXED_COLUMNS)]

    def _reorder_columns(self, desired_order: list[str]) -> None:
        if not desired_order:
            return
        header = self._event_table.horizontalHeader()
        keys_to_logical = {
            self._column_key(col): col for col in range(self._event_model.columnCount())
        }
        target_visual = 0
        for key in desired_order:
            logical = keys_to_logical.get(key)
            if logical is None:
                continue
            current_visual = header.visualIndex(logical)
            if current_visual != target_visual:
                header.moveSection(current_visual, target_visual)
            target_visual += 1
```

In `_on_catalog_selected`, after `self._event_model.set_events(events)`, add:

```python
            self._apply_view_state(node.catalog)
```

In `__init__`, after the header is created:

```python
        header = self._event_table.horizontalHeader()
        header.setSectionsMovable(True)
        header.sectionMoved.connect(lambda *_: self._save_view_state())
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_event_table_view_state.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_browser.py tests/test_event_table_view_state.py
git commit -m "feat(catalogs): apply + persist column visibility per catalog"
```

---

## Task 10: `ColumnVisibilityPopover` widget

**Files:**
- Create: `SciQLop/components/catalogs/ui/column_visibility_popover.py`
- Test: `tests/test_column_visibility_popover.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/test_column_visibility_popover.py`:

```python
from PySide6.QtCore import Qt
from SciQLop.components.catalogs.ui.column_visibility_popover import (
    ColumnVisibilityPopover,
    ColumnEntry,
)


def test_popover_filters_columns_by_search(qtbot, qapp):
    entries = [
        ColumnEntry(key="start", label="start", visible=True, frozen=True),
        ColumnEntry(key="stop", label="stop", visible=True, frozen=True),
        ColumnEntry(key="author", label="author", visible=True, frozen=False),
        ColumnEntry(key="rating", label="rating", visible=False, frozen=False),
    ]
    pop = ColumnVisibilityPopover(entries)
    qtbot.addWidget(pop)
    pop.set_filter("rat")
    assert pop.visible_entry_keys() == ["rating"]


def test_popover_emits_visibility_changed(qtbot, qapp):
    entries = [
        ColumnEntry(key="author", label="author", visible=True, frozen=False),
    ]
    pop = ColumnVisibilityPopover(entries)
    qtbot.addWidget(pop)
    received = []
    pop.visibility_changed.connect(lambda key, vis: received.append((key, vis)))
    pop.set_visible("author", False)
    assert received == [("author", False)]


def test_popover_show_all_unhides_non_frozen(qtbot, qapp):
    entries = [
        ColumnEntry(key="start", label="start", visible=True, frozen=True),
        ColumnEntry(key="author", label="author", visible=False, frozen=False),
    ]
    pop = ColumnVisibilityPopover(entries)
    qtbot.addWidget(pop)
    received = []
    pop.visibility_changed.connect(lambda key, vis: received.append((key, vis)))
    pop.show_all()
    assert ("author", True) in received
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_column_visibility_popover.py -v`
Expected: FAIL — module missing.

- [ ] **Step 3: Implement the popover**

Create `SciQLop/components/catalogs/ui/column_visibility_popover.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLineEdit, QListView, QPushButton,
)


@dataclass
class ColumnEntry:
    key: str
    label: str
    visible: bool
    frozen: bool = False


class ColumnVisibilityPopover(QFrame):
    """Popover with search box + checkable list + Show all/Hide all/Reset.

    Frozen columns (start/stop) are listed but cannot be hidden.
    """

    visibility_changed = Signal(str, bool)
    reorder_requested = Signal(list)  # new key order
    reset_requested = Signal()

    def __init__(self, entries: list[ColumnEntry], parent=None):
        super().__init__(parent)
        self.setObjectName("ColumnVisibilityPopover")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setWindowFlags(Qt.WindowType.Popup)

        self._entries: list[ColumnEntry] = list(entries)

        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Filter columns...")
        self._search.textChanged.connect(self.set_filter)

        self._model = QStandardItemModel(self)
        self._view = QListView(self)
        self._view.setModel(self._model)
        self._view.setDragDropMode(QListView.DragDropMode.InternalMove)
        self._view.setDefaultDropAction(Qt.DropAction.MoveAction)
        self._view.setMovement(QListView.Movement.Snap)
        self._model.itemChanged.connect(self._on_item_changed)
        self._model.rowsMoved.connect(lambda *_: self._emit_order())

        self._show_all_btn = QPushButton("Show all", self)
        self._hide_all_btn = QPushButton("Hide all", self)
        self._reset_btn = QPushButton("Reset", self)
        self._show_all_btn.clicked.connect(self.show_all)
        self._hide_all_btn.clicked.connect(self.hide_all)
        self._reset_btn.clicked.connect(self.reset_requested.emit)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self._show_all_btn)
        btn_row.addWidget(self._hide_all_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._reset_btn)

        layout = QVBoxLayout(self)
        layout.addWidget(self._search)
        layout.addWidget(self._view, 1)
        layout.addLayout(btn_row)

        self._populate()

    def _populate(self) -> None:
        self._model.clear()
        for entry in self._entries:
            item = QStandardItem(entry.label)
            item.setCheckable(True)
            item.setCheckState(Qt.CheckState.Checked if entry.visible else Qt.CheckState.Unchecked)
            item.setData(entry.key, Qt.ItemDataRole.UserRole)
            if entry.frozen:
                flags = item.flags()
                item.setFlags(flags & ~Qt.ItemFlag.ItemIsUserCheckable)
                item.setToolTip("Frozen — cannot be hidden")
            self._model.appendRow(item)

    def set_filter(self, text: str) -> None:
        text_lower = text.lower()
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            self._view.setRowHidden(row, text_lower not in item.text().lower())

    def visible_entry_keys(self) -> list[str]:
        keys = []
        for row in range(self._model.rowCount()):
            if not self._view.isRowHidden(row):
                keys.append(self._model.item(row).data(Qt.ItemDataRole.UserRole))
        return keys

    def set_visible(self, key: str, visible: bool) -> None:
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            if item.data(Qt.ItemDataRole.UserRole) == key:
                item.setCheckState(Qt.CheckState.Checked if visible else Qt.CheckState.Unchecked)
                return

    def show_all(self) -> None:
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(Qt.CheckState.Checked)

    def hide_all(self) -> None:
        for row in range(self._model.rowCount()):
            item = self._model.item(row)
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(Qt.CheckState.Unchecked)

    def _on_item_changed(self, item: QStandardItem) -> None:
        key = item.data(Qt.ItemDataRole.UserRole)
        visible = item.checkState() == Qt.CheckState.Checked
        self.visibility_changed.emit(key, visible)

    def _emit_order(self) -> None:
        order = [self._model.item(row).data(Qt.ItemDataRole.UserRole)
                 for row in range(self._model.rowCount())]
        self.reorder_requested.emit(order)
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_column_visibility_popover.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/catalogs/ui/column_visibility_popover.py tests/test_column_visibility_popover.py
git commit -m "feat(catalogs): ColumnVisibilityPopover widget"
```

---

## Task 11: Wire popover into `CatalogBrowser` toolbar + header context menu

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_browser.py`

- [ ] **Step 1: Add the toolbar button**

In `__init__`, after the event toolbar `_delete_btn` block:

```python
        from SciQLop.components.theming import get_icon
        self._columns_btn = QToolButton()
        self._columns_btn.setToolTip("Show / hide / reorder columns")
        self._columns_btn.setIcon(get_icon("view_column"))
        self._columns_btn.setAutoRaise(True)
        self._columns_btn.clicked.connect(self._open_column_popover)
        event_toolbar.addWidget(self._columns_btn)
```

(`view_column` icon should resolve in the existing icon set — if missing, fall back to a text label `"Columns"` via `setText`.)

- [ ] **Step 2: Add header context menu and popover opener**

Add to `__init__`:

```python
        self._event_table.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._event_table.horizontalHeader().customContextMenuRequested.connect(
            lambda pos: self._open_column_popover(at_header_pos=pos)
        )
```

Add the methods:

```python
    def _build_column_entries(self):
        from .column_visibility_popover import ColumnEntry
        entries = []
        header = self._event_table.horizontalHeader()
        order = [header.logicalIndex(visual)
                 for visual in range(self._event_model.columnCount())]
        fixed_count = len(self._event_model._FIXED_COLUMNS)
        for logical in order:
            key = self._column_key(logical)
            entries.append(ColumnEntry(
                key=key,
                label=key,
                visible=not self._event_table.isColumnHidden(logical),
                frozen=logical < fixed_count,
            ))
        return entries

    def _open_column_popover(self, at_header_pos=None) -> None:
        if self._event_model.columnCount() == 0:
            return
        from .column_visibility_popover import ColumnVisibilityPopover
        popover = ColumnVisibilityPopover(self._build_column_entries(), self)
        popover.visibility_changed.connect(self._on_column_visibility_changed)
        popover.reorder_requested.connect(self._on_column_reorder_requested)
        popover.reset_requested.connect(self._on_columns_reset)
        if at_header_pos is None:
            global_pos = self._columns_btn.mapToGlobal(self._columns_btn.rect().bottomLeft())
        else:
            global_pos = self._event_table.horizontalHeader().mapToGlobal(at_header_pos)
        popover.move(global_pos)
        popover.resize(Metrics.em(28), Metrics.ex(30))
        popover.show()
        popover.setFocus()

    def _on_column_visibility_changed(self, key: str, visible: bool) -> None:
        for col in range(self._event_model.columnCount()):
            if self._column_key(col) == key:
                self._event_table.setColumnHidden(col, not visible)
                break
        self._save_view_state()

    def _on_column_reorder_requested(self, new_order: list) -> None:
        self._reorder_columns(new_order)
        self._save_view_state()

    def _on_columns_reset(self) -> None:
        from ..backend.event_table_view_state import CatalogViewState, save_view_state
        if self._current_catalog is None:
            return
        save_view_state(self._current_catalog.uuid, CatalogViewState())
        for col in range(self._event_model.columnCount()):
            self._event_table.setColumnHidden(col, False)
```

Add at the top of the file:

```python
from SciQLop.core.ui import Metrics
```

(if not already imported).

- [ ] **Step 3: Manual smoke check**

Run: `uv run sciqlop`
Verify: open a catalog; click "Columns"; popover opens, search filters, checkboxes hide/show columns, drag reorders, Show all / Hide all / Reset behave as advertised. Right-click on the table header opens the same popover.

- [ ] **Step 4: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_browser.py
git commit -m "feat(catalogs): Columns popover button + header context menu"
```

---

## Task 12: Free-form attribute add/remove (new column)

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_browser.py`
- Test: `tests/test_event_table_editing.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_event_table_editing.py`:

```python
def test_add_attribute_creates_new_meta_column_for_selected_events(qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from PySide6.QtCore import QItemSelectionModel

    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    browser._current_provider = provider
    browser._current_catalog = cat
    browser._event_model.set_context(provider, cat)
    browser._event_model.set_events(provider.events(cat))
    sm = browser._event_table.selectionModel()
    for row in (0, 1):
        sm.select(
            browser._sort_proxy.index(row, 0),
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows,
        )

    browser._add_attribute_to_selection("note", "")

    events = provider.events(cat)
    assert events[0].meta.get("note") == ""
    assert events[1].meta.get("note") == ""
    assert "note" in browser._event_model._meta_keys
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_event_table_editing.py::test_add_attribute_creates_new_meta_column_for_selected_events -v`
Expected: FAIL.

- [ ] **Step 3: Add the toolbar button and helper**

In `__init__`, after the `_columns_btn` block, add a "+ Attribute" button to `event_toolbar`:

```python
        self._add_attr_btn = QToolButton()
        self._add_attr_btn.setText("+ Attribute")
        self._add_attr_btn.setToolTip("Add a new metadata attribute to the selected events")
        self._add_attr_btn.clicked.connect(self._on_add_attribute_clicked)
        event_toolbar.addWidget(self._add_attr_btn)
```

And the methods:

```python
    def _on_add_attribute_clicked(self) -> None:
        if self._current_provider is None or self._current_catalog is None:
            return
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Add attribute", "Attribute name:")
        if not ok or not name:
            return
        self._add_attribute_to_selection(name, "")

    def _add_attribute_to_selection(self, key: str, value) -> None:
        sm = self._event_table.selectionModel()
        events = []
        if sm is not None:
            for proxy_idx in sm.selectedRows():
                source_idx = self._sort_proxy.mapToSource(proxy_idx)
                ev = self._event_model.event_at(source_idx.row())
                if ev is not None:
                    events.append(ev)
        if not events:
            events = list(self._current_provider.events(self._current_catalog))
        self._current_provider.set_events_meta(self._current_catalog, events, key, value)
```

The model already extends `_meta_keys` on `event_meta_changed` for unknown keys (Task 5, step 4).

- [ ] **Step 4: Capability gate the button**

In `_update_toolbar`:

```python
        self._add_attr_btn.setVisible(Capability.EDIT_EVENTS in caps)
        self._columns_btn.setVisible(self._event_model.columnCount() > 0)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/test_event_table_editing.py -v`
Expected: 6 passed.

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_browser.py tests/test_event_table_editing.py
git commit -m "feat(catalogs): + Attribute button to add free-form metadata"
```

---

## Task 13: Speasy provider stays read-only — verification test

**Files:**
- Test: `tests/test_event_table_editing.py`

- [ ] **Step 1: Write the test**

Append to `tests/test_event_table_editing.py`:

```python
def test_speasy_provider_event_table_is_read_only(qtbot, qapp):
    pytest.importorskip("speasy")
    from PySide6.QtCore import Qt
    from SciQLop.plugins.speasy_catalogs.speasy_provider import SpeasyCatalogProvider

    provider = SpeasyCatalogProvider()
    catalogs = provider.catalogs()
    if not catalogs:
        pytest.skip("Speasy returned no catalogs in test environment")
    cat = catalogs[0]
    events = provider.events(cat)
    if not events:
        pytest.skip("Speasy catalog had no events")

    model = EventTableModel()
    model.set_context(provider, cat)
    model.set_events(events)
    assert not (model.flags(model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable)
    assert model.setData(model.index(0, 0), "anything") is False
```

Adjust the import path if the speasy provider lives in a different module.

- [ ] **Step 2: Run tests**

Run: `uv run pytest tests/test_event_table_editing.py::test_speasy_provider_event_table_is_read_only -v`
Expected: PASS or SKIPPED.

- [ ] **Step 3: Commit**

```bash
git add tests/test_event_table_editing.py
git commit -m "test(catalogs): speasy event table stays read-only"
```

---

## Task 14: Update backlog and changelog

**Files:**
- Modify: `CHANGELOG.md`
- Modify: `/home/jeandet/.claude/projects/-var-home-jeandet-Documents-prog-SciQLop/memory/backlog.md`

- [ ] **Step 1: Update changelog**

Add under the unreleased section (follow the convention from `changelog-convention.md`):

```
### Added
- Editable event table with type-aware editor widgets reusing the settings delegate registry.
- Multi-row selection with bulk edit (edit one cell with N rows selected → applies to all).
- "Columns" popover (search + checklist + drag-reorder + Show all / Hide all / Reset) reachable from a toolbar button or by right-clicking the event-table header.
- "+ Attribute" button to add a new metadata key to the selected events.
- Per-catalog column visibility and order persisted in `EventTableViewState` settings.

### Changed
- `CatalogProvider` API gains `set_event_meta`, `remove_event_meta`, `set_events_meta` and an `event_meta_changed` signal. Tscat and cocat providers route writes through their respective backends. Speasy events stay read-only via capability gating.
```

- [ ] **Step 2: Update backlog memory**

Edit `/home/jeandet/.claude/projects/-var-home-jeandet-Documents-prog-SciQLop/memory/backlog.md`:

```diff
-- Event metadata display/edition (#22)
-- Event multi-selection & bulk-edition (#21)
+- ~~Event metadata display/edition (#22)~~ ✅ 2026-04-30 — editable EventTableModel + type-aware delegate
+- ~~Event multi-selection & bulk-edition (#21)~~ ✅ 2026-04-30 — ExtendedSelection + setData propagation
```

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: log #22 + #21 (event metadata edition + bulk edit)"
```

(`backlog.md` is in the user's `.claude` memory dir — update there but don't commit it from the repo.)

---

## Manual smoke tests

### Cocat event metadata round-trip
1. Start a local cocat server (see cocat library README).
2. Open SciQLop, join a room with at least one catalog and one event.
3. Edit the `tags` cell in the event table; confirm the value persists after rejoining.
4. From a second client joined to the same room, verify the change appears within ~1s.

### End-to-end ergonomics
1. Open a tscat catalog with ~50 events.
2. Click in a `class` cell, type a value, press Enter — verify the cell updates and a save indicator appears.
3. Select 5 rows, edit one cell — verify all 5 rows update.
4. Click the "Columns" button — verify the popover opens, search filters, drag reorders, hide checkbox hides the column, and the choice survives an app restart.
5. Right-click the table header — verify the same popover appears.
6. Switch to a Speasy catalog — verify cells are not editable and the "+ Attribute" / Delete / Add buttons are hidden.
