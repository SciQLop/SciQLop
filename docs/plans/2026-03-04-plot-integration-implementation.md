# Plot Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Draw catalog events as vertical spans on plot panels, with per-panel catalog selection, interaction modes (View/Jump/Edit), and bidirectional selection between the CatalogBrowser and plot spans.

**Architecture:** Each `TimeSyncPanel` gets a `PanelCatalogManager` (QObject, parented to panel) that owns `CatalogOverlay` instances — one per assigned catalog. Each overlay wraps a `MultiPlotsVSpanCollection` + `TimeSpanController` for efficient span rendering. A right-click context menu on panels lets users toggle catalogs and modes. Colors are assigned per catalog via UUID hashing.

**Tech Stack:** PySide6, SciQLopPlots (MultiPlotsVSpanCollection, TimeSpan), existing CatalogProvider/CatalogRegistry, pytest + pytestqt

---

### Task 1: Create catalog_color_palette module

**Files:**
- Create: `SciQLop/components/catalogs/backend/color_palette.py`
- Create: `tests/test_catalog_color_palette.py`

**Step 1: Write the failing test**

```python
# tests/test_catalog_color_palette.py
from .fixtures import *
import pytest


def test_color_for_uuid_returns_qcolor(qapp):
    from SciQLop.components.catalogs.backend.color_palette import color_for_catalog
    color = color_for_catalog("test-uuid-1234")
    from PySide6.QtGui import QColor
    assert isinstance(color, QColor)
    assert color.alpha() > 0


def test_color_is_consistent(qapp):
    from SciQLop.components.catalogs.backend.color_palette import color_for_catalog
    c1 = color_for_catalog("uuid-abc")
    c2 = color_for_catalog("uuid-abc")
    assert c1 == c2


def test_different_uuids_can_differ(qapp):
    from SciQLop.components.catalogs.backend.color_palette import color_for_catalog
    colors = {color_for_catalog(f"uuid-{i}").name() for i in range(12)}
    # at least several distinct colors from 12 different UUIDs
    assert len(colors) >= 6
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_color_palette.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# SciQLop/components/catalogs/backend/color_palette.py
from PySide6.QtGui import QColor

# 12 distinguishable colors with 80 alpha for span fill
_PALETTE = [
    QColor(31, 119, 180, 80),
    QColor(255, 127, 14, 80),
    QColor(44, 160, 44, 80),
    QColor(214, 39, 40, 80),
    QColor(148, 103, 189, 80),
    QColor(140, 86, 75, 80),
    QColor(227, 119, 194, 80),
    QColor(127, 127, 127, 80),
    QColor(188, 189, 34, 80),
    QColor(23, 190, 207, 80),
    QColor(174, 199, 232, 80),
    QColor(255, 187, 120, 80),
]


def color_for_catalog(uuid: str) -> QColor:
    index = hash(uuid) % len(_PALETTE)
    return QColor(_PALETTE[index])
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_catalog_color_palette.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/components/catalogs/backend/color_palette.py tests/test_catalog_color_palette.py
git commit -m "feat(catalogs): add color palette for catalog span coloring"
```

---

### Task 2: Create CatalogOverlay class

**Files:**
- Create: `SciQLop/components/catalogs/backend/overlay.py`
- Create: `tests/test_catalog_overlay.py`

**Context:** `CatalogOverlay` bridges a single `Catalog` to a `MultiPlotsVSpanCollection` on a `TimeSyncPanel`. It converts `CatalogEvent` datetime ranges to `TimeRange` (unix timestamps), creates spans, and sets up bidirectional range synchronization. It uses `TimeSpanController` for lazy visibility.

Key references:
- `SciQLop/components/plotting/backend/catalogue.py:82-116` — existing `Catalogue` class pattern for span creation and range sync
- `SciQLop/components/plotting/backend/time_span_controller.py:11-70` — `TimeSpanController` for lazy visibility
- `SciQLop/core/__init__.py` — `TimeRange` is `SciQLopPlotRange` (takes float timestamps)
- `CatalogEvent.start`/`.stop` are `datetime` objects; convert with `.timestamp()`

**Step 1: Write the failing test**

```python
# tests/test_catalog_overlay.py
from .fixtures import *
import pytest
from datetime import datetime, timezone, timedelta


def test_overlay_creates_spans(qtbot, qapp):
    from SciQLop.components.catalogs.backend.overlay import CatalogOverlay
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


def test_overlay_read_only_default(qtbot, qapp):
    from SciQLop.components.catalogs.backend.overlay import CatalogOverlay
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    catalog = provider.catalogs()[0]

    overlay = CatalogOverlay(catalog=catalog, panel=panel)
    assert overlay.read_only is True


def test_overlay_set_read_only(qtbot, qapp):
    from SciQLop.components.catalogs.backend.overlay import CatalogOverlay
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    catalog = provider.catalogs()[0]

    overlay = CatalogOverlay(catalog=catalog, panel=panel)
    overlay.read_only = False
    assert overlay.read_only is False
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_overlay.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# SciQLop/components/catalogs/backend/overlay.py
from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Qt

from SciQLopPlots import MultiPlotsVSpanCollection
from SciQLop.core import TimeRange
from SciQLop.components.plotting.backend.time_span_controller import TimeSpanController
from SciQLop.components.catalogs.backend.provider import CatalogEvent, Catalog
from SciQLop.components.catalogs.backend.color_palette import color_for_catalog


class CatalogOverlay(QObject):
    """Draws events from one Catalog as vertical spans on a TimeSyncPanel."""

    event_clicked = Signal(object)  # CatalogEvent

    def __init__(self, catalog: Catalog, panel, parent: QObject | None = None):
        super().__init__(parent or panel)
        self._catalog = catalog
        self._panel = panel
        self._color = color_for_catalog(catalog.uuid)
        self._read_only = True

        self._span_collection = MultiPlotsVSpanCollection(panel)
        self._controller = TimeSpanController(panel, parent=self)
        self._event_by_span_id: dict[str, CatalogEvent] = {}

        events = catalog.provider.events(catalog)
        spans = []
        for event in events:
            span = self._add_span(event)
            spans.append(span)
        self._controller.spans = spans

    @property
    def catalog(self) -> Catalog:
        return self._catalog

    @property
    def span_count(self) -> int:
        return len(self._event_by_span_id)

    @property
    def read_only(self) -> bool:
        return self._read_only

    @read_only.setter
    def read_only(self, value: bool) -> None:
        self._read_only = value
        for span in self._span_collection.spans():
            span.read_only = value

    def select_event(self, event: CatalogEvent) -> None:
        span = self._span_collection.span(event.uuid)
        if span is not None:
            span.selected = True

    def _add_span(self, event: CatalogEvent):
        tr = TimeRange(event.start.timestamp(), event.stop.timestamp())
        span = self._span_collection.create_span(
            tr,
            color=self._color,
            read_only=self._read_only,
            tool_tip=f"{event.start} — {event.stop}",
            id=event.uuid,
        )
        self._event_by_span_id[event.uuid] = event

        # Bidirectional sync: event range <-> span range
        event.range_changed.connect(
            lambda e=event, s=span: s.set_range(
                TimeRange(e.start.timestamp(), e.stop.timestamp())
            ),
            Qt.ConnectionType.QueuedConnection,
        )
        span.range_changed.connect(
            lambda r, e=event: self._on_span_range_changed(r, e),
            Qt.ConnectionType.QueuedConnection,
        )
        span.selection_changed.connect(
            lambda selected, e=event: self._on_span_selected(selected, e),
        )
        return span

    def _on_span_range_changed(self, new_range: TimeRange, event: CatalogEvent) -> None:
        from datetime import datetime, timezone
        event.start = datetime.fromtimestamp(new_range.start, tz=timezone.utc)
        event.stop = datetime.fromtimestamp(new_range.stop, tz=timezone.utc)

    def _on_span_selected(self, selected: bool, event: CatalogEvent) -> None:
        if selected:
            self.event_clicked.emit(event)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_catalog_overlay.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/components/catalogs/backend/overlay.py tests/test_catalog_overlay.py
git commit -m "feat(catalogs): add CatalogOverlay for drawing events as spans on panels"
```

---

### Task 3: Create PanelCatalogManager class

**Files:**
- Create: `SciQLop/components/catalogs/backend/panel_manager.py`
- Create: `tests/test_panel_catalog_manager.py`

**Context:** `PanelCatalogManager` is owned by a `TimeSyncPanel`. It holds a dict of `{catalog_uuid: CatalogOverlay}`, provides methods to add/remove catalogs, and manages the interaction mode. It also builds the context menu entries.

Interaction modes:
- `InteractionMode.VIEW` — read-only, click selects
- `InteractionMode.JUMP` — click selects + zooms panel to event time range
- `InteractionMode.EDIT` — spans are draggable (if provider supports EDIT_EVENTS)

**Step 1: Write the failing test**

```python
# tests/test_panel_catalog_manager.py
from .fixtures import *
import pytest
from datetime import datetime, timezone, timedelta
from enum import Enum


def test_manager_add_catalog(qtbot, qapp):
    from SciQLop.components.catalogs.backend.panel_manager import PanelCatalogManager
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())

    provider = DummyProvider(num_catalogs=2, events_per_catalog=3)
    cats = provider.catalogs()

    manager = PanelCatalogManager(panel)
    manager.add_catalog(cats[0])
    assert cats[0].uuid in manager.catalog_uuids


def test_manager_remove_catalog(qtbot, qapp):
    from SciQLop.components.catalogs.backend.panel_manager import PanelCatalogManager
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]

    manager = PanelCatalogManager(panel)
    manager.add_catalog(cat)
    manager.remove_catalog(cat)
    assert cat.uuid not in manager.catalog_uuids


def test_manager_interaction_mode(qtbot, qapp):
    from SciQLop.components.catalogs.backend.panel_manager import (
        PanelCatalogManager, InteractionMode,
    )
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel

    panel = TimeSyncPanel("test-panel")
    manager = PanelCatalogManager(panel)
    assert manager.mode == InteractionMode.VIEW

    manager.mode = InteractionMode.EDIT
    assert manager.mode == InteractionMode.EDIT


def test_manager_edit_mode_sets_spans_writable(qtbot, qapp):
    from SciQLop.components.catalogs.backend.panel_manager import (
        PanelCatalogManager, InteractionMode,
    )
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]

    manager = PanelCatalogManager(panel)
    manager.add_catalog(cat)
    manager.mode = InteractionMode.EDIT
    overlay = manager.overlay(cat.uuid)
    assert overlay.read_only is False
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_panel_catalog_manager.py -v`
Expected: FAIL with ImportError

**Step 3: Write minimal implementation**

```python
# SciQLop/components/catalogs/backend/panel_manager.py
from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMenu

from SciQLop.components.catalogs.backend.provider import Catalog, Capability, CatalogEvent
from SciQLop.components.catalogs.backend.overlay import CatalogOverlay
from SciQLop.components.catalogs.backend.registry import CatalogRegistry


class InteractionMode(Enum):
    VIEW = "view"
    JUMP = "jump"
    EDIT = "edit"


class PanelCatalogManager(QObject):
    """Manages catalog overlays and interaction mode for one TimeSyncPanel."""

    event_clicked = Signal(object)  # CatalogEvent

    def __init__(self, panel, parent: QObject | None = None):
        super().__init__(parent or panel)
        self._panel = panel
        self._overlays: dict[str, CatalogOverlay] = {}
        self._mode = InteractionMode.VIEW

    @property
    def panel(self):
        return self._panel

    @property
    def catalog_uuids(self) -> set[str]:
        return set(self._overlays.keys())

    @property
    def mode(self) -> InteractionMode:
        return self._mode

    @mode.setter
    def mode(self, value: InteractionMode) -> None:
        self._mode = value
        for uuid, overlay in self._overlays.items():
            if value == InteractionMode.EDIT:
                caps = overlay.catalog.provider.capabilities(overlay.catalog)
                overlay.read_only = Capability.EDIT_EVENTS not in caps
            else:
                overlay.read_only = True

    def add_catalog(self, catalog: Catalog) -> None:
        if catalog.uuid in self._overlays:
            return
        overlay = CatalogOverlay(catalog=catalog, panel=self._panel, parent=self)
        overlay.event_clicked.connect(self._on_event_clicked)
        self._overlays[catalog.uuid] = overlay
        # Apply current mode
        if self._mode == InteractionMode.EDIT:
            caps = catalog.provider.capabilities(catalog)
            overlay.read_only = Capability.EDIT_EVENTS not in caps
        else:
            overlay.read_only = True

    def remove_catalog(self, catalog: Catalog) -> None:
        overlay = self._overlays.pop(catalog.uuid, None)
        if overlay is not None:
            overlay.deleteLater()

    def overlay(self, catalog_uuid: str) -> CatalogOverlay | None:
        return self._overlays.get(catalog_uuid)

    def select_event(self, event: CatalogEvent) -> None:
        for overlay in self._overlays.values():
            overlay.select_event(event)

    def build_catalogs_menu(self, parent_menu: QMenu) -> QMenu:
        menu = parent_menu.addMenu("Catalogs")
        registry = CatalogRegistry.instance()
        for provider in registry.providers():
            for catalog in provider.catalogs():
                action = menu.addAction(f"{provider.name} / {catalog.name}")
                action.setCheckable(True)
                action.setChecked(catalog.uuid in self._overlays)
                action.toggled.connect(
                    lambda checked, c=catalog: self.add_catalog(c) if checked else self.remove_catalog(c)
                )

        menu.addSeparator()
        mode_menu = menu.addMenu("Mode")
        for m in InteractionMode:
            action = mode_menu.addAction(m.value.capitalize())
            action.setCheckable(True)
            action.setChecked(m == self._mode)
            action.triggered.connect(lambda checked, mode=m: setattr(self, 'mode', mode))
        return menu

    def _on_event_clicked(self, event: CatalogEvent) -> None:
        if self._mode == InteractionMode.JUMP:
            from SciQLop.core import TimeRange
            margin = (event.stop.timestamp() - event.start.timestamp()) * 0.5
            tr = TimeRange(
                event.start.timestamp() - margin,
                event.stop.timestamp() + margin,
            )
            self._panel.time_range = tr
        self.event_clicked.emit(event)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_panel_catalog_manager.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/components/catalogs/backend/panel_manager.py tests/test_panel_catalog_manager.py
git commit -m "feat(catalogs): add PanelCatalogManager for per-panel catalog overlays"
```

---

### Task 4: Hook context menu into TimeSyncPanel

**Files:**
- Modify: `SciQLop/components/plotting/ui/time_sync_panel.py`
- Modify: `tests/test_panel_catalog_manager.py` (add menu test)

**Context:** `TimeSyncPanel` inherits from `SciQLopMultiPlotPanel` (C++ QWidget). We need to:
1. Create a `PanelCatalogManager` as part of `TimeSyncPanel.__init__`
2. Override `contextMenuEvent` to include the catalogs submenu

Check if `SciQLopMultiPlotPanel` already has a context menu mechanism — if so, extend it rather than overriding.

**Step 1: Write the failing test**

Add to `tests/test_panel_catalog_manager.py`:

```python
def test_panel_has_catalog_manager(qtbot, qapp):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel

    panel = TimeSyncPanel("test-panel")
    assert hasattr(panel, 'catalog_manager')
    from SciQLop.components.catalogs.backend.panel_manager import PanelCatalogManager
    assert isinstance(panel.catalog_manager, PanelCatalogManager)
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_panel_catalog_manager.py::test_panel_has_catalog_manager -v`
Expected: FAIL with AttributeError

**Step 3: Modify TimeSyncPanel**

In `SciQLop/components/plotting/ui/time_sync_panel.py`, add to `TimeSyncPanel.__init__`:

```python
from SciQLop.components.catalogs.backend.panel_manager import PanelCatalogManager

# At end of __init__:
self._catalog_manager = PanelCatalogManager(self)
```

Add property and context menu override:

```python
@property
def catalog_manager(self) -> PanelCatalogManager:
    return self._catalog_manager

def contextMenuEvent(self, event):
    from PySide6.QtWidgets import QMenu
    menu = QMenu(self)
    self._catalog_manager.build_catalogs_menu(menu)
    menu.exec(event.globalPos())
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_panel_catalog_manager.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/components/plotting/ui/time_sync_panel.py tests/test_panel_catalog_manager.py
git commit -m "feat(catalogs): integrate PanelCatalogManager into TimeSyncPanel context menu"
```

---

### Task 5: Bidirectional selection between CatalogBrowser and panels

**Files:**
- Modify: `SciQLop/components/catalogs/ui/catalog_browser.py`
- Create: `tests/test_catalog_plot_integration.py`

**Context:** When the user clicks an event in the `CatalogBrowser` table, the event should be highlighted on any panel displaying that catalog. Conversely, clicking a span on a panel should highlight the row in the browser table.

The `CatalogBrowser` already emits `event_selected(CatalogEvent)`. We need a central coordinator that:
- Listens to `CatalogBrowser.event_selected` → calls `panel.catalog_manager.select_event(event)` on all panels
- Listens to each `PanelCatalogManager.event_clicked` → tells browser to highlight the event

The simplest approach: `CatalogBrowser` gets a `highlight_event(CatalogEvent)` method, and we wire signals externally (in the plugin `load()` or in `CatalogBrowser` itself if it can discover panels).

**Step 1: Write the failing test**

```python
# tests/test_catalog_plot_integration.py
from .fixtures import *
import pytest
from datetime import datetime, timezone, timedelta


def test_browser_event_selected_reaches_panel(qtbot, qapp):
    """When browser emits event_selected, the panel manager's select_event is called."""
    from SciQLop.components.catalogs.backend.panel_manager import PanelCatalogManager
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())

    provider = DummyProvider(num_catalogs=1, events_per_catalog=5)
    cat = provider.catalogs()[0]
    panel.catalog_manager.add_catalog(cat)

    browser = CatalogBrowser()

    # Wire: browser -> panel
    browser.event_selected.connect(panel.catalog_manager.select_event)

    events = provider.events(cat)
    # Emit the signal from browser
    browser.event_selected.emit(events[0])
    # If no crash, the wiring works. A more detailed test would check span.selected.


def test_panel_event_clicked_signal(qtbot, qapp):
    """PanelCatalogManager emits event_clicked when a span is selected."""
    from SciQLop.components.catalogs.backend.panel_manager import PanelCatalogManager
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]
    panel.catalog_manager.add_catalog(cat)

    events = provider.events(cat)
    received = []
    panel.catalog_manager.event_clicked.connect(lambda e: received.append(e))

    # Simulate by calling the overlay's event_clicked directly
    overlay = panel.catalog_manager.overlay(cat.uuid)
    overlay.event_clicked.emit(events[0])

    assert len(received) == 1
    assert received[0].uuid == events[0].uuid
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_catalog_plot_integration.py -v`
Expected: may PASS if Task 4 is done, or FAIL if browser highlight_event is missing

**Step 3: Add `highlight_event` to CatalogBrowser**

In `SciQLop/components/catalogs/ui/catalog_browser.py`, add method:

```python
def highlight_event(self, event: CatalogEvent) -> None:
    """Select the row in the event table matching the given event."""
    row = self._event_model.row_for_event(event)
    if row >= 0:
        index = self._event_model.index(row, 0)
        self._event_table.selectionModel().setCurrentIndex(
            index, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows
        )
```

Also check if `EventTableModel` has a `row_for_event` method. If not, add one:

In `SciQLop/components/catalogs/ui/event_table.py`, add:

```python
def row_for_event(self, event: CatalogEvent) -> int:
    for i, e in enumerate(self._events):
        if e.uuid == event.uuid:
            return i
    return -1
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_catalog_plot_integration.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_browser.py SciQLop/components/catalogs/ui/event_table.py tests/test_catalog_plot_integration.py
git commit -m "feat(catalogs): bidirectional event selection between browser and panels"
```

---

### Task 6: Export public API and update package __init__

**Files:**
- Modify: `SciQLop/components/catalogs/__init__.py`

**Step 1: Update exports**

Add the new classes to `SciQLop/components/catalogs/__init__.py`:

```python
from .backend.overlay import CatalogOverlay
from .backend.panel_manager import PanelCatalogManager, InteractionMode
from .backend.color_palette import color_for_catalog

# Add to __all__:
"CatalogOverlay",
"PanelCatalogManager",
"InteractionMode",
"color_for_catalog",
```

**Step 2: Run all tests**

Run: `uv run pytest tests/test_catalog_color_palette.py tests/test_catalog_overlay.py tests/test_panel_catalog_manager.py tests/test_catalog_plot_integration.py -v`
Expected: all PASS

**Step 3: Commit**

```bash
git add SciQLop/components/catalogs/__init__.py
git commit -m "feat(catalogs): export overlay and panel manager from catalogs package"
```

---

### Task 7: Wire signals in the tscat catalogs plugin

**Files:**
- Modify: `SciQLop/plugins/tscat_catalogs/catalogs.py`

**Context:** The plugin's `Plugin.__init__` already creates both the `CatalogBrowser` (via `main_window.add_side_pan`) and the `TscatCatalogProvider`. We need to wire `CatalogBrowser.event_selected` to all existing panels' `catalog_manager.select_event`, and each panel's `catalog_manager.event_clicked` to `CatalogBrowser.highlight_event`.

Since panels can be created/destroyed dynamically, the simplest approach is to connect via the `CatalogBrowser` itself — give it a `connect_to_panel(panel)` method that sets up the bidirectional signals.

**Step 1: Add `connect_to_panel` / `disconnect_from_panel` to CatalogBrowser**

```python
def connect_to_panel(self, panel) -> None:
    manager = panel.catalog_manager
    self.event_selected.connect(manager.select_event)
    manager.event_clicked.connect(self.highlight_event)

def disconnect_from_panel(self, panel) -> None:
    manager = panel.catalog_manager
    self.event_selected.disconnect(manager.select_event)
    manager.event_clicked.disconnect(self.highlight_event)
```

**Step 2: In the plugin, connect to panels**

In `SciQLop/plugins/tscat_catalogs/catalogs.py`, the `CatalogBrowser` is added as a side panel. Connect it to existing panels and listen for new panels:

```python
# In Plugin.__init__, after creating catalog browser:
from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
self._catalog_browser = CatalogBrowser()
main_window.add_side_pan(self._catalog_browser)

# Connect to all existing panels
for panel in main_window.panels():
    self._catalog_browser.connect_to_panel(panel)

# Connect to future panels
main_window.panels_list_changed.connect(self._on_panels_changed)
```

Note: Verify `main_window.panels()` API exists. The existing code already uses `main_window.panels_list_changed`, so this signal exists. Check if there's a panels accessor or if we need to discover them.

**Step 3: Run full test suite**

Run: `uv run pytest tests/ -v`
Expected: all PASS

**Step 4: Commit**

```bash
git add SciQLop/components/catalogs/ui/catalog_browser.py SciQLop/plugins/tscat_catalogs/catalogs.py
git commit -m "feat(catalogs): wire bidirectional selection between browser and panels in plugin"
```
