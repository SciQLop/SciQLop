# Catalog User API — Design Spec

## Goal

Provide a stable, notebook-friendly facade for CRUD operations on SciQLop catalogs. Users pull catalogs as speasy `Catalog` objects, manipulate them, and push them back — all from Jupyter within a running SciQLop session.

## Module Structure

```
SciQLop/user_api/catalogs/
├── __init__.py      # exports `catalogs` singleton + CatalogInput type alias
└── _service.py      # CatalogService class
```

## Path Convention

Catalogs are identified by path strings: `"{provider}//{path segments}//{catalog name}"`.

- Separator auto-detection: if the path contains `//`, split on `//`; otherwise split on `/`.
- Single `/` is a convenience for the simple `"provider/catalog_name"` case (two segments only). Paths with 3+ segments or catalog names containing `/` require `//`.
- First segment: provider name (matched against `CatalogRegistry.providers()` by `provider.name`).
- Last segment: catalog name.
- Middle segments: `catalog.path` (e.g. cocat room ID).
- Drag-and-drop from the catalog tree always generates `//`-separated paths (consistent with product paths).
- `list()` returns `//`-separated paths for consistency with drag-and-drop.

Examples:
- `"cocat//room1//My Catalog"` → provider `"cocat"`, path `["room1"]`, catalog `"My Catalog"`
- `"tscat/My Local Catalog"` → provider `"tscat"`, path `[]`, catalog `"My Local Catalog"`
- `"cocat//room1//Cat/with slash"` → catalog named `"Cat/with slash"`

### Path Resolution

The facade resolves a path to an internal `(provider, Catalog)` pair by:
1. Splitting the path into segments (auto-detect separator)
2. First segment → match `provider.name` against registered providers
3. Last segment → catalog name, middle segments → path
4. Search `provider.catalogs()` for a catalog matching `(name, path)`

Uniqueness of the `(provider, path, name)` triple is assumed. If duplicates exist, first match wins.

## Exchange Format

speasy `Catalog` and `Event` objects are the exchange format between the user API and notebooks.

UUID round-tripping: `get()` stashes the internal `CatalogEvent.uuid` in `event.meta["__sciqlop_uuid__"]`. `save()` reuses this UUID when present, generates a new one otherwise.

## Input Duck-Typing

`create()` and `save()` accept flexible inputs:

```python
DateTimeLike = Any  # whatever speasy.Event accepts: str, datetime, numpy.datetime64, etc.

CatalogInput = Union[
    speasy.Catalog,
    Iterable[tuple[DateTimeLike, DateTimeLike]],
    Iterable[tuple[DateTimeLike, DateTimeLike, dict]],
]
```

Normalization: if not a `speasy.Catalog`, iterate and check tuple length (2 → `(start, stop)`, 3 → `(start, stop, meta)`), build a `speasy.Catalog` from `speasy.Event` objects.

Catalog-level metadata (name, author, etc.) is derived from the path and provider context, not from the input data. Only event-level metadata is supported through the duck-typed inputs.

## API Surface

```python
from SciQLop.user_api.catalogs import catalogs

# List catalog paths
catalogs.list()                                → list[str]
catalogs.list("cocat//room1")                  → list[str] under prefix

# Get as speasy Catalog
cat = catalogs.get("cocat//room1//My Catalog") → speasy.Catalog

# Save back (upsert: creates if missing, UUID-preserving replace)
catalogs.save("cocat//room1//My Catalog", cat)

# Create new (strict: ValueError if already exists)
catalogs.create("cocat//room1//New Cat", cat)
catalogs.create("cocat//room1//New Cat", [
    ("2018-01-01", "2018-01-02"),
    ("2019-06-15", "2019-06-16", {"tag": "shock"}),
])

# Delete
catalogs.remove("cocat//room1//Old Cat")
```

### Save vs Create Semantics

- `save(path, data)`: upsert — if the catalog exists, replace its events (UUID-preserving reconciliation); if it doesn't exist, create it. If the provider lacks `CREATE_CATALOGS` capability and the catalog doesn't exist, raises `PermissionError`.
- `create(path, data)`: strict create — raises `ValueError` if a catalog already exists at that path.

### Save Reconciliation (UUID-preserving replace)

When `save()` is called on an existing catalog:
1. Normalize input to `speasy.Catalog`
2. Build the new event list as internal `CatalogEvent` objects (reusing UUIDs from `__sciqlop_uuid__` where present)
3. Bulk-replace via `provider._set_events(catalog, new_events)` — single signal, efficient
4. Call `provider.save_catalog(catalog)` to persist

This is logically a full replace but preserves UUIDs for events that round-tripped through `get()`.

### `list()` Prefix Filtering

The prefix is resolved the same way as a full path (split into provider + path segments). Catalogs are returned whose provider matches and whose `catalog.path` starts with the resolved segments.

- `catalogs.list()` → all catalogs across all providers
- `catalogs.list("cocat")` → all cocat catalogs across all rooms
- `catalogs.list("cocat//room1")` → only catalogs in room1

## Error Handling

Standard Python exceptions, no custom hierarchy:
- `KeyError`: path not found (for `get`, `remove`; for `save` only when provider doesn't exist)
- `PermissionError`: provider lacks the required capability (e.g. `save` creating on a read-only provider)
- `ValueError`: catalog already exists (for `create`)

## Architecture

Thin facade (Approach A): `CatalogService` directly uses `CatalogRegistry` to find providers, resolves paths, and handles all speasy ↔ internal `CatalogEvent` conversion.

### Required Provider API Changes

**`create_catalog` signature**: changes from `create_catalog(name: str) -> Catalog | None` to `create_catalog(name: str, path: list[str] = []) -> Catalog`. Two changes:
1. Added `path` parameter — allows the facade to route catalog creation to the correct path (e.g. cocat room). Backward-compatible default.
2. Return type tightened to `Catalog` (dropped `| None`) — providers declaring `CREATE_CATALOGS` capability must return a `Catalog`. The `| None` was a workaround for providers that didn't support creation; that is now handled by capability checks.

Affected implementations:
- `CatalogProvider.create_catalog` (base) — add `path` parameter, keep default `return None` for providers without the capability (facade never calls it without checking capability first)
- `CocatCatalogProvider.create_catalog` — use `path[0]` as room ID instead of guessing
- `TscatCatalogProvider.create_catalog` — fix to return `Catalog` synchronously instead of `None`, ignore `path` (flat structure)
- `DummyCatalogProvider.create_catalog` — store `path` on the created `Catalog`

### Conversion

**Internal → speasy** (`get`):
- `CatalogEvent` → `speasy.Event(start, stop, meta={**event.meta, "__sciqlop_uuid__": event.uuid})`

**speasy → internal** (`save`/`create`):
- `speasy.Event` → `CatalogEvent(uuid=meta.get("__sciqlop_uuid__", new_uuid()), start, stop, meta)`
- The `__sciqlop_uuid__` key is stripped from the meta dict passed to `CatalogEvent` to avoid leaking internal state.

## Scope Boundaries

Not in this version:
- DataFrame input/output (future extension)
- Thread marshalling (currently same thread; the embedded Jupyter kernel runs in-process on the Qt main thread)
- Query/filter operations beyond `list()` prefix filtering
- `remove()` does not check dirty state — it deletes silently, matching provider behavior

Reserved metadata keys: keys starting with `__sciqlop_` are reserved for internal use.

## Integration Points

- `CatalogRegistry.instance()` for provider discovery
- `CatalogProvider` methods: `catalogs()`, `events()`, `create_catalog(name, path)`, `_set_events()`, `remove_catalog()`, `save_catalog()`
- `CatalogProvider.capabilities()` for permission checks before operations
- Catalog tree drag-and-drop: generate `//`-separated path as text MIME type
