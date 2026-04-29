# Catalog Color Mapping Design

## Summary

Add per-event color mapping to catalog overlays on SciQLop plots. Instead of all events in a catalog sharing one color, users can select a catalog column to drive span colors — either categorical (distinct colors per class) or continuous (scalar values mapped through a colormap).

## Use Cases

- **Classification results**: a catalog from a ML classifier has a `class_label` column — each class gets a distinct color on the plot
- **Prediction quality**: a `confidence` column (0–1) mapped through a colormap so uncertain events stand out
- **Physical quantities**: color spans by a scalar like velocity, density, etc.

## Data Model

### ColorMapper

A Pydantic `BaseModel` that encapsulates the mapping configuration:

```python
class ColorMapper(BaseModel):
    column: str | None = None      # None → uniform catalog color (current behavior)
    colormap: str = "viridis"      # matplotlib colormap name (continuous only)
    vmin: float | None = None      # None → auto from data
    vmax: float | None = None      # None → auto from data
```

**Mode detection** is automatic — no explicit mode field. When `column` is set, the mapper inspects the actual values:
- All numeric → continuous mode (use `colormap`, `vmin`, `vmax`)
- Otherwise → categorical mode (hash-based palette assignment)

**Interface:**

```python
def __call__(self, events: list[CatalogEvent], catalog_color: QColor) -> dict[str, QColor]:
    """Maps event UUIDs to QColors."""
```

- Returns `{event.uuid: QColor}` for the overlay to use per-span
- When `column is None`, returns uniform `catalog_color` for all events (backward compatible)
- Events missing the mapped column fall back to `catalog_color`

### Color Computation

**Continuous mode:**
- Use `matplotlib.colormaps[name]` (already a project dependency)
- Normalize values to [0,1] using vmin/vmax (auto-computed from data if not set), clamp out-of-range
- Output QColor with alpha 80 (matching current span transparency)

**Categorical mode:**
- MD5 hash of each unique category value (same approach as existing `color_for_catalog`)
- Index into the existing 12-color palette from `color_palette.py`
- Deterministic: same category always gets the same color across sessions

## Storage

Two storage backends, unified behind a single lookup interface.

### Writable catalogs (cocat)

Store the `ColorMapper` config in the catalog's `attributes` dict:

```python
catalog.attributes["color_mapper"] = mapper.model_dump_json()
```

### Read-only catalogs (speasy, tscat)

Store in a local settings entry using the existing `ConfigEntry` system:

```python
class CatalogColorMappings(ConfigEntry):
    category = SettingsCategory.CATALOGS
    subcategory = "Color Mappings"
    mappings: dict[str, str] = {}  # {catalog_uuid: ColorMapper JSON}
```

Persisted to `~/.config/sciqlop/catalogcolormappings.yaml`.

### Unified access

```python
def get_color_mapper(catalog) -> ColorMapper:
    # 1. Try catalog attributes (writable catalogs)
    # 2. Fall back to local settings (read-only catalogs)
    # 3. Default: ColorMapper() → uniform color

def set_color_mapper(catalog, mapper: ColorMapper):
    # If catalog.provider has EDIT_CATALOG capability → store in catalog attributes
    # Otherwise → store in local settings keyed by catalog.uuid
```

The overlay and UI never need to know which storage backend is used.

## Overlay Integration

### CatalogOverlay changes

**Initialization** — fetch mapper and compute colors:
```python
self._mapper = get_color_mapper(catalog)
self._event_colors = self._mapper(all_events, self._color)
```

**`_add_span` changes** — use per-event color:
```python
color = self._event_colors.get(event.uuid, self._color)
self._span_collection.create_span(time_range, color=color, ...)
```

**When mapping changes** — rebuild all span colors:
```python
def update_color_mapper(self, mapper: ColorMapper):
    self._mapper = mapper
    self._event_colors = self._mapper(all_events, self._color)
    # Recreate spans with new colors
```

### Lazy loading (5000+ events)

For large catalogs, the mapper computes colors for whatever batch of events is currently loaded. For continuous mode with auto min/max, the range may shift as more events come into view — this is acceptable and expected behavior for large catalogs.

## UI: Context Menu

Right-click a catalog in the catalog browser → **Color by...** submenu:

```
── Color by ──────────
✓ Uniform (default)
──────────────────────
  class_label
  confidence
  region
  velocity
──────────────────────
  Configure colormap...
```

- **Uniform** resets to current behavior (`column=None`)
- Column names are populated from the catalog's event metadata keys
- Selecting a column immediately applies the mapping and updates all visible spans
- **Configure colormap...** opens a small dialog for continuous columns: colormap picker (dropdown of matplotlib colormaps) and optional vmin/vmax override fields
- Categorical columns ignore the colormap settings

### Column discovery

Columns are discovered by scanning event metadata keys from the catalog's events. For lazy-loaded catalogs, scan the currently loaded batch — this is sufficient since metadata schema is typically uniform across events.

## Backward Compatibility

- `ColorMapper()` with `column=None` produces identical behavior to the current system
- No changes to `CatalogEvent`, `color_for_catalog()`, or the C++ span API
- Existing catalogs with no color mapping config get uniform coloring as before
- The `color_for_catalog()` function remains the source of the default uniform color

## Testing

- Unit tests for `ColorMapper`: continuous mapping, categorical mapping, missing values, auto min/max, clamping
- Unit tests for storage: get/set with writable catalogs, get/set with read-only fallback
- Integration test: overlay with color-mapped catalog, verify spans have different colors
