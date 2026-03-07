# Catalog System — Next Steps Design

Date: 2026-03-04

## Scope

Six improvements to the new unified catalog system on the `cocat` branch:

1. Wire Add Event / Delete buttons in CatalogBrowser
2. Wire filter bar in CatalogBrowser
3. Fix `catalog_removed` emitting `None` bug
4. Replace busy-wait event loading in TscatCatalogProvider
5. Port collaborative catalogs plugin to new provider API
6. Lazy event loading in CatalogOverlay

---

## 1. Add Event / Delete Buttons

**Current state:** `CatalogBrowser._on_add_event` and `_on_delete` are stubs (`pass`). The buttons show/hide based on capabilities already.

**Design:**

`_on_add_event`:
- Guard: `_current_catalog` and `_current_provider` must be set, provider must have `CREATE_EVENTS` capability.
- Get the panel's current visible time range. If no panel is connected, use a default 1-hour window around `datetime.utcnow()`.
- Create a new `CatalogEvent` with `start`/`stop` from the center of the visible range (±30 min), empty meta, new UUID.
- Call `_current_provider._add_event(_current_catalog, event)`. The base class already emits `events_changed`.
- The `events_changed` signal triggers the overlay to refresh spans and the event table to reload.

`_on_delete`:
- Determine what's selected: if the event table has a selected row, delete that event. If the tree has a catalog selected and the provider has `DELETE_CATALOGS`, delete the catalog.
- For event deletion: get the `CatalogEvent` from the table model, call `_current_provider._remove_event(_current_catalog, event)`.
- For catalog deletion: a new `remove_catalog` public method on `CatalogProvider` base class (with default impl that removes from `_events` dict and emits `catalog_removed`). Subclass providers that need backend cleanup (tscat, cocat) override it.

**New methods on `CatalogProvider`:**
- `add_event(catalog, event)` — public wrapper around `_add_event` (currently protected). Providers override to add backend persistence.
- `remove_event(catalog, event)` — public wrapper around `_remove_event`. Providers override for backend.
- `remove_catalog(catalog)` — new. Removes from internal state, emits `catalog_removed`.

**TscatCatalogProvider** overrides:
- `add_event`: create a tscat entity via `CreateEventAction`, then call `super().add_event()`.
- `remove_event`: delete via tscat `RemoveEntitiesAction`, then call `super().remove_event()`.

**CatalogOverlay** must react to `events_changed` to add/remove spans dynamically. Currently it only loads events at construction. Add:
- Connect to `provider.events_changed` signal in `__init__`.
- On `events_changed(catalog)`: diff current `_event_by_span_id` keys against new event UUIDs. Add new spans, remove stale ones.

---

## 2. Filter Bar

**Current state:** `_filter_bar` QLineEdit exists with placeholder "Filter catalogs..." but `textChanged` is not connected.

**Design:**
- Add a `QSortFilterProxyModel` between `CatalogTreeModel` and `_catalog_tree` (the QTreeView).
- Override `filterAcceptsRow` to do case-insensitive substring match on the node's display name.
- When a catalog node matches, show it and all its ancestor folder/provider nodes.
- When a provider or folder node has any matching descendant, show it.
- Connect `_filter_bar.textChanged` → `proxy.setFilterFixedString`.
- The proxy auto-expands matching subtrees by calling `_catalog_tree.expandAll()` when filter is non-empty.

---

## 3. Fix `catalog_removed` Emitting None

**Current state:** `TscatCatalogProvider._on_root_rows_changed` emits `catalog_removed.emit(None)` for removed catalogs. The tree model's `_on_catalog_removed` then compares `child.catalog is catalog`, which will match folder nodes (where `catalog is None`).

**Fix:**
- Before clearing `_catalog_cache`, snapshot the old catalogs list.
- After rebuilding, compute `removed = old_catalogs - new_catalogs` (by UUID).
- Emit `catalog_removed.emit(cat)` for each actually-removed catalog.
- Also call `_remove_event` cleanup for removed catalogs.

---

## 4. Replace Busy-Wait Event Loading

**Current state:** `_load_events` has a `for _ in range(5000)` loop calling `processEvents()` + `QThread.sleep(1)` waiting for tscat's model to populate.

**Design:**
- Connect to the tscat catalog model's `rowsInserted` signal instead of polling.
- Use a `QTimer.singleShot(0, ...)` to defer event reading until the event loop processes the insertion.
- Flow:
  1. `_load_events(catalog)` gets the tscat model, checks `rowCount()`.
  2. If `rowCount() > 0`, read immediately.
  3. If `rowCount() == 0`, connect a one-shot lambda to `model.rowsInserted` that calls `_read_events_from_model(catalog, model)`, then disconnects.
  4. Add a timeout `QTimer(5000ms)` that disconnects and emits `error_occurred` if events never arrive.

---

## 5. Port Collaborative Catalogs Plugin

**Current state:** Uses old `CatalogueProviderBase` / `EventBase` / `Catalogue` from `components/plotting/backend/catalogue.py`. Creates its own `CatalogueProvider` and `Event` wrappers around cocat objects. The `Plugin` adds a toolbar button that connects to a WebSocket room, creates a single plot panel, and attaches a `Catalogue` overlay.

**Design:**
- Create `CocatCatalogProvider(CatalogProvider)` in `collaborative_catalogs/cocat_provider.py`.
- Wraps a cocat `Room` + `DB`.
- On connection, enumerate `db.catalogues` → create `Catalog` objects.
- Map cocat `Event` → `CatalogEvent` (same pattern as `TscatEvent`).
- Capabilities: `EDIT_EVENTS`, `CREATE_EVENTS`, `DELETE_EVENTS` (matching cocat's features).
- The provider auto-registers in `CatalogRegistry`, so it appears in `CatalogBrowser` and panel context menus automatically.
- `CatalogGUISpawner` simplified: just connects to the room and creates the provider. No longer creates its own `Catalogue` overlay or hardcoded plot panel.
- Room's `event_added`/`event_removed` signals → provider's `_add_event`/`_remove_event`.

---

## 6. Lazy Event Loading in CatalogOverlay

**Current state:** `CatalogOverlay.__init__` calls `catalog.provider.events(catalog)` with no time range and creates a span for every event.

**Design:**
- `CatalogOverlay` tracks the panel's visible time range.
- Connect to the panel's `time_axis().range_changed` signal (already exists on `SciQLopPlotAxis`).
- On range change, query `provider.events(catalog, start, stop)` with a margin (2x the visible range on each side).
- Diff against currently-displayed spans: add new ones, remove out-of-range ones.
- Use a debounce `QTimer(200ms, singleShot=True)` to avoid excessive recomputation during zoom/pan.
- Keep a `_visible_events: dict[str, CatalogEvent]` tracking what's currently on screen.
- The provider's `events()` method already supports `start`/`stop` filtering with bisect — zero changes needed there.

**Edge cases:**
- When a catalog is first added, load events for the current visible range immediately.
- When the user edits a span and moves it out of range, keep it visible (it's in `_event_by_span_id` and has unsaved changes).
- Fallback: if the provider reports < 5000 total events, just load them all (the bisect query is cheap). Only apply lazy loading above that threshold.

---

## Dependencies Between Items

```
3 (bugfix)         → independent, do first
4 (async loading)  → independent of others
2 (filter bar)     → independent
1 (add/delete)     → needs public add_event/remove_event API on CatalogProvider
                   → overlay must react to events_changed (prerequisite for 6 too)
6 (lazy loading)   → builds on overlay event diffing from item 1
5 (cocat port)     → needs public add_event/remove_event from item 1
```

Suggested order: **3 → 4 → 2 → 1 → 6 → 5**
