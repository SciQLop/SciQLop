# Catalog Deferred Save & Dirty State Design

## Problem

Catalog modifications (event edits, additions, deletions) are not persisted until the provider's save function is explicitly called (e.g. tscat requires `save()` to flush to database). SciQLop currently has no mechanism to:
- Track which catalogs have unsaved modifications
- Let the user trigger a save explicitly
- Visually indicate unsaved state

## Design

### Provider API Changes

**New capabilities** added to `Capability` enum:
- `SAVE` — provider supports bulk save (all modified catalogs at once)
- `SAVE_CATALOG` — provider supports per-catalog save (future use)

**New state in `CatalogProvider` base class:**
- `_dirty_catalogs: set[str]` — set of dirty catalog UUIDs
- `dirty_changed = Signal(Catalog, bool)` — emitted when a catalog's dirty state changes (catalog, is_dirty)

**New methods in `CatalogProvider`:**
- `mark_dirty(catalog)` — adds catalog UUID to dirty set, emits `dirty_changed(catalog, True)`
- `is_dirty(catalog=None)` — if catalog is None, returns whether any catalog is dirty; otherwise checks specific catalog
- `save()` — calls `_do_save()`, clears dirty set, emits `dirty_changed(catalog, False)` for each cleared catalog
- `save_catalog(catalog)` — calls `_do_save_catalog(catalog)`, clears that catalog from dirty set. Only valid if provider has `SAVE_CATALOG` capability.
- `_do_save()` — protected, subclass implements actual persistence. No-op by default.
- `_do_save_catalog(catalog)` — protected, optional override for per-catalog save. No-op by default.

**Automatic dirty marking:**
- `add_event()` and `remove_event()` auto-mark the catalog dirty via `mark_dirty()`
- `CatalogProvider` connects to `CatalogEvent.range_changed` when events are added (in `_add_event()`), and calls `mark_dirty()` on the parent catalog when triggered
- Dirty state is set immediately on any modification (no debounce)

### TscatCatalogProvider Changes

- Declares `SAVE` capability
- `_do_save()` calls tscat's `save()` function to flush the in-memory model to the database
- No changes to `TscatEvent` — the existing debounce + `SetAttributeAction` flow is fine since it only modifies tscat's in-memory model
- Dirty marking happens automatically from the base class

### UI: Catalog Tree Dirty Indicators

**Display text:**
- When a catalog is dirty, its display name gets an asterisk suffix (e.g. "MyCatalog *")
- Provider node shows as dirty if any of its catalogs are dirty (e.g. "TSCat *")
- Indicator clears when all catalogs under a provider are saved

**Save button in tree:**
- A small save icon rendered next to dirty provider nodes via `QStyledItemDelegate`
- Clicking it calls `provider.save()`
- Only visible when the provider is dirty and has `SAVE` capability

**Context menu:**
- Right-clicking a dirty provider node shows a "Save" action that calls `provider.save()`
- Right-clicking a dirty catalog node shows "Save" too — calls `provider.save()` for provider-level save, or `provider.save_catalog(catalog)` if `SAVE_CATALOG` is supported
- Save actions only appear when the target is dirty

## Files to Modify

1. `SciQLop/components/catalogs/backend/provider.py` — add capabilities, dirty state, save methods
2. `SciQLop/plugins/tscat_catalogs/tscat_provider.py` — add SAVE capability, implement `_do_save()`
3. `SciQLop/components/catalogs/ui/catalog_browser.py` — add context menu save actions, connect to dirty_changed
4. `SciQLop/components/catalogs/ui/event_table.py` — no changes expected
5. `SciQLop/components/catalogs/backend/registry.py` — no changes expected (providers auto-register)

## Out of Scope

- Unsaved-changes warning on application exit
- Undo/redo integration
- Per-catalog save for tscat (tscat doesn't support it)
