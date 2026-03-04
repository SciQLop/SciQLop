# Plot Integration for Catalog Provider System

## Goal

Connect the unified catalog provider system to plot panels so that catalog
events are drawn as vertical spans on any `TimeSyncPanel`. Each panel
independently selects which catalogs to display and which interaction mode to
use. The existing `LightweightManager` (single-panel, tscat-only) is
superseded by a per-panel, provider-agnostic design.

## Constraints

- Reuse `MultiPlotsVSpanCollection` and `TimeSpanController` (already handle
  100k+ events efficiently).
- Per-panel state: each panel independently chooses catalogs and interaction
  mode.
- Bidirectional selection between `CatalogBrowser` event table and plot spans.
- Fixed catalog colors (consistent across panels).
- Transient state — no persistence across sessions.
- Minimal UI: right-click context menu on the panel, no extra widgets.

## 1. Architecture

### CatalogOverlay

One instance per (panel, catalog) pair. Owns a `MultiPlotsVSpanCollection`
and a `TimeSpanController`. Creates one span per `CatalogEvent` with
bidirectional range synchronization.

```
CatalogProvider.events(catalog) → CatalogOverlay → MultiPlotsVSpanCollection
                                                  ↕ (bidirectional range sync)
                                            TimeSpanController (lazy visibility)
```

### PanelCatalogManager

One per `TimeSyncPanel`, parented to the panel (destroyed with it). Holds a
dict of `{catalog.uuid: CatalogOverlay}`. Provides context menu entries and
manages the interaction mode for its panel.

### Signal Flow (Bidirectional Selection)

```
CatalogBrowser.event_selected(CatalogEvent)
  → PanelCatalogManager.select_event(event)
    → span.selected = True

Span.selection_changed
  → PanelCatalogManager.event_clicked(CatalogEvent)   [signal]
    → CatalogBrowser.highlight_event(event)
```

## 2. Context Menu

Right-clicking a `TimeSyncPanel` shows a **Catalogs** submenu:

```
Catalogs ►
  ☑ TSCat Local / My Catalog A
  ☐ TSCat Local / My Catalog B
  ☐ CoCat / Shared Catalog
  ─────────────
  Mode ►
    ○ View
    ○ Jump
    ○ Edit
```

- Catalog entries are checkable actions — toggle to show/hide on this panel.
- Catalogs listed as `ProviderName / CatalogName`.
- Mode applies to all overlays on this panel.
- List populated dynamically from `CatalogRegistry`.

## 3. Color Assignment

Each catalog gets a fixed color derived by hashing its UUID into a rotating
palette of ~12 distinguishable colors. The color is consistent across all
panels.

## 4. Interaction Modes

| Mode | Click span          | Drag span edge                          |
|------|--------------------|-----------------------------------------|
| View | Select (highlight) | Nothing                                 |
| Jump | Select + zoom      | Nothing                                 |
| Edit | Select             | Resize event (if EDIT_EVENTS capability) |

In Edit mode, `span.read_only` is `False` only if the catalog's provider
supports `Capability.EDIT_EVENTS`. Otherwise spans stay read-only.

## 5. File Layout

```
SciQLop/components/catalogs/backend/
  overlay.py          — CatalogOverlay
  panel_manager.py    — PanelCatalogManager
  color_palette.py    — catalog color assignment
```

## 6. Testing Strategy

### Unit Tests

- `CatalogOverlay` creates spans from events; range sync is bidirectional.
- Color palette assigns consistent colors from UUID.

### Qt Tests

- `PanelCatalogManager` adds/removes overlays correctly.
- Context menu populates from registry.
- Mode changes propagate to span `read_only` state.

### Integration Tests

- Full flow with `DummyProvider`: assign catalog to panel via context menu,
  verify spans appear in visible range.
- Bidirectional selection: click span → browser highlights row; click row →
  span selected on panel.
- Edit mode: drag span edge → `CatalogEvent.start`/`stop` updated.
