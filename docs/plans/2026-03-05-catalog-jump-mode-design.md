# Catalog Browser Jump Mode

**Date**: 2026-03-05

## Problem

The catalog browser has one event list view connected to 0-N plot panels. When the user selects an event in the event table, we need to decide which panel(s) should jump to show that event.

## Design

### Behavior

When an event is selected in the catalog browser's event table, all connected panels whose `InteractionMode` is `JUMP` adjust their time range to center on that event.

The event occupies ~10% of the visible range. For an event of duration `d`, the visible range is `10 * d`, with `4.5 * d` margin on each side. For zero-duration events, use a fallback of 1 hour each side.

### Toggle

No new UI needed. The existing **Mode** menu (View / Jump / Edit) in each panel's Catalogs context menu serves as the per-panel opt-in toggle.

### Implementation

The wiring already exists:
- `CatalogBrowser._on_event_selected` emits `event_selected(event)`
- `CatalogBrowser.connect_to_panel` wires `event_selected` to `PanelCatalogManager.select_event`

The only change is in `PanelCatalogManager.select_event`: when `self._mode == InteractionMode.JUMP`, compute the time range and set it on the panel.

### Margin Calculation

```
event_duration = event.stop - event.start
if event_duration == 0:
    margin = 3600  # 1 hour fallback
else:
    margin = event_duration * 4.5

time_range = TimeRange(event.start - margin, event.stop + margin)
panel.time_range = time_range
```

This makes the event occupy 10% of the visible range (`d / (d + 2 * 4.5d) = d / 10d = 0.1`).
