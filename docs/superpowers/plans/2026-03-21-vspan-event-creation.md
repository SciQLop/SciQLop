# VSpan-Based Catalog Event Creation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to draw vertical spans on plots to create catalog events, with a combo box to select the target catalog.

**Architecture:** `PanelCatalogManager` orchestrates: it connects to the panel's `span_created` signal, extracts the time range from the raw span, deletes it, and calls `provider.add_event()`. The existing `CatalogOverlay` picks up the new event via `events_changed` and creates a managed span. A `_catalog_combo` on `TimeRangeBar` lets the user select the target catalog.

**Tech Stack:** PySide6, SciQLopPlots (C++ bindings), pytest/pytest-qt

**Spec:** `docs/superpowers/specs/2026-03-21-vspan-event-creation-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `SciQLop/components/plotting/ui/time_range_bar.py` | Modify | Add `_catalog_combo` QComboBox + public methods |
| `SciQLop/components/catalogs/backend/panel_manager.py` | Modify | Wire `span_created`, manage combo box state, create events |
| `tests/test_time_range_bar.py` | Create | Unit tests for catalog combo on TimeRangeBar |
| `tests/test_panel_catalog_manager.py` | Modify | Add tests for span-based event creation |

---

### Task 1: Add `_catalog_combo` to `TimeRangeBar`

**Files:**
- Modify: `SciQLop/components/plotting/ui/time_range_bar.py`
- Create: `tests/test_time_range_bar.py`

- [ ] **Step 1: Write failing tests for catalog combo**

Create `tests/test_time_range_bar.py`:

```python
from .fixtures import *
import pytest
from SciQLop.core import TimeRange


@pytest.fixture
def bar(qtbot):
    from SciQLop.components.plotting.ui.time_range_bar import TimeRangeBar
    w = TimeRangeBar()
    qtbot.addWidget(w)
    return w


def test_catalog_combo_hidden_by_default(bar):
    assert bar._catalog_combo.isVisible() is False


def test_set_catalog_choices_shows_combo(bar):
    bar.set_catalog_choices([("MyCatalog", "uuid-1")])
    assert bar._catalog_combo.isVisible() is True
    assert bar._catalog_combo.count() == 1
    assert bar._catalog_combo.currentText() == "MyCatalog"


def test_set_catalog_choices_auto_selects_first(bar):
    bar.set_catalog_choices([("Cat-A", "uuid-a"), ("Cat-B", "uuid-b")])
    assert bar.selected_catalog_uuid() == "uuid-a"


def test_selected_catalog_uuid_returns_item_data(bar):
    bar.set_catalog_choices([("Cat-A", "uuid-a"), ("Cat-B", "uuid-b")])
    bar._catalog_combo.setCurrentIndex(1)
    assert bar.selected_catalog_uuid() == "uuid-b"


def test_selected_catalog_uuid_none_when_empty(bar):
    assert bar.selected_catalog_uuid() is None


def test_clear_catalog_choices_hides_combo(bar):
    bar.set_catalog_choices([("MyCatalog", "uuid-1")])
    bar.clear_catalog_choices()
    assert bar._catalog_combo.isVisible() is False
    assert bar._catalog_combo.count() == 0
    assert bar.selected_catalog_uuid() is None


def test_catalog_choice_changed_signal(bar, qtbot):
    bar.set_catalog_choices([("Cat-A", "uuid-a"), ("Cat-B", "uuid-b")])
    with qtbot.waitSignal(bar.catalog_choice_changed, timeout=1000) as blocker:
        bar._catalog_combo.setCurrentIndex(1)
    assert blocker.args == ["uuid-b"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_time_range_bar.py -v`
Expected: FAIL — `_catalog_combo` attribute does not exist

- [ ] **Step 3: Implement `_catalog_combo` on `TimeRangeBar`**

In `SciQLop/components/plotting/ui/time_range_bar.py`:

Add a new signal to `TimeRangeBar`:
```python
catalog_choice_changed = Signal(str)  # emits uuid
```

In `__init__`, after creating `_fast_forward_btn`, add:
```python
self._catalog_combo = QComboBox(self)
self._catalog_combo.setVisible(False)
self._catalog_combo.currentIndexChanged.connect(self._on_catalog_choice_changed)
```

In the layout, insert `self._catalog_combo` after `self._fast_forward_btn` and before `layout.addStretch(1)` (the trailing stretch on line 61):
```python
layout.addWidget(self._catalog_combo)
```

Add these methods to `TimeRangeBar`:
```python
def set_catalog_choices(self, items: list[tuple[str, str]]) -> None:
    self._catalog_combo.blockSignals(True)
    self._catalog_combo.clear()
    for name, uuid in items:
        self._catalog_combo.addItem(name, userData=uuid)
    self._catalog_combo.blockSignals(False)
    self._catalog_combo.setVisible(len(items) > 0)
    if items:
        self._on_catalog_choice_changed(0)

def clear_catalog_choices(self) -> None:
    self._catalog_combo.blockSignals(True)
    self._catalog_combo.clear()
    self._catalog_combo.blockSignals(False)
    self._catalog_combo.setVisible(False)

def selected_catalog_uuid(self) -> str | None:
    if self._catalog_combo.count() == 0:
        return None
    return self._catalog_combo.currentData()

def _on_catalog_choice_changed(self, index: int) -> None:
    uuid = self._catalog_combo.itemData(index)
    if uuid is not None:
        self.catalog_choice_changed.emit(uuid)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_time_range_bar.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add SciQLop/components/plotting/ui/time_range_bar.py tests/test_time_range_bar.py
git commit -m "feat: add catalog target combo box to TimeRangeBar"
```

---

### Task 2: Wire `PanelCatalogManager` to create events from spans

**Files:**
- Modify: `SciQLop/components/catalogs/backend/panel_manager.py`
- Modify: `tests/test_panel_catalog_manager.py`

- [ ] **Step 1: Write failing tests for span-based event creation**

Append to `tests/test_panel_catalog_manager.py`. Note: `_on_span_created` expects a span-like object with `.range` (returning a `TimeRange`) and `.deleteLater()`. Tests use a `FakeSpan` stub:

```python
class FakeSpan:
    """Stub for MultiPlotsVerticalSpan — provides .range and .deleteLater()."""
    def __init__(self, tr):
        self._range = tr

    @property
    def range(self):
        return self._range

    def deleteLater(self):
        pass


def test_edit_mode_updates_catalog_combo(qtbot, qapp):
    from SciQLop.components.catalogs.backend.panel_manager import (
        PanelCatalogManager, InteractionMode,
    )
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.components.plotting.ui.panel_container import PanelContainer
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    container = PanelContainer(panel)
    qtbot.addWidget(container)
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())

    provider = DummyProvider(num_catalogs=2, events_per_catalog=3)
    cats = provider.catalogs()

    manager = panel.catalog_manager
    manager.add_catalog(cats[0])
    manager.add_catalog(cats[1])
    manager.mode = InteractionMode.EDIT

    bar = panel._time_range_bar
    assert bar._catalog_combo.isVisible() is True
    assert bar._catalog_combo.count() == 2


def test_view_mode_hides_catalog_combo(qtbot, qapp):
    from SciQLop.components.catalogs.backend.panel_manager import (
        PanelCatalogManager, InteractionMode,
    )
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.components.plotting.ui.panel_container import PanelContainer
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    container = PanelContainer(panel)
    qtbot.addWidget(container)
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]

    manager = panel.catalog_manager
    manager.add_catalog(cat)
    manager.mode = InteractionMode.EDIT
    assert panel._time_range_bar._catalog_combo.isVisible() is True

    manager.mode = InteractionMode.VIEW
    assert panel._time_range_bar._catalog_combo.isVisible() is False


def test_span_created_adds_event_to_target_catalog(qtbot, qapp):
    from SciQLop.components.catalogs.backend.panel_manager import (
        PanelCatalogManager, InteractionMode,
    )
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.components.plotting.ui.panel_container import PanelContainer
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    container = PanelContainer(panel)
    qtbot.addWidget(container)
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0)
    cat = provider.catalogs()[0]

    manager = panel.catalog_manager
    manager.add_catalog(cat)
    manager.mode = InteractionMode.EDIT

    initial_count = len(provider.events(cat))

    start_ts = base.timestamp() + 86400 * 50
    stop_ts = start_ts + 3600
    manager._on_span_created(FakeSpan(TimeRange(start_ts, stop_ts)))

    events = provider.events(cat)
    assert len(events) == initial_count + 1
    new_event = events[0]
    assert abs(new_event.start.timestamp() - start_ts) < 1.0
    assert abs(new_event.stop.timestamp() - stop_ts) < 1.0


def test_span_created_ignored_when_not_in_edit_mode(qtbot, qapp):
    from SciQLop.components.catalogs.backend.panel_manager import (
        PanelCatalogManager, InteractionMode,
    )
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.components.plotting.ui.panel_container import PanelContainer
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    container = PanelContainer(panel)
    qtbot.addWidget(container)
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0)
    cat = provider.catalogs()[0]

    manager = panel.catalog_manager
    manager.add_catalog(cat)
    # Stay in VIEW mode

    start_ts = base.timestamp() + 86400 * 50
    manager._on_span_created(FakeSpan(TimeRange(start_ts, start_ts + 3600)))

    assert len(provider.events(cat)) == 0


def test_edit_mode_enables_span_creation_on_panel(qtbot, qapp):
    from SciQLop.components.catalogs.backend.panel_manager import (
        PanelCatalogManager, InteractionMode,
    )
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.components.plotting.ui.panel_container import PanelContainer
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    container = PanelContainer(panel)
    qtbot.addWidget(container)
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0)
    cat = provider.catalogs()[0]

    manager = panel.catalog_manager
    manager.add_catalog(cat)

    assert panel.span_creation_enabled() is False
    manager.mode = InteractionMode.EDIT
    assert panel.span_creation_enabled() is True
    manager.mode = InteractionMode.VIEW
    assert panel.span_creation_enabled() is False


def test_removing_catalog_updates_combo(qtbot, qapp):
    from SciQLop.components.catalogs.backend.panel_manager import (
        PanelCatalogManager, InteractionMode,
    )
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.components.plotting.ui.panel_container import PanelContainer
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    container = PanelContainer(panel)
    qtbot.addWidget(container)
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())

    provider = DummyProvider(num_catalogs=2, events_per_catalog=0)
    cats = provider.catalogs()

    manager = panel.catalog_manager
    manager.add_catalog(cats[0])
    manager.add_catalog(cats[1])
    manager.mode = InteractionMode.EDIT

    bar = panel._time_range_bar
    assert bar._catalog_combo.count() == 2

    manager.remove_catalog(cats[0])
    assert bar._catalog_combo.count() == 1

    manager.remove_catalog(cats[1])
    assert bar._catalog_combo.count() == 0
    assert panel.span_creation_enabled() is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_panel_catalog_manager.py::test_edit_mode_updates_catalog_combo tests/test_panel_catalog_manager.py::test_span_created_adds_event_to_target_catalog tests/test_panel_catalog_manager.py::test_span_created_ignored_when_not_in_edit_mode tests/test_panel_catalog_manager.py::test_edit_mode_enables_span_creation_on_panel tests/test_panel_catalog_manager.py::test_view_mode_hides_catalog_combo tests/test_panel_catalog_manager.py::test_removing_catalog_updates_combo -v`
Expected: FAIL — methods don't exist yet

- [ ] **Step 3: Implement span creation wiring in `PanelCatalogManager`**

In `SciQLop/components/catalogs/backend/panel_manager.py`, add imports at top:

```python
from uuid import uuid4
from datetime import datetime, timezone
from SciQLop.components.catalogs.backend.color_palette import color_for_catalog
```

Modify `__init__`:

```python
def __init__(self, panel, parent: QObject | None = None):
    super().__init__(parent or panel)
    self._panel = panel
    self._overlays: dict[str, CatalogOverlay] = {}
    self._mode = InteractionMode.VIEW
    self._bar_connected = False
    self._panel.span_created.connect(self._on_span_created)
```

Modify `mode.setter`:

```python
@mode.setter
def mode(self, value: InteractionMode) -> None:
    self._mode = value
    for uuid, overlay in self._overlays.items():
        if value == InteractionMode.EDIT:
            caps = overlay.catalog.provider.capabilities(overlay.catalog)
            overlay.read_only = Capability.EDIT_EVENTS not in caps
        else:
            overlay.read_only = True
    self._update_creation_target_choices()
    self._apply_span_creation_state()
```

Modify `add_catalog` — add `self._update_creation_target_choices()` and `self._apply_span_creation_state()` at the end:

```python
def add_catalog(self, catalog: Catalog) -> None:
    if catalog.uuid in self._overlays:
        return
    overlay = CatalogOverlay(catalog=catalog, panel=self._panel, parent=self)
    overlay.event_clicked.connect(self._on_event_clicked)
    self._overlays[catalog.uuid] = overlay
    if self._mode == InteractionMode.EDIT:
        caps = catalog.provider.capabilities(catalog)
        overlay.read_only = Capability.EDIT_EVENTS not in caps
    else:
        overlay.read_only = True
    self._update_creation_target_choices()
    self._apply_span_creation_state()
```

Modify `remove_catalog` — add same calls at the end:

```python
def remove_catalog(self, catalog: Catalog) -> None:
    overlay = self._overlays.pop(catalog.uuid, None)
    if overlay is not None:
        overlay.clear()
        overlay.deleteLater()
    self._update_creation_target_choices()
    self._apply_span_creation_state()
```

Add new private methods:

```python
def _editable_catalogs(self) -> list[Catalog]:
    result = []
    for overlay in self._overlays.values():
        cat = overlay.catalog
        caps = cat.provider.capabilities(cat)
        if Capability.CREATE_EVENTS in caps:
            result.append(cat)
    return result

def _time_range_bar(self):
    bar = getattr(self._panel, '_time_range_bar', None)
    if bar is not None and not self._bar_connected:
        bar.catalog_choice_changed.connect(lambda _: self._apply_span_creation_state())
        self._bar_connected = True
    return bar

def _update_creation_target_choices(self) -> None:
    bar = self._time_range_bar()
    if bar is None:
        return
    if self._mode != InteractionMode.EDIT:
        bar.clear_catalog_choices()
        return
    editable = self._editable_catalogs()
    bar.set_catalog_choices([(c.name, c.uuid) for c in editable])

def _apply_span_creation_state(self) -> None:
    bar = self._time_range_bar()
    if bar is None:
        return
    uuid = bar.selected_catalog_uuid()
    enabled = self._mode == InteractionMode.EDIT and uuid is not None
    self._panel.set_span_creation_enabled(enabled)
    if enabled:
        self._panel.set_span_creation_color(color_for_catalog(uuid))

def _on_span_created(self, raw_span) -> None:
    bar = self._time_range_bar()
    if self._mode != InteractionMode.EDIT or bar is None:
        raw_span.deleteLater()
        return
    target_uuid = bar.selected_catalog_uuid()
    if target_uuid is None:
        raw_span.deleteLater()
        return
    tr = raw_span.range
    raw_span.deleteLater()
    overlay = self._overlays.get(target_uuid)
    if overlay is None:
        return
    cat = overlay.catalog
    start = datetime.fromtimestamp(tr.start(), tz=timezone.utc)
    stop = datetime.fromtimestamp(tr.stop(), tz=timezone.utc)
    event = CatalogEvent(uuid=str(uuid4()), start=start, stop=stop)
    cat.provider.add_event(cat, event)
```

- [ ] **Step 4: Run new tests to verify they pass**

Run: `uv run pytest tests/test_panel_catalog_manager.py -v`
Expected: all PASS (both old and new tests)

- [ ] **Step 5: Run the full test suite**

Run: `uv run pytest tests/test_time_range_bar.py tests/test_panel_catalog_manager.py tests/test_panel_container.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add SciQLop/components/catalogs/backend/panel_manager.py tests/test_panel_catalog_manager.py
git commit -m "feat: create catalog events by drawing spans on plots

Wire PanelCatalogManager to panel.span_created signal. In EDIT mode,
drawing a vspan creates a CatalogEvent in the selected target catalog.
Target catalog is chosen via _catalog_combo on the TimeRangeBar."
```

---

### Task 3: Final integration verification

- [ ] **Step 1: Run all catalog-related tests together**

Run: `uv run pytest tests/test_time_range_bar.py tests/test_panel_catalog_manager.py tests/test_panel_container.py tests/test_catalog_overlay.py tests/test_catalog_provider.py tests/test_catalog_dirty_state.py -v`
Expected: all PASS

- [ ] **Step 2: Run the full test suite**

Run: `uv run pytest -v`
Expected: no new failures (pre-existing failures documented in backlog are acceptable)
