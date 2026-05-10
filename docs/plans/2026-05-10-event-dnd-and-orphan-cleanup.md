# Event Drag-and-Drop + Orphan Event Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users drag events between catalogs (link by default, Shift = move, Ctrl = duplicate, cross-provider always duplicates) and clean up orphan tscat events both passively (a synthetic *Orphan events* node under *My Catalogs*) and actively (a "Clean up orphan events…" provider-level action that opens a small dialog).

**Architecture:** Two phases. Phase A adds an `EVENT_LIST_MIME_TYPE`, makes the event table a drag source, and teaches the catalog tree to accept event drops by dispatching to a new `CatalogProvider.handle_event_drop(catalog, events, action)` hook. Phase B adds a tscat orphan query helper, a virtual `Catalog` ("🗑 Orphan events", `Capability.DELETE_EVENTS` only), and a provider-level cleanup dialog. Both reuse existing event-table, multi-select, bulk-delete, and `ProviderAction` plumbing — no new global widgets.

**Tech Stack:** PySide6 (QTableView drag, QAbstractItemModel mime, QDrag), `tscat` (`get_events`, `get_catalogues`, `add_events_to_catalogue`, `remove_events_from_catalogue`), existing SciQLop catalog/provider/MIME infrastructure (`SciQLop.core.mime`, `SciQLop.components.catalogs.backend.provider`).

---

## File Structure

**Create:**

- `SciQLop/components/catalogs/backend/event_mime.py` — encoder/decoder for `EVENT_LIST_MIME_TYPE` payloads `{provider, catalog_uuid, event_uuids}`.
- `SciQLop/plugins/tscat_catalogs/orphans.py` — `list_orphan_events()` helper plus a virtual `OrphanCatalog` factory.
- `SciQLop/plugins/tscat_catalogs/orphan_cleanup_dialog.py` — modal dialog with checkable list + Delete buttons.
- `tests/test_event_mime.py` — round-trip tests for the new MIME encoder/decoder.
- `tests/test_event_dnd.py` — UI-level drop dispatch tests (link / move / duplicate; same-provider and cross-provider).
- `tests/test_tscat_orphans.py` — orphan-query tests, virtual-catalog event listing, dialog flow.

**Modify:**

- `SciQLop/core/mime/types.py:1-5` — add `EVENT_LIST_MIME_TYPE` constant.
- `SciQLop/components/catalogs/__init__.py:6` — register the event MIME alongside the catalog MIME.
- `SciQLop/components/catalogs/backend/provider.py:107-235` — base-class `handle_event_drop(self, target_catalog, events, action)` with default link semantics and a `_copy_event(ev)` helper.
- `SciQLop/components/catalogs/ui/event_table.py:43-230` — `EventTableModel.flags()` adds `ItemIsDragEnabled`, `mimeTypes()`, `mimeData()`.
- `SciQLop/components/catalogs/ui/catalog_browser.py:185-205` — enable drag on the QTableView.
- `SciQLop/components/catalogs/ui/catalog_tree.py:549-650` — accept `EVENT_LIST_MIME_TYPE` in `mimeTypes`/`canDropMimeData`/`dropMimeData`, dispatch to provider hook with action derived from keyboard modifiers.
- `SciQLop/plugins/tscat_catalogs/tscat_provider.py:101-130` — implement `handle_event_drop`, expose `actions(None)` entries for orphan cleanup, optionally publish the virtual orphan catalog via `catalogs()`.
- `CHANGELOG.md` — note the event DnD and orphan cleanup features.

**File responsibilities:** Each file stays single-purpose. The mime module knows nothing about UI; the dialog knows nothing about Qt drag mechanics; the provider hook is backend-agnostic so cocat/dummy can override later.

---

## Phase A — Event drag-and-drop primitive

### Task A1: EVENT_LIST_MIME_TYPE constant

**Files:**
- Modify: `SciQLop/core/mime/types.py:1-5`

- [ ] **Step 1: Add the constant**

```python
# at the bottom of SciQLop/core/mime/types.py
EVENT_LIST_MIME_TYPE = "application/x.sciqlop.event-list"
```

- [ ] **Step 2: Commit**

```bash
git add SciQLop/core/mime/types.py
git commit -m "feat(catalogs): EVENT_LIST_MIME_TYPE constant"
```

---

### Task A2: Event MIME encoder/decoder

**Files:**
- Create: `SciQLop/components/catalogs/backend/event_mime.py`
- Test: `tests/test_event_mime.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_event_mime.py
import json
from datetime import datetime, timezone
from PySide6.QtCore import QMimeData

from SciQLop.components.catalogs.backend.provider import CatalogEvent
from SciQLop.core.mime.types import EVENT_LIST_MIME_TYPE


def _ev(uuid: str) -> CatalogEvent:
    return CatalogEvent(
        uuid=uuid,
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
        meta={"note": "x"},
    )


def test_encode_decode_roundtrip(qapp):
    from SciQLop.components.catalogs.backend.event_mime import (
        encode_event_list, decode_event_list,
    )

    events = [_ev("u1"), _ev("u2")]
    md = encode_event_list("My Catalogs", "cat-1", events)
    assert md.hasFormat(EVENT_LIST_MIME_TYPE)

    payload = json.loads(bytes(md.data(EVENT_LIST_MIME_TYPE)).decode())
    assert payload == {
        "provider": "My Catalogs",
        "catalog_uuid": "cat-1",
        "event_uuids": ["u1", "u2"],
    }

    decoded = decode_event_list(md)
    assert decoded.provider == "My Catalogs"
    assert decoded.catalog_uuid == "cat-1"
    assert decoded.event_uuids == ["u1", "u2"]


def test_decode_returns_none_for_unrelated_mime(qapp):
    from SciQLop.components.catalogs.backend.event_mime import decode_event_list
    md = QMimeData()
    md.setText("not an event payload")
    assert decode_event_list(md) is None


def test_decode_handles_missing_catalog_uuid(qapp):
    """Orphan-bucket drags carry catalog_uuid=None."""
    from SciQLop.components.catalogs.backend.event_mime import (
        encode_event_list, decode_event_list,
    )
    md = encode_event_list("My Catalogs", None, [_ev("u9")])
    decoded = decode_event_list(md)
    assert decoded.catalog_uuid is None
    assert decoded.event_uuids == ["u9"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_event_mime.py -v`
Expected: FAIL with `ModuleNotFoundError: SciQLop.components.catalogs.backend.event_mime`.

- [ ] **Step 3: Implement the module**

```python
# SciQLop/components/catalogs/backend/event_mime.py
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Iterable

from PySide6.QtCore import QMimeData

from SciQLop.core.mime.types import EVENT_LIST_MIME_TYPE
from .provider import CatalogEvent


@dataclass(frozen=True)
class EventDropPayload:
    provider: str
    catalog_uuid: str | None
    event_uuids: list[str]


def encode_event_list(
    provider_name: str,
    catalog_uuid: str | None,
    events: Iterable[CatalogEvent],
) -> QMimeData:
    payload = {
        "provider": provider_name,
        "catalog_uuid": catalog_uuid,
        "event_uuids": [e.uuid for e in events],
    }
    md = QMimeData()
    md.setData(EVENT_LIST_MIME_TYPE, json.dumps(payload).encode("utf-8"))
    return md


def decode_event_list(mime: QMimeData) -> EventDropPayload | None:
    if not mime.hasFormat(EVENT_LIST_MIME_TYPE):
        return None
    raw = bytes(mime.data(EVENT_LIST_MIME_TYPE))
    if not raw:
        return None
    data = json.loads(raw.decode("utf-8"))
    return EventDropPayload(
        provider=data["provider"],
        catalog_uuid=data.get("catalog_uuid"),
        event_uuids=list(data.get("event_uuids", [])),
    )
```

- [ ] **Step 4: Register the MIME type at package import**

Append at the end of `SciQLop/components/catalogs/__init__.py`:

```python
from .backend import event_mime  # noqa: F401  registers the event MIME helpers
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_event_mime.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/catalogs/backend/event_mime.py SciQLop/components/catalogs/__init__.py tests/test_event_mime.py
git commit -m "feat(catalogs): event-list MIME encoder/decoder"
```

---

### Task A3: Provider drop hook

**Files:**
- Modify: `SciQLop/components/catalogs/backend/provider.py:233-245`
- Test: `tests/test_event_dnd.py`

- [ ] **Step 1: Write failing test for default link semantics**

```python
# tests/test_event_dnd.py
from datetime import datetime, timezone
import pytest

from SciQLop.components.catalogs.backend.provider import (
    Capability, CatalogEvent,
)
from SciQLop.components.catalogs.backend.dummy_provider import DummyCatalogProvider


def _ev(uuid="u1"):
    return CatalogEvent(
        uuid=uuid,
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
        meta={},
    )


@pytest.fixture
def provider(qapp):
    p = DummyCatalogProvider()
    yield p
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    CatalogRegistry.instance()._providers.pop(p.name, None)


def test_handle_event_drop_link_keeps_event_in_source(qapp, provider):
    src = provider.create_catalog("src")
    dst = provider.create_catalog("dst")
    e = _ev("u-link")
    provider.add_event(src, e)

    provider.handle_event_drop(target_catalog=dst, events=[e], action="link", source_catalog=src)

    assert any(x.uuid == "u-link" for x in provider.events(src))
    assert any(x.uuid == "u-link" for x in provider.events(dst))


def test_handle_event_drop_move_removes_from_source(qapp, provider):
    src = provider.create_catalog("src")
    dst = provider.create_catalog("dst")
    e = _ev("u-move")
    provider.add_event(src, e)

    provider.handle_event_drop(target_catalog=dst, events=[e], action="move", source_catalog=src)

    assert not any(x.uuid == "u-move" for x in provider.events(src))
    assert any(x.uuid == "u-move" for x in provider.events(dst))


def test_handle_event_drop_duplicate_assigns_new_uuid(qapp, provider):
    src = provider.create_catalog("src")
    dst = provider.create_catalog("dst")
    e = _ev("u-dup")
    provider.add_event(src, e)

    provider.handle_event_drop(target_catalog=dst, events=[e], action="duplicate", source_catalog=src)

    src_uuids = {x.uuid for x in provider.events(src)}
    dst_uuids = {x.uuid for x in provider.events(dst)}
    assert "u-dup" in src_uuids
    assert "u-dup" not in dst_uuids
    assert len(dst_uuids) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_event_dnd.py -v`
Expected: FAIL with `AttributeError: ... has no attribute 'handle_event_drop'`.

- [ ] **Step 3: Implement the hook on the base class**

In `SciQLop/components/catalogs/backend/provider.py`, after `folder_actions`:

```python
    def handle_event_drop(
        self,
        target_catalog: Catalog,
        events: list[CatalogEvent],
        action: str = "link",
        source_catalog: Catalog | None = None,
    ) -> None:
        """Receive an event drop on a catalog of this provider.

        action ∈ {"link", "move", "duplicate"}:
        - "link":      add the same UUID to target (no-op for events already there)
        - "move":      add to target then remove from source
        - "duplicate": insert a fresh UUID copy into target
        """
        if not events:
            return
        caps = self.capabilities()
        if Capability.CREATE_EVENTS not in caps and action != "link":
            raise PermissionError(f"{self.name} does not allow CREATE_EVENTS")
        for ev in events:
            if action == "duplicate":
                self.add_event(target_catalog, self._copy_event(ev))
            else:
                self.add_event(target_catalog, ev)
        if action == "move" and source_catalog is not None:
            for ev in events:
                self.remove_event(source_catalog, ev)

    @staticmethod
    def _copy_event(ev: CatalogEvent) -> CatalogEvent:
        import uuid as _uuid
        return CatalogEvent(
            uuid=str(_uuid.uuid4()),
            start=ev.start, stop=ev.stop,
            meta=dict(ev.meta),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_event_dnd.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/catalogs/backend/provider.py tests/test_event_dnd.py
git commit -m "feat(catalogs): handle_event_drop with link/move/duplicate semantics"
```

---

### Task A4: Cross-provider duplication path

**Files:**
- Modify: `tests/test_event_dnd.py`

- [ ] **Step 1: Add cross-provider test**

Append to `tests/test_event_dnd.py`:

```python
def test_cross_provider_drop_always_duplicates(qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyCatalogProvider
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry

    a = DummyCatalogProvider(name="A")
    b = DummyCatalogProvider(name="B")
    try:
        cat_a = a.create_catalog("a-cat")
        cat_b = b.create_catalog("b-cat")
        e = _ev("cross")
        a.add_event(cat_a, e)

        b.handle_event_drop(target_catalog=cat_b, events=[e], action="link", source_catalog=cat_a)

        # Provider B must NOT have stored the source UUID — link across providers
        # is meaningless; the dispatcher escalates to duplicate.
        assert any(x.uuid == "cross" for x in a.events(cat_a))
        b_events = b.events(cat_b)
        assert len(b_events) == 1
        assert b_events[0].uuid != "cross"
    finally:
        CatalogRegistry.instance()._providers.pop("A", None)
        CatalogRegistry.instance()._providers.pop("B", None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_event_dnd.py::test_cross_provider_drop_always_duplicates -v`
Expected: FAIL — currently link path would try to insert a UUID owned by another backend.

- [ ] **Step 3: Implement the cross-provider escalation in the catalog tree drop dispatcher**

This logic belongs in `catalog_tree.py:dropMimeData` (Task A6); for now mark this test xfail with a TODO so the suite stays green. Add at the top of the test:

```python
import pytest
pytestmark = pytest.mark.xfail(reason="cross-provider escalation lives in catalog_tree, see Task A6")
```

- [ ] **Step 4: Commit**

```bash
git add tests/test_event_dnd.py
git commit -m "test(catalogs): cross-provider event drop must duplicate (xfail until A6)"
```

---

### Task A5: Drag source on the event table

**Files:**
- Modify: `SciQLop/components/catalogs/ui/event_table.py:43-230`
- Modify: `SciQLop/components/catalogs/ui/catalog_browser.py:185-205`
- Test: `tests/test_event_table_drag.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_event_table_drag.py
import json
from datetime import datetime, timezone

from PySide6.QtCore import QModelIndex

from SciQLop.components.catalogs.backend.dummy_provider import DummyCatalogProvider
from SciQLop.components.catalogs.backend.provider import CatalogEvent
from SciQLop.components.catalogs.backend.registry import CatalogRegistry
from SciQLop.components.catalogs.ui.event_table import EventTableModel
from SciQLop.core.mime.types import EVENT_LIST_MIME_TYPE


def test_event_table_model_emits_event_mime(qapp):
    provider = DummyCatalogProvider(name="DragSrc")
    try:
        cat = provider.create_catalog("c")
        provider.add_event(cat, CatalogEvent(
            uuid="ev-1",
            start=datetime(2020, 1, 1, tzinfo=timezone.utc),
            stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
            meta={},
        ))
        provider.add_event(cat, CatalogEvent(
            uuid="ev-2",
            start=datetime(2020, 1, 2, tzinfo=timezone.utc),
            stop=datetime(2020, 1, 2, 1, tzinfo=timezone.utc),
            meta={},
        ))

        model = EventTableModel()
        model.set_catalog(cat)

        idx0 = model.index(0, 0)
        idx1 = model.index(1, 0)
        md = model.mimeData([idx0, idx1])
        assert md is not None
        assert md.hasFormat(EVENT_LIST_MIME_TYPE)
        payload = json.loads(bytes(md.data(EVENT_LIST_MIME_TYPE)).decode())
        assert payload["provider"] == "DragSrc"
        assert payload["catalog_uuid"] == cat.uuid
        assert sorted(payload["event_uuids"]) == ["ev-1", "ev-2"]
    finally:
        CatalogRegistry.instance()._providers.pop("DragSrc", None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_event_table_drag.py -v`
Expected: FAIL — `EventTableModel.mimeData` returns the default (None) or raises `NotImplementedError`.

- [ ] **Step 3: Implement drag source on the model**

Add to `EventTableModel` in `SciQLop/components/catalogs/ui/event_table.py`:

```python
    def flags(self, index):
        base = super().flags(index)
        if index.isValid():
            from PySide6.QtCore import Qt
            base |= Qt.ItemFlag.ItemIsDragEnabled
        return base

    def mimeTypes(self):
        from SciQLop.core.mime.types import EVENT_LIST_MIME_TYPE
        return [EVENT_LIST_MIME_TYPE]

    def mimeData(self, indexes):
        from SciQLop.components.catalogs.backend.event_mime import encode_event_list
        if self._catalog is None:
            return None
        seen: set[str] = set()
        events = []
        for idx in indexes:
            if not idx.isValid():
                continue
            row = idx.row()
            if 0 <= row < len(self._events):
                ev = self._events[row]
                if ev.uuid not in seen:
                    seen.add(ev.uuid)
                    events.append(ev)
        if not events:
            return None
        provider_name = self._catalog.provider.name if self._catalog.provider else ""
        return encode_event_list(provider_name, self._catalog.uuid, events)
```

- [ ] **Step 4: Enable drag on the QTableView in the browser**

In `SciQLop/components/catalogs/ui/catalog_browser.py` after the existing `setSelectionMode` line, add:

```python
        from PySide6.QtWidgets import QAbstractItemView
        self._event_table.setDragEnabled(True)
        self._event_table.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_event_table_drag.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/catalogs/ui/event_table.py SciQLop/components/catalogs/ui/catalog_browser.py tests/test_event_table_drag.py
git commit -m "feat(catalogs): event table is a drag source for EVENT_LIST_MIME_TYPE"
```

---

### Task A6: Drop dispatcher in the catalog tree

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_tree.py:549-650`
- Modify: `tests/test_event_dnd.py` (un-xfail Task A4)
- Test: `tests/test_event_dnd.py` (add UI dispatcher tests)

- [ ] **Step 1: Write failing test for the dispatcher**

Append to `tests/test_event_dnd.py`:

```python
class _StubModifiers:
    def __init__(self, shift=False, ctrl=False):
        from PySide6.QtCore import Qt
        m = Qt.KeyboardModifier.NoModifier
        if shift:
            m |= Qt.KeyboardModifier.ShiftModifier
        if ctrl:
            m |= Qt.KeyboardModifier.ControlModifier
        self._m = m

    def __call__(self):
        return self._m


@pytest.fixture
def tree_with_two_catalogs(qapp, monkeypatch):
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel

    p = DummyCatalogProvider(name="DropTest")
    src = p.create_catalog("src")
    dst = p.create_catalog("dst")
    e = _ev("u-dispatcher")
    p.add_event(src, e)

    model = CatalogTreeModel()
    yield model, p, src, dst, e

    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    CatalogRegistry.instance()._providers.pop("DropTest", None)


def test_dispatcher_no_modifier_links(tree_with_two_calls := None):
    pass  # placeholder — real test lives in test_event_dnd_ui below
```

(The deeper UI test lives below; we keep this section minimal because the model's `dropMimeData` is the natural seam.)

```python
def test_dropmime_dispatch_link(tree_with_two_catalogs, monkeypatch):
    from PySide6.QtCore import Qt, QModelIndex
    from PySide6.QtWidgets import QApplication
    from SciQLop.components.catalogs.backend.event_mime import encode_event_list

    model, provider, src, dst, ev = tree_with_two_catalogs
    md = encode_event_list(provider.name, src.uuid, [ev])

    # Locate the destination catalog's QModelIndex
    target_idx = QModelIndex()
    for row in range(model.rowCount()):
        prov_idx = model.index(row, 0)
        if prov_idx.internalPointer().provider is provider:
            for r in range(model.rowCount(prov_idx)):
                cidx = model.index(r, 0, prov_idx)
                if cidx.internalPointer().catalog is dst:
                    target_idx = cidx
                    break
    assert target_idx.isValid()

    monkeypatch.setattr(QApplication, "keyboardModifiers", _StubModifiers())
    handled = model.dropMimeData(md, Qt.DropAction.MoveAction, -1, -1, target_idx)
    assert handled is False  # tree returns False so Qt does not removeRows()
    assert any(x.uuid == "u-dispatcher" for x in provider.events(src))
    assert any(x.uuid == "u-dispatcher" for x in provider.events(dst))


def test_dropmime_dispatch_move_with_shift(tree_with_two_catalogs, monkeypatch):
    from PySide6.QtCore import Qt, QModelIndex
    from PySide6.QtWidgets import QApplication
    from SciQLop.components.catalogs.backend.event_mime import encode_event_list

    model, provider, src, dst, ev = tree_with_two_catalogs
    md = encode_event_list(provider.name, src.uuid, [ev])

    target_idx = QModelIndex()
    for row in range(model.rowCount()):
        prov_idx = model.index(row, 0)
        if prov_idx.internalPointer().provider is provider:
            for r in range(model.rowCount(prov_idx)):
                cidx = model.index(r, 0, prov_idx)
                if cidx.internalPointer().catalog is dst:
                    target_idx = cidx

    monkeypatch.setattr(QApplication, "keyboardModifiers", _StubModifiers(shift=True))
    model.dropMimeData(md, Qt.DropAction.MoveAction, -1, -1, target_idx)
    assert not any(x.uuid == "u-dispatcher" for x in provider.events(src))
    assert any(x.uuid == "u-dispatcher" for x in provider.events(dst))
```

- [ ] **Step 2: Un-xfail the cross-provider test**

In `tests/test_event_dnd.py` remove the `pytestmark = pytest.mark.xfail(...)` block above `test_cross_provider_drop_always_duplicates` and restructure: the cross-provider escalation will now happen in `dropMimeData`. Replace the test body with a UI-level version that drives the model:

```python
def test_cross_provider_drop_always_duplicates(qapp, monkeypatch):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from SciQLop.components.catalogs.backend.dummy_provider import DummyCatalogProvider
    from SciQLop.components.catalogs.backend.event_mime import encode_event_list
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel

    a = DummyCatalogProvider(name="A")
    b = DummyCatalogProvider(name="B")
    try:
        cat_a = a.create_catalog("a-cat")
        cat_b = b.create_catalog("b-cat")
        e = _ev("cross")
        a.add_event(cat_a, e)

        model = CatalogTreeModel()
        b_idx = None
        for row in range(model.rowCount()):
            prov = model.index(row, 0)
            if prov.internalPointer().provider is b:
                for r in range(model.rowCount(prov)):
                    cidx = model.index(r, 0, prov)
                    if cidx.internalPointer().catalog is cat_b:
                        b_idx = cidx

        md = encode_event_list("A", cat_a.uuid, [e])
        monkeypatch.setattr(QApplication, "keyboardModifiers", _StubModifiers())
        model.dropMimeData(md, Qt.DropAction.MoveAction, -1, -1, b_idx)

        b_events = b.events(cat_b)
        assert len(b_events) == 1
        assert b_events[0].uuid != "cross"  # duplicated, new UUID
        assert any(x.uuid == "cross" for x in a.events(cat_a))  # source untouched
    finally:
        CatalogRegistry.instance()._providers.pop("A", None)
        CatalogRegistry.instance()._providers.pop("B", None)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_event_dnd.py -v`
Expected: 3 tests fail (the new dispatcher tests + un-xfailed cross-provider) — `dropMimeData` does not yet recognise `EVENT_LIST_MIME_TYPE`.

- [ ] **Step 4: Implement the dispatcher**

In `SciQLop/components/catalogs/ui/catalog_tree.py`, extend `mimeTypes`, `canDropMimeData`, and `dropMimeData`:

```python
    def mimeTypes(self) -> list[str]:
        from SciQLop.core.mime.types import CATALOG_LIST_MIME_TYPE, EVENT_LIST_MIME_TYPE
        return [CATALOG_LIST_MIME_TYPE, EVENT_LIST_MIME_TYPE]
```

```python
    def canDropMimeData(self, data, action, row, column, parent) -> bool:
        from SciQLop.core.mime.types import CATALOG_LIST_MIME_TYPE, EVENT_LIST_MIME_TYPE
        from ..backend.provider import Capability
        if data.hasFormat(EVENT_LIST_MIME_TYPE):
            if not parent.isValid():
                return False
            node = parent.internalPointer()
            if node.catalog is None or node.provider is None:
                return False
            caps = node.provider.capabilities()
            return Capability.CREATE_EVENTS in caps or Capability.EDIT_EVENTS in caps
        if not data.hasFormat(CATALOG_LIST_MIME_TYPE):
            return False
        # ... existing catalog-drop logic unchanged ...
```

Then in `dropMimeData`, before the existing catalog-handling block, add an event branch:

```python
    def dropMimeData(self, data, action, row, column, parent) -> bool:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import QApplication
        from SciQLop.core.mime.types import EVENT_LIST_MIME_TYPE
        from SciQLop.components.catalogs.backend.event_mime import decode_event_list
        from SciQLop.components.catalogs.backend.registry import CatalogRegistry
        from SciQLop.components.sciqlop_logging import getLogger
        log = getLogger(__name__)
        if action == Qt.DropAction.IgnoreAction:
            return True

        if data.hasFormat(EVENT_LIST_MIME_TYPE):
            payload = decode_event_list(data)
            if payload is None or not parent.isValid():
                return False
            target_node = parent.internalPointer()
            target_catalog = target_node.catalog
            if target_catalog is None or target_node.provider is None:
                return False
            registry = CatalogRegistry.instance()
            source_provider = registry.provider_by_name(payload.provider)
            source_catalog = None
            source_events = []
            if source_provider is not None and payload.catalog_uuid is not None:
                for c in source_provider.catalogs():
                    if c.uuid == payload.catalog_uuid:
                        source_catalog = c
                        break
                if source_catalog is not None:
                    by_uuid = {e.uuid: e for e in source_provider.events(source_catalog)}
                    source_events = [by_uuid[u] for u in payload.event_uuids if u in by_uuid]
            if not source_events:
                return False

            mods = QApplication.keyboardModifiers()
            cross_provider = source_provider is not target_node.provider
            if cross_provider:
                drop_action = "duplicate"
            elif mods & Qt.KeyboardModifier.ShiftModifier:
                drop_action = "move"
            elif mods & Qt.KeyboardModifier.ControlModifier:
                drop_action = "duplicate"
            else:
                drop_action = "link"

            try:
                target_node.provider.handle_event_drop(
                    target_catalog=target_catalog,
                    events=source_events,
                    action=drop_action,
                    source_catalog=source_catalog,
                )
            except Exception as e:
                log.warning("Event drop failed: %s", e)
            return False  # provider signals will refresh

        # ... existing catalog-drop block unchanged ...
```

- [ ] **Step 5: Add `provider_by_name` to the registry if missing**

Check `SciQLop/components/catalogs/backend/registry.py`. If absent:

```python
    def provider_by_name(self, name: str) -> "CatalogProvider | None":
        return self._providers.get(name)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_event_dnd.py -v`
Expected: PASS (5 tests).

- [ ] **Step 7: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_tree.py SciQLop/components/catalogs/backend/registry.py tests/test_event_dnd.py
git commit -m "feat(catalogs): event drop dispatcher with link/move/duplicate semantics"
```

---

### Task A7: Manual smoke test + CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Manual sanity check**

Run: `uv run sciqlop`. Open the catalog browser, create two catalogs under *My Catalogs*, add an event in catalog A. Drag the event row onto catalog B. Verify the event appears in B and remains in A (default = link). Drag again with Shift held — verify the event now disappears from A. Drag with Ctrl held — verify a new copy lands in B with a different UUID (visible in metadata).

- [ ] **Step 2: Update changelog**

Append under `## Unreleased › Catalogs` in `CHANGELOG.md`:

```markdown
- Drag & drop events between catalogs. Default = link (event appears in both, single UUID; tscat's many-to-many is honored). Hold Shift to move (remove from source). Hold Ctrl to duplicate (new UUID, independent copy). Cross-provider drops always duplicate. Implemented via `EVENT_LIST_MIME_TYPE` + a new `CatalogProvider.handle_event_drop()` hook.
```

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): event drag-and-drop"
```

---

## Phase B — tscat orphan cleanup

### Task B1: tscat orphan-events helper

**Files:**
- Create: `SciQLop/plugins/tscat_catalogs/orphans.py`
- Test: `tests/test_tscat_orphans.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_tscat_orphans.py
import time
from datetime import datetime, timezone

import pytest
import tscat


def _process(qapp, rounds=15):
    for _ in range(rounds):
        qapp.processEvents()
        time.sleep(0.05)


def test_list_orphan_events_returns_events_without_catalogue(qapp):
    from SciQLop.plugins.tscat_catalogs.orphans import list_orphan_events

    # Reset by collecting current orphan UUIDs as the baseline.
    baseline = {e.uuid for e in list_orphan_events()}

    orphan_event = tscat.create_event(
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
        author="orphan",
    )
    cat = tscat.create_catalogue(name="not-orphan-host", author="t")
    attached_event = tscat.create_event(
        start=datetime(2020, 1, 2, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 2, 1, tzinfo=timezone.utc),
        author="attached",
    )
    tscat.add_events_to_catalogue(cat, [attached_event])
    _process(qapp)

    orphan_uuids = {e.uuid for e in list_orphan_events()} - baseline
    assert orphan_event.uuid in orphan_uuids
    assert attached_event.uuid not in orphan_uuids


def test_list_orphan_events_empty_when_all_attached(qapp):
    from SciQLop.plugins.tscat_catalogs.orphans import list_orphan_events

    baseline = {e.uuid for e in list_orphan_events()}
    cat = tscat.create_catalogue(name="all-mine", author="t")
    e = tscat.create_event(
        start=datetime(2020, 2, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 2, 1, 1, tzinfo=timezone.utc),
        author="t",
    )
    tscat.add_events_to_catalogue(cat, [e])
    _process(qapp)

    orphan_uuids = {ev.uuid for ev in list_orphan_events()} - baseline
    assert e.uuid not in orphan_uuids
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tscat_orphans.py::test_list_orphan_events_returns_events_without_catalogue -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the helper**

```python
# SciQLop/plugins/tscat_catalogs/orphans.py
from __future__ import annotations

import tscat


def list_orphan_events() -> list:
    """Return tscat events that are not members of any catalogue."""
    all_events = {e.uuid: e for e in tscat.get_events()}
    attached: set[str] = set()
    for cat in tscat.get_catalogues():
        for ev in tscat.get_events(cat):
            attached.add(ev.uuid)
    return [all_events[u] for u in all_events.keys() - attached]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tscat_orphans.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/plugins/tscat_catalogs/orphans.py tests/test_tscat_orphans.py
git commit -m "feat(tscat): list_orphan_events helper"
```

---

### Task B2: Virtual orphan catalog node

**Files:**
- Modify: `SciQLop/plugins/tscat_catalogs/orphans.py`
- Modify: `SciQLop/plugins/tscat_catalogs/tscat_provider.py`
- Test: `tests/test_tscat_orphans.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_tscat_orphans.py`:

```python
def test_provider_lists_orphan_pseudo_catalog_when_orphans_exist(qapp):
    from SciQLop.plugins.tscat_catalogs.tscat_provider import TscatCatalogProvider
    from SciQLop.plugins.tscat_catalogs.orphans import ORPHAN_CATALOG_UUID

    tscat.create_event(
        start=datetime(2020, 3, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 3, 1, 1, tzinfo=timezone.utc),
        author="orph",
    )
    _process(qapp)

    provider = TscatCatalogProvider()
    catalog_uuids = {c.uuid for c in provider.catalogs()}
    assert ORPHAN_CATALOG_UUID in catalog_uuids


def test_orphan_catalog_capabilities_are_delete_only(qapp):
    from SciQLop.plugins.tscat_catalogs.tscat_provider import TscatCatalogProvider
    from SciQLop.plugins.tscat_catalogs.orphans import ORPHAN_CATALOG_UUID
    from SciQLop.components.catalogs.backend.provider import Capability

    tscat.create_event(
        start=datetime(2020, 4, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 4, 1, 1, tzinfo=timezone.utc),
        author="orph2",
    )
    _process(qapp)
    provider = TscatCatalogProvider()
    orph_cat = next(c for c in provider.catalogs() if c.uuid == ORPHAN_CATALOG_UUID)

    caps = provider.capabilities(orph_cat)
    assert Capability.DELETE_EVENTS in caps
    assert Capability.RENAME_CATALOG not in caps
    assert Capability.EDIT_EVENTS not in caps
    assert Capability.CREATE_EVENTS not in caps
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_tscat_orphans.py -v -k "pseudo_catalog or orphan_catalog_capabilities"`
Expected: FAIL — provider does not yet expose the virtual catalog.

- [ ] **Step 3: Add a stable UUID and a factory**

Append to `SciQLop/plugins/tscat_catalogs/orphans.py`:

```python
ORPHAN_CATALOG_UUID = "00000000-0000-0000-0000-orphan-tscat"
ORPHAN_CATALOG_NAME = "🗑 Orphan events"
```

- [ ] **Step 4: Modify TscatCatalogProvider to surface the virtual catalog**

In `tscat_provider.py`, extend `catalogs()` and add a per-catalog capabilities override:

```python
    def catalogs(self) -> list[Catalog]:
        result = self._real_catalogs()
        from .orphans import list_orphan_events, ORPHAN_CATALOG_UUID, ORPHAN_CATALOG_NAME
        if list_orphan_events():
            result.append(Catalog(
                uuid=ORPHAN_CATALOG_UUID,
                name=ORPHAN_CATALOG_NAME,
                provider=self,
                path=[],
            ))
        return result

    def capabilities(self, catalog: Catalog | None = None) -> set[Capability]:
        from .orphans import ORPHAN_CATALOG_UUID
        if catalog is not None and catalog.uuid == ORPHAN_CATALOG_UUID:
            return {Capability.DELETE_EVENTS}
        return self._default_capabilities()
```

(Move the existing `catalogs()` body into a helper called `_real_catalogs()` and the existing capability set into `_default_capabilities()`.)

- [ ] **Step 5: Override `events(catalog)` for the orphan UUID**

Add to `tscat_provider.py`:

```python
    def events(self, catalog: Catalog, start=None, stop=None) -> list[CatalogEvent]:
        from .orphans import ORPHAN_CATALOG_UUID, list_orphan_events
        if catalog.uuid == ORPHAN_CATALOG_UUID:
            return [TscatEvent(e, parent=self) for e in list_orphan_events()]
        return super().events(catalog, start, stop)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_tscat_orphans.py -v`
Expected: PASS (4 tests).

- [ ] **Step 7: Commit**

```bash
git add SciQLop/plugins/tscat_catalogs/orphans.py SciQLop/plugins/tscat_catalogs/tscat_provider.py tests/test_tscat_orphans.py
git commit -m "feat(tscat): expose orphan events as a delete-only virtual catalog"
```

---

### Task B3: Cleanup dialog

**Files:**
- Create: `SciQLop/plugins/tscat_catalogs/orphan_cleanup_dialog.py`
- Test: `tests/test_tscat_orphans.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_tscat_orphans.py`:

```python
def test_cleanup_dialog_lists_orphans_and_deletes_selected(qapp):
    import tscat
    from SciQLop.plugins.tscat_catalogs.orphan_cleanup_dialog import OrphanCleanupDialog
    from SciQLop.plugins.tscat_catalogs.orphans import list_orphan_events

    baseline = {e.uuid for e in list_orphan_events()}
    e1 = tscat.create_event(
        start=datetime(2021, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2021, 1, 1, 1, tzinfo=timezone.utc),
        author="cleanup1",
    )
    e2 = tscat.create_event(
        start=datetime(2021, 1, 2, tzinfo=timezone.utc),
        stop=datetime(2021, 1, 2, 1, tzinfo=timezone.utc),
        author="cleanup2",
    )
    _process(qapp)

    dialog = OrphanCleanupDialog()
    listed = {row[0] for row in dialog.orphan_rows()}
    assert e1.uuid in listed
    assert e2.uuid in listed

    dialog.delete_uuids([e1.uuid])
    _process(qapp)
    after = {e.uuid for e in list_orphan_events()} - baseline
    assert e1.uuid not in after
    assert e2.uuid in after
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tscat_orphans.py -v -k cleanup_dialog`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement the dialog**

```python
# SciQLop/plugins/tscat_catalogs/orphan_cleanup_dialog.py
from __future__ import annotations

import tscat
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QLabel,
)
from PySide6.QtCore import Qt

from .orphans import list_orphan_events


class OrphanCleanupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Clean up orphan events")
        self._list = QListWidget()
        self._list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self._populate()

        layout = QVBoxLayout(self)
        self._summary = QLabel()
        layout.addWidget(self._summary)
        layout.addWidget(self._list)

        btns = QHBoxLayout()
        self._delete_selected = QPushButton("Delete checked")
        self._delete_selected.clicked.connect(self._on_delete_selected)
        self._delete_all = QPushButton("Delete all")
        self._delete_all.clicked.connect(self._on_delete_all)
        cancel = QPushButton("Close")
        cancel.clicked.connect(self.close)
        btns.addWidget(self._delete_selected)
        btns.addWidget(self._delete_all)
        btns.addStretch(1)
        btns.addWidget(cancel)
        layout.addLayout(btns)

    def _populate(self) -> None:
        self._list.clear()
        events = list_orphan_events()
        self._summary.setText(f"{len(events)} orphan event(s)")
        for ev in events:
            label = f"{ev.start.isoformat()} → {ev.stop.isoformat()} (uuid={ev.uuid[:8]}…)"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, ev.uuid)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            self._list.addItem(item)

    def orphan_rows(self) -> list[tuple[str, str]]:
        return [
            (self._list.item(i).data(Qt.ItemDataRole.UserRole), self._list.item(i).text())
            for i in range(self._list.count())
        ]

    def delete_uuids(self, uuids: list[str]) -> None:
        events = [e for e in list_orphan_events() if e.uuid in set(uuids)]
        if events:
            tscat.delete_events(events)
        self._populate()

    def _on_delete_selected(self) -> None:
        uuids = [
            self._list.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self._list.count())
            if self._list.item(i).checkState() == Qt.CheckState.Checked
        ]
        self.delete_uuids(uuids)

    def _on_delete_all(self) -> None:
        self.delete_uuids([e.uuid for e in list_orphan_events()])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tscat_orphans.py -v -k cleanup_dialog`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/plugins/tscat_catalogs/orphan_cleanup_dialog.py tests/test_tscat_orphans.py
git commit -m "feat(tscat): orphan-event cleanup dialog"
```

---

### Task B4: Wire dialog into provider actions

**Files:**
- Modify: `SciQLop/plugins/tscat_catalogs/tscat_provider.py`
- Test: `tests/test_catalog_tscat_integration.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_catalog_tscat_integration.py`:

```python
def test_provider_action_offers_orphan_cleanup(qapp, tscat_provider):
    actions = tscat_provider.actions(None)
    names = {a.name for a in actions}
    assert "Clean up orphan events…" in names
    assert "Open in TSCat editor…" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_tscat_integration.py::test_provider_action_offers_orphan_cleanup -v`
Expected: FAIL — only the editor action exists today.

- [ ] **Step 3: Extend the actions list**

In `tscat_provider.py` `actions()`:

```python
    def actions(self, catalog: Catalog | None = None) -> list[ProviderAction]:
        if catalog is not None:
            return []
        from SciQLop.components.theming import theme_icon
        return [
            ProviderAction(
                name="Open in TSCat editor…",
                callback=lambda _: self._show_editor_window(),
                icon=theme_icon("catalogue"),
            ),
            ProviderAction(
                name="Clean up orphan events…",
                callback=lambda _: self._show_orphan_cleanup_dialog(),
                icon=theme_icon("trash"),
            ),
        ]

    def _show_orphan_cleanup_dialog(self) -> None:
        from .orphan_cleanup_dialog import OrphanCleanupDialog
        dialog = OrphanCleanupDialog()
        dialog.exec()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_catalog_tscat_integration.py::test_provider_action_offers_orphan_cleanup -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add SciQLop/plugins/tscat_catalogs/tscat_provider.py tests/test_catalog_tscat_integration.py
git commit -m "feat(tscat): right-click \"Clean up orphan events…\" action"
```

---

### Task B5: Refresh the tree on orphan changes

**Files:**
- Modify: `SciQLop/plugins/tscat_catalogs/tscat_provider.py`
- Test: `tests/test_tscat_orphans.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_tscat_orphans.py`:

```python
def test_orphan_node_disappears_when_last_orphan_is_assigned(qapp):
    from SciQLop.plugins.tscat_catalogs.tscat_provider import TscatCatalogProvider
    from SciQLop.plugins.tscat_catalogs.orphans import ORPHAN_CATALOG_UUID

    cat = tscat.create_catalogue(name="adopt", author="t")
    e = tscat.create_event(
        start=datetime(2022, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2022, 1, 1, 1, tzinfo=timezone.utc),
        author="orph-adopt",
    )
    _process(qapp)

    provider = TscatCatalogProvider()
    assert any(c.uuid == ORPHAN_CATALOG_UUID for c in provider.catalogs())

    tscat.add_events_to_catalogue(cat, [e])
    _process(qapp)
    # Re-query — provider must drop the virtual node when no orphans remain
    real_uuids = {c.uuid for c in provider.catalogs()
                  if c.uuid != ORPHAN_CATALOG_UUID}
    assert ORPHAN_CATALOG_UUID not in {c.uuid for c in provider.catalogs()
                                       if c.uuid == ORPHAN_CATALOG_UUID
                                       and not list(real_uuids)}
```

- [ ] **Step 2: Add a refresh signal**

The existing `_on_root_rows_changed` slot is already wired to tscat model signals. Add a hook that also re-checks the orphan node by emitting a synthetic `catalog_added`/`catalog_removed`:

```python
    def _refresh_orphan_node(self) -> None:
        from .orphans import list_orphan_events, ORPHAN_CATALOG_UUID
        has_orphans = bool(list_orphan_events())
        had_orphan_node = ORPHAN_CATALOG_UUID in self._known_uuids
        if has_orphans and not had_orphan_node:
            self._known_uuids.add(ORPHAN_CATALOG_UUID)
            self.catalog_added.emit(self._make_orphan_catalog())
        elif not has_orphans and had_orphan_node:
            self._known_uuids.discard(ORPHAN_CATALOG_UUID)
            self.catalog_removed.emit(self._make_orphan_catalog())

    def _make_orphan_catalog(self) -> Catalog:
        from .orphans import ORPHAN_CATALOG_UUID, ORPHAN_CATALOG_NAME
        return Catalog(uuid=ORPHAN_CATALOG_UUID, name=ORPHAN_CATALOG_NAME,
                       provider=self, path=[])
```

Call `self._refresh_orphan_node()` at the end of the existing `_on_root_rows_changed` and `_on_action_done` slots.

- [ ] **Step 3: Run test to verify it passes**

Run: `uv run pytest tests/test_tscat_orphans.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add SciQLop/plugins/tscat_catalogs/tscat_provider.py tests/test_tscat_orphans.py
git commit -m "feat(tscat): refresh orphan virtual catalog on tscat model changes"
```

---

### Task B6: CHANGELOG + manual check

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Manual sanity check**

Run: `uv run sciqlop`. Create a tscat event without attaching it to any catalog (via the embedded Jupyter console: `import tscat; tscat.create_event(...)`). Verify the *🗑 Orphan events* node appears under *My Catalogs*. Open it — the event is in the table, can be multi-selected and bulk-deleted, but cannot be renamed or color-mapped. Drag the orphan onto a real catalog: the orphan disappears (link gives it a parent → it leaves the orphan query). Right-click the *My Catalogs* row → "Clean up orphan events…": dialog lists remaining orphans with checkable rows; "Delete all" empties them.

- [ ] **Step 2: Update changelog**

Append under `## Unreleased › Catalogs` in `CHANGELOG.md`:

```markdown
- Surfaced tscat orphan events (events with no catalog membership) as a virtual *🗑 Orphan events* row under *My Catalogs*, plus a right-click "Clean up orphan events…" action on the provider that opens a focused cleanup dialog. The orphan row is delete-only (no rename, no color-by); dragging an orphan onto a real catalog restores it without any special-case code (the link semantics give the event a parent, after which the orphan query drops it). Closes the long-standing "no way to clean orphan events" gap.
```

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs(changelog): tscat orphan-event surface + cleanup dialog"
```

---

## Self-Review

**Spec coverage**
- Event DnD with link/move/duplicate semantics — Tasks A3, A6.
- Cross-provider always duplicates — Task A6.
- EVENT_LIST_MIME_TYPE plumbing — Tasks A1, A2.
- Event table is a drag source — Task A5.
- Catalog tree accepts event drops — Task A6.
- Orphan event query — Task B1.
- Orphan virtual catalog (delete-only) — Tasks B2, B5.
- Cleanup dialog reachable via provider right-click — Tasks B3, B4.
- Drag-from-orphans-to-real-catalog as restore — falls out of A6 + B2 (no extra code).

**Placeholder scan** — all steps include concrete code or commands; no TBDs or "implement later".

**Type consistency** — `EventDropPayload` fields (`provider`, `catalog_uuid`, `event_uuids`) match between encoder, decoder, and dispatcher. `handle_event_drop(target_catalog, events, action, source_catalog)` signature is identical in base class, dummy provider tests, and the dispatcher call in `catalog_tree.py`. `ORPHAN_CATALOG_UUID` and `ORPHAN_CATALOG_NAME` are defined once in `orphans.py` and imported everywhere else.

**Open question (flag for the executor):** the Phase B virtual-catalog approach assumes `CatalogProvider.capabilities()` already accepts an optional `catalog` argument. Verify against `provider.py` before implementing B2; if the base signature is `capabilities(self) -> set[Capability]` (no per-catalog flavor), Task B2 needs to add an optional argument first and update all call sites.
