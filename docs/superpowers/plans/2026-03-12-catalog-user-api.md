# Catalog User API Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a stable, notebook-friendly `catalogs` facade to `SciQLop/user_api/` for CRUD operations on catalogs using speasy `Catalog`/`Event` as the exchange format.

**Architecture:** Thin `CatalogService` class wraps `CatalogRegistry` to resolve paths → `(provider, Catalog)`, converts between speasy and internal `CatalogEvent`, and delegates persistence to providers. Requires a small backward-compatible change to `CatalogProvider.create_catalog` (add `path` param, tighten return type).

**Tech Stack:** Python, PySide6 (QObject/signals), speasy (`Catalog`, `Event`), pytest/pytest-qt

**Spec:** `docs/superpowers/specs/2026-03-12-catalog-user-api-design.md`

---

## File Structure

| Action | Path | Responsibility |
|--------|------|---------------|
| Modify | `SciQLop/components/catalogs/backend/provider.py:192` | Add `path` param to `create_catalog`, tighten return type |
| Modify | `SciQLop/components/catalogs/backend/dummy_provider.py:55` | Update `create_catalog` to accept and store `path` |
| Modify | `SciQLop/plugins/collaborative_catalogs/cocat_provider.py:176` | Use `path[0]` as room ID in `create_catalog` |
| Modify | `SciQLop/plugins/tscat_catalogs/tscat_provider.py:145` | Fix `create_catalog` to return `Catalog` synchronously |
| Create | `SciQLop/user_api/catalogs/__init__.py` | Export `catalogs` singleton, `CatalogInput` type alias |
| Create | `SciQLop/user_api/catalogs/_service.py` | `CatalogService` class: path parsing, conversion, CRUD |
| Create | `tests/test_catalog_user_api.py` | Tests for the full user API |

---

## Chunk 1: Provider API Change

### Task 1: Update `CatalogProvider.create_catalog` signature

**Files:**
- Modify: `SciQLop/components/catalogs/backend/provider.py:192-194`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_catalog_provider.py`:

```python
def test_create_catalog_with_path(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    provider = DummyProvider(num_catalogs=0, events_per_catalog=0)
    cat = provider.create_catalog("PathCat", path=["room1"])
    assert cat is not None
    assert cat.name == "PathCat"
    assert cat.path == ["room1"]
    assert cat.provider is provider
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_provider.py::test_create_catalog_with_path -v`
Expected: FAIL — `create_catalog()` does not accept `path` keyword

- [ ] **Step 3: Update base class signature**

In `SciQLop/components/catalogs/backend/provider.py`, change line 192:

```python
# Before:
def create_catalog(self, name: str) -> Catalog | None:
    """Public API: create a new catalog. Override for backend persistence."""
    return None

# After:
def create_catalog(self, name: str, path: list[str] | None = None) -> Catalog:
    """Public API: create a new catalog. Override for backend persistence."""
    raise NotImplementedError
```

- [ ] **Step 4: Update DummyProvider**

In `SciQLop/components/catalogs/backend/dummy_provider.py`, change line 55:

```python
# Before:
def create_catalog(self, name: str) -> Catalog | None:
    cat = Catalog(
        uuid=str(_uuid.uuid4()),
        name=name,
        provider=self,
        path=[],
    )

# After:
def create_catalog(self, name: str, path: list[str] | None = None) -> Catalog:
    cat = Catalog(
        uuid=str(_uuid.uuid4()),
        name=name,
        provider=self,
        path=path or [],
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_catalog_provider.py::test_create_catalog_with_path -v`
Expected: PASS

- [ ] **Step 6: Run full provider test suite**

Run: `uv run pytest tests/test_catalog_provider.py -v`
Expected: All existing tests still pass

- [ ] **Step 7: Commit**

```bash
git add SciQLop/components/catalogs/backend/provider.py \
        SciQLop/components/catalogs/backend/dummy_provider.py \
        tests/test_catalog_provider.py
git commit -m "feat(catalogs): add path parameter to CatalogProvider.create_catalog"
```

### Task 2: Update CocatCatalogProvider.create_catalog

**Files:**
- Modify: `SciQLop/plugins/collaborative_catalogs/cocat_provider.py:176-195`

- [ ] **Step 1: Update `create_catalog` to use `path` parameter**

```python
# Before (lines 176-195):
def create_catalog(self, name: str) -> Catalog | None:
    # Create in whichever room... we need to know which room.
    # For now, create in default room if joined, else first joined room.
    room_id = self._default_room_id
    if room_id not in self._rooms:
        room_id = next(iter(self._rooms), None)
    if room_id is None:
        return None
    ...

# After:
def create_catalog(self, name: str, path: list[str] | None = None) -> Catalog:
    room_id = path[0] if path else self._default_room_id
    if room_id not in self._rooms:
        if path:
            raise KeyError(f"Room '{room_id}' is not joined")
        room_id = next(iter(self._rooms), None)
    if room_id is None:
        raise RuntimeError("No rooms joined")
    room = self._rooms[room_id]
    cocat_cat = room.db.create_catalogue(name=name, author="SciQLop")
    cat = Catalog(
        uuid=str(cocat_cat.uuid),
        name=name,
        provider=self,
        path=[room_id],
    )
    self._catalog_map[cat.uuid] = cat
    self._set_events(cat, [])
    self.catalog_added.emit(cat)
    return cat
```

- [ ] **Step 2: Commit**

```bash
git add SciQLop/plugins/collaborative_catalogs/cocat_provider.py
git commit -m "feat(cocat): route create_catalog to specified room via path param"
```

### Task 3: Fix TscatCatalogProvider.create_catalog to return synchronously

**Files:**
- Modify: `SciQLop/plugins/tscat_catalogs/tscat_provider.py:145-153`

- [ ] **Step 1: Update `create_catalog` to return `Catalog` synchronously**

```python
# Before (lines 145-153):
def create_catalog(self, name: str) -> Catalog | None:
    import uuid as _uuid
    catalog_uuid = str(_uuid.uuid4())
    tscat_model.do(CreateEntityAction(
        user_callback=None,
        cls=tscat._Catalogue,
        args=dict(name=name, author="SciQLop", uuid=catalog_uuid),
    ))
    return None

# After:
def create_catalog(self, name: str, path: list[str] | None = None) -> Catalog:
    import uuid as _uuid
    catalog_uuid = str(_uuid.uuid4())
    tscat_model.do(CreateEntityAction(
        user_callback=None,
        cls=tscat._Catalogue,
        args=dict(name=name, author="SciQLop", uuid=catalog_uuid),
    ))
    cat = Catalog(
        uuid=catalog_uuid,
        name=name,
        provider=self,
        path=path or [],
    )
    if self._catalog_cache is not None:
        self._catalog_cache.append(cat)
    self._known_uuids.add(catalog_uuid)
    self._set_events(cat, [])
    return cat
```

Note: We build the `Catalog` object immediately rather than waiting for `_on_root_rows_changed`. The async tscat model will still create the entity in the background; we just return a usable handle now. The `_on_root_rows_changed` handler will reconcile when it fires.

- [ ] **Step 2: Commit**

```bash
git add SciQLop/plugins/tscat_catalogs/tscat_provider.py
git commit -m "fix(tscat): return Catalog synchronously from create_catalog"
```

---

## Chunk 2: CatalogService — Path Parsing and Conversion

### Task 4: Path parsing and catalog resolution

**Files:**
- Create: `SciQLop/user_api/catalogs/_service.py`
- Create: `tests/test_catalog_user_api.py`

- [ ] **Step 1: Write failing tests for path parsing**

Create `tests/test_catalog_user_api.py`:

```python
from .fixtures import *
import pytest


def test_parse_path_single_slash():
    from SciQLop.user_api.catalogs._service import _parse_path
    provider, path, name = _parse_path("tscat/My Catalog")
    assert provider == "tscat"
    assert path == []
    assert name == "My Catalog"


def test_parse_path_double_slash():
    from SciQLop.user_api.catalogs._service import _parse_path
    provider, path, name = _parse_path("cocat//room1//My Catalog")
    assert provider == "cocat"
    assert path == ["room1"]
    assert name == "My Catalog"


def test_parse_path_double_slash_nested():
    from SciQLop.user_api.catalogs._service import _parse_path
    provider, path, name = _parse_path("cocat//room1//sub//My Catalog")
    assert provider == "cocat"
    assert path == ["room1", "sub"]
    assert name == "My Catalog"


def test_parse_path_name_with_slash():
    from SciQLop.user_api.catalogs._service import _parse_path
    provider, path, name = _parse_path("cocat//room1//Cat/with slash")
    assert provider == "cocat"
    assert path == ["room1"]
    assert name == "Cat/with slash"


def test_parse_path_too_short():
    from SciQLop.user_api.catalogs._service import _parse_path
    with pytest.raises(ValueError):
        _parse_path("just-provider")


def test_parse_prefix_provider_only():
    from SciQLop.user_api.catalogs._service import _parse_prefix
    provider, path = _parse_prefix("cocat")
    assert provider == "cocat"
    assert path == []


def test_parse_prefix_with_path():
    from SciQLop.user_api.catalogs._service import _parse_prefix
    provider, path = _parse_prefix("cocat//room1")
    assert provider == "cocat"
    assert path == ["room1"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_catalog_user_api.py -v -k parse`
Expected: FAIL — module does not exist

- [ ] **Step 3: Implement path parsing**

Create `SciQLop/user_api/catalogs/_service.py`:

```python
from __future__ import annotations

import uuid as _uuid
from typing import Any

from speasy.products.catalog import Catalog as SpeasyCatalog, Event as SpeasyEvent

from SciQLop.components.catalogs.backend.provider import (
    Catalog,
    CatalogEvent,
    CatalogProvider,
    Capability,
)
from SciQLop.components.catalogs.backend.registry import CatalogRegistry

_UUID_KEY = "__sciqlop_uuid__"


def _split_segments(path: str) -> list[str]:
    if "//" in path:
        return path.split("//")
    return path.split("/")


def _parse_path(path: str) -> tuple[str, list[str], str]:
    segments = _split_segments(path)
    if len(segments) < 2:
        raise ValueError(f"Path must have at least provider and catalog name: {path!r}")
    return segments[0], segments[1:-1], segments[-1]


def _parse_prefix(prefix: str) -> tuple[str, list[str]]:
    segments = _split_segments(prefix)
    return segments[0], segments[1:]


def _build_path_string(provider_name: str, path: list[str], catalog_name: str) -> str:
    parts = [provider_name] + path + [catalog_name]
    return "//".join(parts)
```

Also create `SciQLop/user_api/catalogs/__init__.py` (empty for now, will fill in Task 6):

```python
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_catalog_user_api.py -v -k parse`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/catalogs/__init__.py \
        SciQLop/user_api/catalogs/_service.py \
        tests/test_catalog_user_api.py
git commit -m "feat(user_api): add catalog path parsing utilities"
```

### Task 5: Speasy ↔ internal conversion functions

**Files:**
- Modify: `SciQLop/user_api/catalogs/_service.py`
- Modify: `tests/test_catalog_user_api.py`

- [ ] **Step 1: Write failing tests for conversion**

Append to `tests/test_catalog_user_api.py`:

```python
from datetime import datetime, timezone


def test_catalog_event_to_speasy(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    from SciQLop.user_api.catalogs._service import _event_to_speasy

    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    stop = datetime(2020, 1, 2, tzinfo=timezone.utc)
    event = CatalogEvent(uuid="evt-1", start=start, stop=stop,
                         meta={"author": "Alice"})
    speasy_event = _event_to_speasy(event)
    assert speasy_event.start_time == start
    assert speasy_event.stop_time == stop
    assert speasy_event.meta["author"] == "Alice"
    assert speasy_event.meta["__sciqlop_uuid__"] == "evt-1"


def test_speasy_event_to_internal(qtbot, qapp):
    from speasy.products.catalog import Event as SpeasyEvent
    from SciQLop.user_api.catalogs._service import _event_to_internal

    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    stop = datetime(2020, 1, 2, tzinfo=timezone.utc)
    ev = SpeasyEvent(start, stop, meta={"author": "Alice", "__sciqlop_uuid__": "evt-1"})
    internal = _event_to_internal(ev)
    assert internal.uuid == "evt-1"
    assert internal.start == start
    assert internal.stop == stop
    assert internal.meta == {"author": "Alice"}
    assert "__sciqlop_uuid__" not in internal.meta


def test_speasy_event_to_internal_no_uuid(qtbot, qapp):
    from speasy.products.catalog import Event as SpeasyEvent
    from SciQLop.user_api.catalogs._service import _event_to_internal

    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    stop = datetime(2020, 1, 2, tzinfo=timezone.utc)
    ev = SpeasyEvent(start, stop, meta={"author": "Alice"})
    internal = _event_to_internal(ev)
    assert internal.uuid  # auto-generated, non-empty
    assert internal.meta == {"author": "Alice"}


def test_normalize_input_speasy_catalog(qtbot, qapp):
    from speasy.products.catalog import Catalog as SpeasyCatalog, Event as SpeasyEvent
    from SciQLop.user_api.catalogs._service import _normalize_input

    cat = SpeasyCatalog(name="test", events=[
        SpeasyEvent("2020-01-01", "2020-01-02", meta={"tag": "a"}),
    ])
    result = _normalize_input(cat)
    assert isinstance(result, SpeasyCatalog)
    assert result is cat


def test_normalize_input_tuples(qtbot, qapp):
    from SciQLop.user_api.catalogs._service import _normalize_input
    from speasy.products.catalog import Catalog as SpeasyCatalog

    data = [("2020-01-01", "2020-01-02"), ("2020-06-01", "2020-06-02")]
    result = _normalize_input(data)
    assert isinstance(result, SpeasyCatalog)
    assert len(result) == 2


def test_normalize_input_triples(qtbot, qapp):
    from SciQLop.user_api.catalogs._service import _normalize_input
    from speasy.products.catalog import Catalog as SpeasyCatalog

    data = [("2020-01-01", "2020-01-02", {"tag": "a"})]
    result = _normalize_input(data)
    assert isinstance(result, SpeasyCatalog)
    assert len(result) == 1
    assert result[0].meta["tag"] == "a"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_catalog_user_api.py -v -k "speasy or normalize"`
Expected: FAIL — functions not defined

- [ ] **Step 3: Implement conversion functions**

Append to `SciQLop/user_api/catalogs/_service.py`:

```python
def _event_to_speasy(event: CatalogEvent) -> SpeasyEvent:
    meta = {**event.meta, _UUID_KEY: event.uuid}
    return SpeasyEvent(event.start, event.stop, meta=meta)


def _event_to_internal(event: SpeasyEvent) -> CatalogEvent:
    meta = dict(event.meta) if event.meta else {}
    uuid = meta.pop(_UUID_KEY, str(_uuid.uuid4()))
    return CatalogEvent(uuid=uuid, start=event.start_time, stop=event.stop_time, meta=meta)


def _normalize_input(data) -> SpeasyCatalog:
    if isinstance(data, SpeasyCatalog):
        return data
    events = []
    for item in data:
        if len(item) == 2:
            events.append(SpeasyEvent(item[0], item[1]))
        elif len(item) == 3:
            events.append(SpeasyEvent(item[0], item[1], meta=item[2]))
        else:
            raise ValueError(f"Expected (start, stop) or (start, stop, meta), got {len(item)} elements")
    return SpeasyCatalog(name="", events=events)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_catalog_user_api.py -v -k "speasy or normalize"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/catalogs/_service.py tests/test_catalog_user_api.py
git commit -m "feat(user_api): add speasy <-> internal catalog conversion functions"
```

---

## Chunk 3: CatalogService CRUD Operations

### Task 6: `list()` and `get()`

**Files:**
- Modify: `SciQLop/user_api/catalogs/_service.py`
- Modify: `tests/test_catalog_user_api.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_catalog_user_api.py`:

```python
@pytest.fixture
def dummy_provider(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    # Reset registry to avoid cross-test pollution
    registry = CatalogRegistry.instance()
    old_providers = list(registry._providers)
    provider = DummyProvider(
        num_catalogs=2, events_per_catalog=3,
        paths=[["room1"], ["room2"]],
    )
    yield provider
    # Cleanup: remove this provider
    registry._providers = old_providers


@pytest.fixture
def catalog_service(dummy_provider):
    from SciQLop.user_api.catalogs._service import CatalogService
    return CatalogService()


def test_list_all(catalog_service, dummy_provider):
    paths = catalog_service.list()
    assert len(paths) == 2
    assert all("//" in p for p in paths)
    assert any("Catalog-0" in p for p in paths)
    assert any("Catalog-1" in p for p in paths)


def test_list_with_prefix(catalog_service, dummy_provider):
    paths = catalog_service.list("DummyProvider//room1")
    assert len(paths) == 1
    assert "Catalog-0" in paths[0]


def test_list_provider_only(catalog_service, dummy_provider):
    paths = catalog_service.list("DummyProvider")
    assert len(paths) == 2


def test_get_catalog(catalog_service, dummy_provider):
    from speasy.products.catalog import Catalog as SpeasyCatalog
    cat = catalog_service.get("DummyProvider//room1//Catalog-0")
    assert isinstance(cat, SpeasyCatalog)
    assert len(cat) == 3
    assert cat[0].meta["__sciqlop_uuid__"]


def test_get_not_found(catalog_service, dummy_provider):
    with pytest.raises(KeyError):
        catalog_service.get("DummyProvider//room1//NoSuchCatalog")


def test_get_bad_provider(catalog_service, dummy_provider):
    with pytest.raises(KeyError):
        catalog_service.get("NoSuchProvider//Catalog-0")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_catalog_user_api.py -v -k "test_list or test_get"`
Expected: FAIL — `CatalogService` not defined

- [ ] **Step 3: Implement `CatalogService` with `list()` and `get()`**

Add to `SciQLop/user_api/catalogs/_service.py`:

```python
class CatalogService:

    def _registry(self) -> CatalogRegistry:
        return CatalogRegistry.instance()

    def _find_provider(self, provider_name: str) -> CatalogProvider:
        for p in self._registry().providers():
            if p.name == provider_name:
                return p
        raise KeyError(f"Provider not found: {provider_name!r}")

    def _resolve(self, path: str) -> tuple[CatalogProvider, Catalog]:
        provider_name, segments, name = _parse_path(path)
        provider = self._find_provider(provider_name)
        for cat in provider.catalogs():
            if cat.name == name and cat.path == segments:
                return provider, cat
        raise KeyError(f"Catalog not found: {path!r}")

    def list(self, prefix: str | None = None) -> list[str]:
        if prefix is None:
            return [
                _build_path_string(p.name, cat.path, cat.name)
                for p in self._registry().providers()
                for cat in p.catalogs()
            ]
        provider_name, path_prefix = _parse_prefix(prefix)
        provider = self._find_provider(provider_name)
        return [
            _build_path_string(provider.name, cat.path, cat.name)
            for cat in provider.catalogs()
            if cat.path[:len(path_prefix)] == path_prefix
        ]

    def get(self, path: str) -> SpeasyCatalog:
        provider, catalog = self._resolve(path)
        events = provider.events(catalog)
        speasy_events = [_event_to_speasy(e) for e in events]
        return SpeasyCatalog(name=catalog.name, events=speasy_events)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_catalog_user_api.py -v -k "test_list or test_get"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/catalogs/_service.py tests/test_catalog_user_api.py
git commit -m "feat(user_api): implement CatalogService.list() and get()"
```

### Task 7: `save()` and `create()`

**Files:**
- Modify: `SciQLop/user_api/catalogs/_service.py`
- Modify: `tests/test_catalog_user_api.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_catalog_user_api.py`:

```python
def test_save_existing_catalog(catalog_service, dummy_provider):
    cat = catalog_service.get("DummyProvider//room1//Catalog-0")
    assert len(cat) == 3

    # Modify: keep first event, drop rest, add new
    from speasy.products.catalog import Catalog as SpeasyCatalog, Event as SpeasyEvent
    modified = SpeasyCatalog(name="Catalog-0", events=[
        cat[0],  # kept — has __sciqlop_uuid__
        SpeasyEvent("2025-01-01", "2025-01-02", meta={"new": True}),
    ])
    catalog_service.save("DummyProvider//room1//Catalog-0", modified)

    reloaded = catalog_service.get("DummyProvider//room1//Catalog-0")
    assert len(reloaded) == 2
    # First event preserved UUID
    assert reloaded[0].meta["__sciqlop_uuid__"] == cat[0].meta["__sciqlop_uuid__"]


def test_save_creates_if_missing(catalog_service, dummy_provider):
    catalog_service.save("DummyProvider//room1//Brand New", [
        ("2020-01-01", "2020-01-02"),
    ])
    cat = catalog_service.get("DummyProvider//room1//Brand New")
    assert len(cat) == 1


def test_save_bad_provider(catalog_service, dummy_provider):
    with pytest.raises(KeyError):
        catalog_service.save("NoSuchProvider//room//Cat", [("2020-01-01", "2020-01-02")])


def test_create_new_catalog(catalog_service, dummy_provider):
    catalog_service.create("DummyProvider//room3//New Cat", [
        ("2020-01-01", "2020-01-02"),
        ("2020-06-01", "2020-06-02", {"tag": "storm"}),
    ])
    cat = catalog_service.get("DummyProvider//room3//New Cat")
    assert len(cat) == 2
    assert cat[1].meta["tag"] == "storm"


def test_create_already_exists(catalog_service, dummy_provider):
    with pytest.raises(ValueError):
        catalog_service.create("DummyProvider//room1//Catalog-0", [])


def test_create_with_speasy_catalog(catalog_service, dummy_provider):
    from speasy.products.catalog import Catalog as SpeasyCatalog, Event as SpeasyEvent
    speasy_cat = SpeasyCatalog(name="FromSpeasy", events=[
        SpeasyEvent("2021-03-01", "2021-03-02"),
    ])
    catalog_service.create("DummyProvider//FromSpeasy", speasy_cat)
    result = catalog_service.get("DummyProvider//FromSpeasy")
    assert len(result) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_catalog_user_api.py -v -k "test_save or test_create"`
Expected: FAIL — methods not defined

- [ ] **Step 3: Implement `save()` and `create()`**

Add to `CatalogService` class in `SciQLop/user_api/catalogs/_service.py`:

```python
    def save(self, path: str, data) -> None:
        speasy_cat = _normalize_input(data)
        new_events = [_event_to_internal(e) for e in speasy_cat]
        provider_name, segments, name = _parse_path(path)
        provider = self._find_provider(provider_name)

        existing = self._find_catalog(provider, segments, name)
        if existing is None:
            if Capability.CREATE_CATALOGS not in provider.capabilities():
                raise PermissionError(f"Provider {provider_name!r} cannot create catalogs")
            existing = provider.create_catalog(name, path=segments)

        provider._set_events(existing, new_events)
        provider.events_changed.emit(existing)
        provider.mark_dirty(existing)
        if Capability.SAVE_CATALOG in provider.capabilities():
            provider.save_catalog(existing)
        elif Capability.SAVE in provider.capabilities():
            provider.save()

    def create(self, path: str, data) -> None:
        provider_name, segments, name = _parse_path(path)
        provider = self._find_provider(provider_name)

        if self._find_catalog(provider, segments, name) is not None:
            raise ValueError(f"Catalog already exists: {path!r}")
        if Capability.CREATE_CATALOGS not in provider.capabilities():
            raise PermissionError(f"Provider {provider_name!r} cannot create catalogs")

        catalog = provider.create_catalog(name, path=segments)
        speasy_cat = _normalize_input(data)
        new_events = [_event_to_internal(e) for e in speasy_cat]
        if new_events:
            provider._set_events(catalog, new_events)
            provider.events_changed.emit(catalog)
            provider.mark_dirty(catalog)
            if Capability.SAVE_CATALOG in provider.capabilities():
                provider.save_catalog(catalog)
            elif Capability.SAVE in provider.capabilities():
                provider.save()

    def _find_catalog(self, provider: CatalogProvider, path: list[str], name: str) -> Catalog | None:
        for cat in provider.catalogs():
            if cat.name == name and cat.path == path:
                return cat
        return None
```

Also refactor `_resolve` to use `_find_catalog`:

```python
    def _resolve(self, path: str) -> tuple[CatalogProvider, Catalog]:
        provider_name, segments, name = _parse_path(path)
        provider = self._find_provider(provider_name)
        catalog = self._find_catalog(provider, segments, name)
        if catalog is None:
            raise KeyError(f"Catalog not found: {path!r}")
        return provider, catalog
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_catalog_user_api.py -v -k "test_save or test_create"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/catalogs/_service.py tests/test_catalog_user_api.py
git commit -m "feat(user_api): implement CatalogService.save() and create()"
```

### Task 8: `remove()`

**Files:**
- Modify: `SciQLop/user_api/catalogs/_service.py`
- Modify: `tests/test_catalog_user_api.py`

- [ ] **Step 1: Write failing test**

Append to `tests/test_catalog_user_api.py`:

```python
def test_remove_catalog(catalog_service, dummy_provider):
    catalog_service.remove("DummyProvider//room1//Catalog-0")
    with pytest.raises(KeyError):
        catalog_service.get("DummyProvider//room1//Catalog-0")
    assert len(catalog_service.list()) == 1


def test_remove_not_found(catalog_service, dummy_provider):
    with pytest.raises(KeyError):
        catalog_service.remove("DummyProvider//room1//NoSuchCatalog")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_catalog_user_api.py -v -k test_remove`
Expected: FAIL

- [ ] **Step 3: Implement `remove()`**

Add to `CatalogService` class:

```python
    def remove(self, path: str) -> None:
        provider, catalog = self._resolve(path)
        if Capability.DELETE_CATALOGS not in provider.capabilities():
            raise PermissionError(f"Provider {provider.name!r} cannot delete catalogs")
        provider.remove_catalog(catalog)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_catalog_user_api.py -v -k test_remove`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/catalogs/_service.py tests/test_catalog_user_api.py
git commit -m "feat(user_api): implement CatalogService.remove()"
```

---

## Chunk 4: Public API and Integration

### Task 9: Wire up `__init__.py` and singleton

**Files:**
- Modify: `SciQLop/user_api/catalogs/__init__.py`

- [ ] **Step 1: Write failing test for import**

Append to `tests/test_catalog_user_api.py`:

```python
def test_import_catalogs_singleton():
    from SciQLop.user_api.catalogs import catalogs
    assert hasattr(catalogs, 'list')
    assert hasattr(catalogs, 'get')
    assert hasattr(catalogs, 'save')
    assert hasattr(catalogs, 'create')
    assert hasattr(catalogs, 'remove')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_user_api.py::test_import_catalogs_singleton -v`
Expected: FAIL — `catalogs` not importable

- [ ] **Step 3: Implement `__init__.py`**

Write `SciQLop/user_api/catalogs/__init__.py`:

```python
from typing import Any, Iterable, Union

from speasy.products.catalog import Catalog as SpeasyCatalog

from SciQLop.user_api.catalogs._service import CatalogService

DateTimeLike = Any
CatalogInput = Union[
    SpeasyCatalog,
    Iterable[tuple[DateTimeLike, DateTimeLike]],
    Iterable[tuple[DateTimeLike, DateTimeLike, dict]],
]

catalogs = CatalogService()

__all__ = ["catalogs", "CatalogInput"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_catalog_user_api.py::test_import_catalogs_singleton -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/user_api/catalogs/__init__.py tests/test_catalog_user_api.py
git commit -m "feat(user_api): export catalogs singleton"
```

### Task 10: Run full test suite

- [ ] **Step 1: Run all catalog user API tests**

Run: `uv run pytest tests/test_catalog_user_api.py -v`
Expected: All tests PASS

- [ ] **Step 2: Run full project test suite**

Run: `uv run pytest -v`
Expected: No regressions. All existing tests still pass.

- [ ] **Step 3: Final commit if any cleanup needed**

If any test adjustments were needed, commit them:

```bash
git commit -m "test: fix test adjustments for catalog user API"
```
