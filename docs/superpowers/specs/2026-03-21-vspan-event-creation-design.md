# VSpan-Based Catalog Event Creation

**Date:** 2026-03-21
**Status:** Draft
**Branch:** cocat

## Problem

Users need to create catalog events interactively by drawing time intervals directly on plots. Currently, events can only be created programmatically (Jupyter API) or via the catalog browser's "Add Event" button, which requires manual time entry.

## Solution

When a panel is in EDIT mode, the user can draw a vertical span on the plot to create a new event in a selected target catalog. A combo box (`_catalog_combo`) on the `TimeRangeBar` determines which catalog receives the event.

## Design

### Data flow

```
User draws span on plot
  → panel.span_created(raw_span)
  → PanelCatalogManager._on_span_created(raw_span)
      → extract TimeRange from raw_span.range
      → convert to datetime: datetime.fromtimestamp(ts, tz=timezone.utc)
      → raw_span.deleteLater()  (C++ side removes it from the plot)
      → provider.add_event(target_catalog, CatalogEvent(str(uuid4()), start_dt, stop_dt))
          → provider._add_event() inserts + emits events_changed
              → CatalogOverlay._on_events_changed()
                  → _add_span(event) — managed span with bidirectional sync
```

### Wiring: PanelCatalogManager ↔ TimeRangeBar

`PanelContainer` creates both the `TimeSyncPanel` and the `TimeRangeBar`, and sets `panel._time_range_bar = self.time_range_bar`. `PanelCatalogManager` accesses the bar lazily via `self._panel._time_range_bar` — by the time the user interacts (enters EDIT mode), the bar is guaranteed to exist.

### Components modified

#### 1. `TimeRangeBar` — add `_catalog_combo`

Add a `QComboBox` named `_catalog_combo` to the right side of the layout (after `▶|` button, before trailing stretch). Distinct from the existing `_duration_combo`.

- Shows names of editable catalogs currently overlaid on the panel
- Stores `catalog.uuid` as `itemData` for unambiguous lookup
- Hidden by default (shown only in EDIT mode with editable catalogs)
- Auto-selects first item when populated (avoids requiring an extra click when there's only one choice)
- Exposes methods for external control:
  - `set_catalog_choices(items: list[tuple[str, str]])` — list of `(name, uuid)` pairs; auto-selects first
  - `clear_catalog_choices()` — clears and hides the combo
  - `selected_catalog_uuid() -> str | None` — returns `itemData` of current selection, or None
  - Signal: `catalog_choice_changed(str)` — emits uuid when selection changes

#### 2. `PanelCatalogManager` — orchestrate creation

New responsibilities:

- **Connect to `panel.span_created`** in `__init__` — always connected, but handler is a no-op when not in EDIT mode
- **Toggle span creation** on the panel (`panel.set_span_creation_enabled(bool)`) based on: mode == EDIT AND `_catalog_combo` has a selection
- **Set span creation color** to match the target catalog's overlay color (`panel.set_span_creation_color(color)`)
- **Handle `panel.span_created`**: extract time range, delete raw span via `deleteLater()`, convert epoch floats to `datetime(tz=utc)`, call `provider.add_event()`
- **Update `_catalog_combo`** when overlays are added/removed — filter to catalogs whose provider declares `CREATE_EVENTS` capability
- **React to mode changes**: call `_sync_span_creation_state()` at end of `mode.setter`
- **React to combo box selection changes**: update span creation color, call `_sync_span_creation_state()`
- **Handle target catalog removal**: if the selected catalog is removed while in EDIT mode, the combo box loses that item; auto-selects next item or clears → `_sync_span_creation_state()` disables span creation if nothing left

New private methods:
- `_on_span_created(raw_span)` — the core creation handler
- `_update_creation_target_choices()` — rebuild combo box items from current overlays filtered by `CREATE_EVENTS`
- `_sync_span_creation_state()` — enable/disable `panel.set_span_creation_enabled()` + show/hide combo based on mode + selection

#### 3. No changes to `CatalogOverlay` or `CatalogProvider`

- `CatalogOverlay` already reacts to `events_changed` and creates managed spans
- `CatalogProvider.add_event()` already exists with the right signature
- `events_changed` signal already emitted by `_add_event()`

### Span creation lifecycle

1. User enters EDIT mode (via context menu > Catalogs > Mode > Edit)
2. `_catalog_combo` appears on `TimeRangeBar` with editable catalogs (auto-selects first)
3. `panel.set_span_creation_enabled(True)` + `panel.set_span_creation_color(catalog_color)`
4. User clicks and drags on plot to draw a span
5. `panel.span_created` fires with the raw span
6. `PanelCatalogManager._on_span_created()`: extracts time range, `raw_span.deleteLater()`, calls `provider.add_event()`
7. Provider emits `events_changed` → overlay creates a properly managed span
8. New event appears in catalog browser's event table

### Guard conditions

- Span creation is **only enabled** when mode == EDIT AND `_catalog_combo` has a selection
- Span creation is **disabled** when mode changes away from EDIT, when the combo box is cleared, or when all editable overlays are removed
- The `_catalog_combo` is **hidden** when not in EDIT mode or when no editable catalogs are overlaid
- `span_creation_canceled` signal (emitted when user presses Escape during drawing) requires no handling — C++ side cleans up the in-progress drawing internally

### Raw span cleanup

The raw span emitted by `span_created` is a `MultiPlotsVerticalSpan` created by the panel's internal span-creation mechanism (not by a `MultiPlotsVSpanCollection`). Calling `raw_span.deleteLater()` removes it from the plot — the C++ destructor handles visual cleanup. This is called immediately after extracting the time range, before `add_event()`.

### UUID generation

New events get a `str(uuid4())` string. This is consistent with how cocat and tscat providers generate UUIDs.

### What's NOT in scope

- Event metadata at creation time (just start/stop — metadata added later via event table)
- Keyboard shortcut to toggle EDIT mode
- Jupyter API for this workflow
- Delete event via span (already handled by existing `delete_requested` signal path)
