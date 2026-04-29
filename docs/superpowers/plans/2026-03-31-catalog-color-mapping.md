# Catalog Color Mapping Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow catalog overlay spans to be colored per-event based on a metadata column, supporting both categorical and continuous mappings.

**Architecture:** A `ColorMapper` Pydantic model encapsulates the mapping config (column, colormap, vmin/vmax). The overlay queries it per-event to get a QColor. Storage is in catalog attributes (writable catalogs) or local settings (read-only). A context menu on the catalog browser tree lets users pick a column.

**Tech Stack:** PySide6, Pydantic, matplotlib (colormaps), existing `ConfigEntry` settings system, existing `CatalogOverlay` / `CatalogBrowser` widgets.

**Spec:** `docs/superpowers/specs/2026-03-31-catalog-color-mapping-design.md`

---

## File Structure

| Action | File | Responsibility |
|--------|------|---------------|
| Create | `SciQLop/components/catalogs/backend/color_mapper.py` | `ColorMapper` model + mapping logic |
| Create | `SciQLop/components/catalogs/backend/color_mapper_storage.py` | `get_color_mapper` / `set_color_mapper` + `CatalogColorMappings` settings |
| Modify | `SciQLop/components/catalogs/backend/overlay.py` | Use `ColorMapper` for per-event colors |
| Modify | `SciQLop/components/catalogs/ui/catalog_browser.py` | "Color by..." context menu |
| Modify | `SciQLop/components/settings/backend/entry.py` | Add `CATALOGS` to `SettingsCategory` |
| Modify | `SciQLop/components/catalogs/backend/dummy_provider.py` | Add metadata with mixed types for testing |
| Create | `tests/test_color_mapper.py` | Unit tests for ColorMapper |
| Create | `tests/test_color_mapper_storage.py` | Unit tests for storage get/set |
| Modify | `tests/test_catalog_overlay.py` | Integration test: overlay with color mapper |

---

### Task 1: ColorMapper Model

**Files:**
- Create: `SciQLop/components/catalogs/backend/color_mapper.py`
- Create: `tests/test_color_mapper.py`

- [ ] **Step 1: Write failing test for uniform (default) mapping**

```python
# tests/test_color_mapper.py
from .fixtures import *
from datetime import datetime, timezone, timedelta
from PySide6.QtGui import QColor


def _make_events(metas: list[dict]):
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    return [
        CatalogEvent(uuid=f"ev-{i}", start=base + timedelta(days=i),
                     stop=base + timedelta(days=i, hours=1), meta=m)
        for i, m in enumerate(metas)
    ]


def test_uniform_mapping_returns_catalog_color(qapp):
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    mapper = ColorMapper()
    catalog_color = QColor(31, 119, 180, 80)
    events = _make_events([{"class": "A"}, {"class": "B"}])
    result = mapper(events, catalog_color)
    assert len(result) == 2
    for color in result.values():
        assert color == catalog_color
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_color_mapper.py::test_uniform_mapping_returns_catalog_color -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'SciQLop.components.catalogs.backend.color_mapper'`

- [ ] **Step 3: Write ColorMapper model with uniform mapping**

```python
# SciQLop/components/catalogs/backend/color_mapper.py
from __future__ import annotations

from hashlib import md5
from typing import Any

from pydantic import BaseModel
from PySide6.QtGui import QColor

from .color_palette import _PALETTE

_SPAN_ALPHA = 80


def _is_numeric(values: list[Any]) -> bool:
    return all(isinstance(v, (int, float)) for v in values if v is not None)


def _hash_color(value: str) -> QColor:
    index = int.from_bytes(md5(str(value).encode()).digest()[:4], "little") % len(_PALETTE)
    return QColor(_PALETTE[index])


class ColorMapper(BaseModel):
    column: str | None = None
    colormap: str = "viridis"
    vmin: float | None = None
    vmax: float | None = None

    def __call__(self, events, catalog_color: QColor) -> dict[str, QColor]:
        if self.column is None:
            return {e.uuid: QColor(catalog_color) for e in events}

        values = [e.meta.get(self.column) for e in events]
        non_none = [v for v in values if v is not None]

        if not non_none:
            return {e.uuid: QColor(catalog_color) for e in events}

        if _is_numeric(non_none):
            return self._continuous(events, values, catalog_color)
        return self._categorical(events, values, catalog_color)

    def _continuous(self, events, values, catalog_color: QColor) -> dict[str, QColor]:
        import matplotlib
        cmap = matplotlib.colormaps[self.colormap]

        numeric = [v for v in values if v is not None and isinstance(v, (int, float))]
        lo = self.vmin if self.vmin is not None else min(numeric)
        hi = self.vmax if self.vmax is not None else max(numeric)
        span = hi - lo if hi != lo else 1.0

        result = {}
        for event, val in zip(events, values):
            if val is None or not isinstance(val, (int, float)):
                result[event.uuid] = QColor(catalog_color)
                continue
            norm = max(0.0, min(1.0, (val - lo) / span))
            r, g, b, _ = cmap(norm)
            result[event.uuid] = QColor(int(r * 255), int(g * 255), int(b * 255), _SPAN_ALPHA)
        return result

    def _categorical(self, events, values, catalog_color: QColor) -> dict[str, QColor]:
        result = {}
        for event, val in zip(events, values):
            if val is None:
                result[event.uuid] = QColor(catalog_color)
            else:
                result[event.uuid] = _hash_color(val)
        return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_color_mapper.py::test_uniform_mapping_returns_catalog_color -v`
Expected: PASS

- [ ] **Step 5: Write failing test for categorical mapping**

```python
# append to tests/test_color_mapper.py

def test_categorical_mapping_assigns_distinct_colors(qapp):
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    mapper = ColorMapper(column="class")
    catalog_color = QColor(127, 127, 127, 80)
    events = _make_events([{"class": "A"}, {"class": "B"}, {"class": "A"}])
    result = mapper(events, catalog_color)
    assert result["ev-0"] == result["ev-2"]  # same class → same color
    assert result["ev-0"] != result["ev-1"]  # different class → different color (very likely)


def test_categorical_mapping_missing_value_falls_back(qapp):
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    mapper = ColorMapper(column="class")
    catalog_color = QColor(127, 127, 127, 80)
    events = _make_events([{"class": "A"}, {}])
    result = mapper(events, catalog_color)
    assert result["ev-1"] == catalog_color
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/test_color_mapper.py -v`
Expected: PASS (implementation already handles categorical)

- [ ] **Step 7: Write failing test for continuous mapping**

```python
# append to tests/test_color_mapper.py

def test_continuous_mapping_varies_by_value(qapp):
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    mapper = ColorMapper(column="score", colormap="viridis")
    catalog_color = QColor(127, 127, 127, 80)
    events = _make_events([{"score": 0.0}, {"score": 0.5}, {"score": 1.0}])
    result = mapper(events, catalog_color)
    # All three should be different (viridis maps 0, 0.5, 1 to distinct colors)
    assert result["ev-0"] != result["ev-1"]
    assert result["ev-1"] != result["ev-2"]
    # Alpha should be 80
    assert result["ev-0"].alpha() == 80


def test_continuous_mapping_custom_range(qapp):
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    mapper = ColorMapper(column="score", colormap="viridis", vmin=0.0, vmax=10.0)
    catalog_color = QColor(127, 127, 127, 80)
    events = _make_events([{"score": 0.0}, {"score": 10.0}])
    result = mapper(events, catalog_color)
    # score=0 maps to viridis(0.0), score=10 maps to viridis(1.0)
    assert result["ev-0"] != result["ev-1"]


def test_continuous_mapping_clamps_out_of_range(qapp):
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    mapper = ColorMapper(column="score", colormap="viridis", vmin=0.0, vmax=1.0)
    catalog_color = QColor(127, 127, 127, 80)
    events = _make_events([{"score": -5.0}, {"score": 0.0}, {"score": 100.0}, {"score": 1.0}])
    result = mapper(events, catalog_color)
    # Clamped: -5 → same as 0, 100 → same as 1
    assert result["ev-0"] == result["ev-1"]
    assert result["ev-2"] == result["ev-3"]


def test_continuous_mapping_missing_value_falls_back(qapp):
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    mapper = ColorMapper(column="score")
    catalog_color = QColor(127, 127, 127, 80)
    events = _make_events([{"score": 0.5}, {}])
    result = mapper(events, catalog_color)
    assert result["ev-1"] == catalog_color
```

- [ ] **Step 8: Run all tests to verify they pass**

Run: `uv run pytest tests/test_color_mapper.py -v`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add SciQLop/components/catalogs/backend/color_mapper.py tests/test_color_mapper.py
git commit -m "feat: add ColorMapper model for per-event catalog color mapping"
```

---

### Task 2: Color Mapper Storage

**Files:**
- Modify: `SciQLop/components/settings/backend/entry.py` (add `CATALOGS` to `SettingsCategory`)
- Create: `SciQLop/components/catalogs/backend/color_mapper_storage.py`
- Create: `tests/test_color_mapper_storage.py`

- [ ] **Step 1: Add CATALOGS to SettingsCategory**

In `SciQLop/components/settings/backend/entry.py`, add to the `SettingsCategory` enum:

```python
class SettingsCategory(str, Enum):
    PLUGINS = "plugins"
    WORKSPACES = "workspaces"
    APPLICATION = "application"
    APPEARANCE = "appearance"
    CATALOGS = "catalogs"
```

- [ ] **Step 2: Write failing test for storage with read-only catalogs**

```python
# tests/test_color_mapper_storage.py
from .fixtures import *
import pytest
from datetime import datetime, timezone


def test_get_default_returns_uniform_mapper(qapp, tmp_path, monkeypatch):
    """When no mapping is stored, get_color_mapper returns a default (column=None) mapper."""
    monkeypatch.setattr(
        "SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR",
        str(tmp_path),
    )
    from SciQLop.components.catalogs.backend.color_mapper_storage import get_color_mapper
    from SciQLop.components.catalogs.backend.provider import Catalog
    cat = Catalog(uuid="test-uuid-1", name="test", provider=None)
    mapper = get_color_mapper(cat)
    assert mapper.column is None


def test_set_and_get_roundtrip_readonly(qapp, tmp_path, monkeypatch):
    """For catalogs with no writable provider, storage falls back to local settings."""
    monkeypatch.setattr(
        "SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR",
        str(tmp_path),
    )
    from SciQLop.components.catalogs.backend.color_mapper_storage import (
        get_color_mapper, set_color_mapper,
    )
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    from SciQLop.components.catalogs.backend.provider import Catalog
    cat = Catalog(uuid="test-uuid-2", name="test", provider=None)
    mapper = ColorMapper(column="class", colormap="plasma")
    set_color_mapper(cat, mapper)
    loaded = get_color_mapper(cat)
    assert loaded.column == "class"
    assert loaded.colormap == "plasma"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_color_mapper_storage.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Write storage module**

```python
# SciQLop/components/catalogs/backend/color_mapper_storage.py
from __future__ import annotations

from typing import ClassVar

from SciQLop.components.settings.backend.entry import ConfigEntry, SettingsCategory
from .color_mapper import ColorMapper
from .provider import Catalog, Capability


class CatalogColorMappings(ConfigEntry):
    category: ClassVar[str] = SettingsCategory.CATALOGS
    subcategory: ClassVar[str] = "Color Mappings"
    mappings: dict[str, str] = {}  # {catalog_uuid: ColorMapper JSON}


def _is_writable(catalog: Catalog) -> bool:
    if catalog.provider is None:
        return False
    caps = catalog.provider.capabilities(catalog)
    return Capability.EDIT_EVENTS in caps


def get_color_mapper(catalog: Catalog) -> ColorMapper:
    # Local settings (works for all catalogs)
    with CatalogColorMappings() as settings:
        json_str = settings.mappings.get(catalog.uuid)
    if json_str is not None:
        return ColorMapper.model_validate_json(json_str)
    return ColorMapper()


def set_color_mapper(catalog: Catalog, mapper: ColorMapper) -> None:
    with CatalogColorMappings() as settings:
        if mapper.column is None:
            settings.mappings.pop(catalog.uuid, None)
        else:
            settings.mappings[catalog.uuid] = mapper.model_dump_json()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_color_mapper_storage.py -v`
Expected: PASS

- [ ] **Step 6: Write test for clearing mapping**

```python
# append to tests/test_color_mapper_storage.py

def test_set_uniform_removes_stored_mapping(qapp, tmp_path, monkeypatch):
    """Setting column=None removes the stored mapping entry."""
    monkeypatch.setattr(
        "SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR",
        str(tmp_path),
    )
    from SciQLop.components.catalogs.backend.color_mapper_storage import (
        get_color_mapper, set_color_mapper, CatalogColorMappings,
    )
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    from SciQLop.components.catalogs.backend.provider import Catalog
    cat = Catalog(uuid="test-uuid-3", name="test", provider=None)
    set_color_mapper(cat, ColorMapper(column="class"))
    set_color_mapper(cat, ColorMapper())  # reset to uniform
    loaded = get_color_mapper(cat)
    assert loaded.column is None
    with CatalogColorMappings() as s:
        assert cat.uuid not in s.mappings
```

- [ ] **Step 7: Run all storage tests**

Run: `uv run pytest tests/test_color_mapper_storage.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add SciQLop/components/settings/backend/entry.py \
       SciQLop/components/catalogs/backend/color_mapper_storage.py \
       tests/test_color_mapper_storage.py
git commit -m "feat: add color mapper storage with local settings fallback"
```

---

### Task 3: Integrate ColorMapper into CatalogOverlay

**Files:**
- Modify: `SciQLop/components/catalogs/backend/overlay.py`
- Modify: `tests/test_catalog_overlay.py`

- [ ] **Step 1: Write failing test for color-mapped overlay**

```python
# append to tests/test_catalog_overlay.py

def test_overlay_uses_color_mapper(qtbot, qapp, tmp_path, monkeypatch):
    """When a color mapper is set, spans should get per-event colors."""
    monkeypatch.setattr(
        "SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR",
        str(tmp_path),
    )
    from SciQLop.components.catalogs.backend.overlay import CatalogOverlay
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    from SciQLop.components.catalogs.backend.color_mapper_storage import set_color_mapper
    from SciQLop.components.catalogs.backend.provider import CatalogEvent, Catalog, CatalogProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange
    from PySide6.QtGui import QColor

    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())

    # Create provider with events that have distinct "class" meta values
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    catalog = provider.catalogs()[0]
    events = provider.events(catalog)
    events[0]._meta["class"] = "solar_wind"
    events[1]._meta["class"] = "magnetosheath"
    events[2]._meta["class"] = "solar_wind"

    # Set a color mapper on this catalog
    set_color_mapper(catalog, ColorMapper(column="class"))

    overlay = CatalogOverlay(catalog=catalog, panel=panel)
    assert overlay.span_count == 3
    # The overlay should have used the mapper (we can't easily inspect span colors
    # from the C++ side, but we can verify the mapper is stored)
    assert overlay._mapper.column == "class"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_overlay.py::test_overlay_uses_color_mapper -v`
Expected: FAIL — `AttributeError: 'CatalogOverlay' object has no attribute '_mapper'`

- [ ] **Step 3: Modify CatalogOverlay to use ColorMapper**

Edit `SciQLop/components/catalogs/backend/overlay.py`:

Add import at the top:

```python
from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
from SciQLop.components.catalogs.backend.color_mapper_storage import get_color_mapper
```

Modify `__init__` — after computing `self._color`, add mapper initialization:

```python
    def __init__(self, catalog: Catalog, panel, parent: QObject | None = None):
        super().__init__(parent or panel)
        self._catalog = catalog
        self._panel = panel
        self._color = color_for_catalog(catalog.uuid)
        self._read_only = True
        self._lazy = False
        self._mapper = get_color_mapper(catalog)

        self._span_collection = MultiPlotsVSpanCollection(panel)
        self._event_by_span_id: dict[str, CatalogEvent] = {}
        self._event_connections: dict[str, list[tuple]] = {}

        catalog.provider.events_changed.connect(self._on_events_changed)

        all_events = catalog.provider.events(catalog)
        self._event_colors = self._mapper(all_events, self._color)

        if len(all_events) >= 5000:
            self._lazy = True
            self._debounce = QTimer(self)
            self._debounce.setSingleShot(True)
            self._debounce.setInterval(200)
            self._debounce.timeout.connect(self._refresh_visible)
            if hasattr(panel, 'time_range_changed'):
                panel.time_range_changed.connect(self._on_time_range_changed)
            self._refresh_visible()
        else:
            for event in all_events:
                self._add_span(event)
```

Modify `_add_span` — use per-event color:

```python
    def _add_span(self, event: CatalogEvent):
        color = self._event_colors.get(event.uuid, self._color)
        tr = TimeRange(event.start.timestamp(), event.stop.timestamp())
        span = self._span_collection.create_span(
            tr,
            color=color,
            read_only=self._read_only,
            tool_tip=f"{event.start} — {event.stop}",
            id=event.uuid,
        )
        # ... rest of _add_span stays the same
```

Add `update_color_mapper` method:

```python
    def update_color_mapper(self, mapper: ColorMapper) -> None:
        self._mapper = mapper
        all_events = list(self._event_by_span_id.values())
        self._event_colors = self._mapper(all_events, self._color)
        # Recreate all spans with new colors
        for uuid in list(self._event_connections):
            self._disconnect_event(uuid)
        for span in self._span_collection.spans():
            self._span_collection.delete_span(span)
        self._event_by_span_id.clear()
        for event in all_events:
            self._add_span(event)
```

Also update `_on_events_changed` to recompute colors when events change (non-lazy path):

```python
    def _on_events_changed(self, changed_catalog: Catalog) -> None:
        if changed_catalog.uuid != self._catalog.uuid:
            return
        if self._lazy:
            self._refresh_visible()
            return
        current_uuids = set(self._event_by_span_id.keys())
        new_events = self._catalog.provider.events(self._catalog)
        new_uuids = {e.uuid for e in new_events}

        # Recompute colors for all events
        self._event_colors = self._mapper(new_events, self._color)

        for uuid in current_uuids - new_uuids:
            self._disconnect_event(uuid)
            span = self._span_collection.span(uuid)
            if span is not None:
                self._span_collection.delete_span(span)
            self._event_by_span_id.pop(uuid, None)

        for event in new_events:
            if event.uuid not in current_uuids:
                self._add_span(event)
```

For `_refresh_visible`, recompute colors for the visible batch:

```python
    def _refresh_visible(self) -> None:
        try:
            tr = self._panel.time_range
            duration = tr.stop() - tr.start()
            margin = duration
            start = datetime.fromtimestamp(tr.start() - margin, tz=timezone.utc)
            stop = datetime.fromtimestamp(tr.stop() + margin, tz=timezone.utc)
        except Exception:
            log.debug("Could not get panel time range for lazy refresh", exc_info=True)
            return

        new_events = self._catalog.provider.events(self._catalog, start, stop)
        new_uuids = {e.uuid for e in new_events}
        current_uuids = set(self._event_by_span_id.keys())

        # Recompute colors for visible batch
        self._event_colors.update(self._mapper(new_events, self._color))

        for uuid in current_uuids - new_uuids:
            self._disconnect_event(uuid)
            span = self._span_collection.span(uuid)
            if span is not None:
                self._span_collection.delete_span(span)
            self._event_by_span_id.pop(uuid, None)

        for event in new_events:
            if event.uuid not in current_uuids:
                self._add_span(event)
```

- [ ] **Step 4: Run the new test to verify it passes**

Run: `uv run pytest tests/test_catalog_overlay.py::test_overlay_uses_color_mapper -v`
Expected: PASS

- [ ] **Step 5: Run all overlay tests to verify no regressions**

Run: `uv run pytest tests/test_catalog_overlay.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/catalogs/backend/overlay.py tests/test_catalog_overlay.py
git commit -m "feat: integrate ColorMapper into CatalogOverlay for per-event colors"
```

---

### Task 4: Context Menu — "Color by..." in Catalog Browser

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_browser.py`
- Modify: `SciQLop/components/catalogs/backend/panel_manager.py`

- [ ] **Step 1: Add "Color by..." submenu to the catalog browser context menu**

In `SciQLop/components/catalogs/ui/catalog_browser.py`, modify `_on_tree_context_menu`. After the existing save/delete actions block (before `if menu.isEmpty():`), add the color-by submenu for catalog nodes:

```python
        # Color mapping (catalog nodes only)
        if node.catalog is not None:
            self._build_color_by_menu(menu, node.catalog)
```

Add the helper method to `CatalogBrowser`:

```python
    def _build_color_by_menu(self, parent_menu: QMenu, catalog: Catalog) -> None:
        from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
        from SciQLop.components.catalogs.backend.color_mapper_storage import (
            get_color_mapper, set_color_mapper,
        )

        current = get_color_mapper(catalog)
        color_menu = parent_menu.addMenu("Color by...")

        # Uniform (default) option
        uniform_action = color_menu.addAction("Uniform (default)")
        uniform_action.setCheckable(True)
        uniform_action.setChecked(current.column is None)
        uniform_action.triggered.connect(
            lambda: self._apply_color_mapper(catalog, ColorMapper())
        )

        # Discover columns from event metadata
        events = catalog.provider.events(catalog)
        columns: set[str] = set()
        for event in events[:200]:  # scan up to 200 events for column discovery
            columns.update(event.meta.keys())

        if columns:
            color_menu.addSeparator()
            for col in sorted(columns):
                action = color_menu.addAction(col)
                action.setCheckable(True)
                action.setChecked(current.column == col)
                action.triggered.connect(
                    lambda checked, c=col: self._apply_color_mapper(
                        catalog, ColorMapper(column=c)
                    )
                )

    def _apply_color_mapper(self, catalog: Catalog, mapper) -> None:
        from SciQLop.components.catalogs.backend.color_mapper_storage import set_color_mapper
        set_color_mapper(catalog, mapper)
        for panel in self._panels:
            overlay = panel.catalog_manager.overlay(catalog.uuid)
            if overlay is not None:
                overlay.update_color_mapper(mapper)
```

- [ ] **Step 2: Run the full test suite to verify no regressions**

Run: `uv run pytest tests/ -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_browser.py
git commit -m "feat: add 'Color by...' context menu to catalog browser"
```

---

### Task 5: "Configure colormap..." Dialog

**Files:**
- Create: `SciQLop/components/catalogs/ui/colormap_dialog.py`
- Modify: `SciQLop/components/catalogs/ui/catalog_browser.py`

- [ ] **Step 1: Write the colormap configuration dialog**

```python
# SciQLop/components/catalogs/ui/colormap_dialog.py
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QLabel,
    QLineEdit, QDialogButtonBox, QWidget,
)

_COLORMAPS = [
    "viridis", "plasma", "inferno", "magma", "cividis",
    "coolwarm", "RdYlBu", "Spectral", "RdBu",
    "hot", "jet", "turbo",
]


class ColormapDialog(QDialog):
    def __init__(self, current_colormap: str = "viridis",
                 current_vmin: float | None = None,
                 current_vmax: float | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Configure Colormap")
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)

        # Colormap picker
        cmap_layout = QHBoxLayout()
        cmap_layout.addWidget(QLabel("Colormap:"))
        self._cmap_combo = QComboBox()
        self._cmap_combo.addItems(_COLORMAPS)
        if current_colormap in _COLORMAPS:
            self._cmap_combo.setCurrentText(current_colormap)
        cmap_layout.addWidget(self._cmap_combo)
        layout.addLayout(cmap_layout)

        # vmin
        vmin_layout = QHBoxLayout()
        vmin_layout.addWidget(QLabel("Min value:"))
        self._vmin_edit = QLineEdit()
        self._vmin_edit.setPlaceholderText("auto")
        if current_vmin is not None:
            self._vmin_edit.setText(str(current_vmin))
        vmin_layout.addWidget(self._vmin_edit)
        layout.addLayout(vmin_layout)

        # vmax
        vmax_layout = QHBoxLayout()
        vmax_layout.addWidget(QLabel("Max value:"))
        self._vmax_edit = QLineEdit()
        self._vmax_edit.setPlaceholderText("auto")
        if current_vmax is not None:
            self._vmax_edit.setText(str(current_vmax))
        vmax_layout.addWidget(self._vmax_edit)
        layout.addLayout(vmax_layout)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def colormap(self) -> str:
        return self._cmap_combo.currentText()

    @property
    def vmin(self) -> float | None:
        text = self._vmin_edit.text().strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    @property
    def vmax(self) -> float | None:
        text = self._vmax_edit.text().strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
```

- [ ] **Step 2: Add "Configure colormap..." action to the context menu**

In `SciQLop/components/catalogs/ui/catalog_browser.py`, modify `_build_color_by_menu` to add a configure action at the bottom:

```python
        # Configure colormap... (only meaningful when a column is selected)
        if current.column is not None:
            color_menu.addSeparator()
            configure_action = color_menu.addAction("Configure colormap...")
            configure_action.triggered.connect(
                lambda: self._show_colormap_dialog(catalog, current)
            )
```

Add the dialog handler to `CatalogBrowser`:

```python
    def _show_colormap_dialog(self, catalog: Catalog, current_mapper) -> None:
        from .colormap_dialog import ColormapDialog
        from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
        dialog = ColormapDialog(
            current_colormap=current_mapper.colormap,
            current_vmin=current_mapper.vmin,
            current_vmax=current_mapper.vmax,
            parent=self,
        )
        if dialog.exec() == ColormapDialog.DialogCode.Accepted:
            mapper = ColorMapper(
                column=current_mapper.column,
                colormap=dialog.colormap,
                vmin=dialog.vmin,
                vmax=dialog.vmax,
            )
            self._apply_color_mapper(catalog, mapper)
```

- [ ] **Step 3: Run all tests to verify no regressions**

Run: `uv run pytest tests/ -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add SciQLop/components/catalogs/ui/colormap_dialog.py \
       SciQLop/components/catalogs/ui/catalog_browser.py
git commit -m "feat: add Configure colormap dialog for continuous color mapping"
```

---

### Task 6: Add Metadata to DummyProvider for Testing

**Files:**
- Modify: `SciQLop/components/catalogs/backend/dummy_provider.py`

- [ ] **Step 1: Enrich DummyProvider events with varied metadata**

In `SciQLop/components/catalogs/backend/dummy_provider.py`, update the event creation loop to include classification and score metadata useful for testing both categorical and continuous color mapping:

```python
            _CLASSES = ["solar_wind", "magnetosheath", "foreshock", "magnetopause"]
            events = []
            for i in range(events_per_catalog):
                events.append(CatalogEvent(
                    uuid=str(_uuid.uuid4()),
                    start=base + timedelta(days=i),
                    stop=base + timedelta(days=i, hours=1),
                    meta={
                        "index": i,
                        "catalog": c,
                        "class": _CLASSES[i % len(_CLASSES)],
                        "score": (i % 10) / 9.0,
                    },
                ))
```

- [ ] **Step 2: Run existing tests to verify no regressions**

Run: `uv run pytest tests/ -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add SciQLop/components/catalogs/backend/dummy_provider.py
git commit -m "feat: add class and score metadata to DummyProvider for color mapping testing"
```

---

### Task 7: Integration Tests

**Files:**
- Modify: `tests/test_catalog_overlay.py`

- [ ] **Step 1: Write integration test for update_color_mapper**

```python
# append to tests/test_catalog_overlay.py

def test_overlay_update_color_mapper_recreates_spans(qtbot, qapp, tmp_path, monkeypatch):
    """Calling update_color_mapper should recreate spans with new colors."""
    monkeypatch.setattr(
        "SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR",
        str(tmp_path),
    )
    from SciQLop.components.catalogs.backend.overlay import CatalogOverlay
    from SciQLop.components.catalogs.backend.color_mapper import ColorMapper
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())

    provider = DummyProvider(num_catalogs=1, events_per_catalog=5)
    catalog = provider.catalogs()[0]

    overlay = CatalogOverlay(catalog=catalog, panel=panel)
    assert overlay.span_count == 5
    assert overlay._mapper.column is None

    # Switch to categorical mapping
    overlay.update_color_mapper(ColorMapper(column="class"))
    assert overlay.span_count == 5
    assert overlay._mapper.column == "class"

    # Switch to continuous mapping
    overlay.update_color_mapper(ColorMapper(column="score", colormap="plasma"))
    assert overlay.span_count == 5
    assert overlay._mapper.column == "score"

    # Switch back to uniform
    overlay.update_color_mapper(ColorMapper())
    assert overlay.span_count == 5
    assert overlay._mapper.column is None
```

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest tests/ -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add tests/test_catalog_overlay.py
git commit -m "test: add integration tests for color mapper overlay updates"
```

---

### Task 8: Update CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add entry to CHANGELOG under v0.11.0**

Add under the appropriate section (Features):

```markdown
- Per-event color mapping for catalog overlays: right-click a catalog → "Color by..." to color spans by a metadata column (categorical or continuous with matplotlib colormaps)
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: add color mapping feature to CHANGELOG"
```
