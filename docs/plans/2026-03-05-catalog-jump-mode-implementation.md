# Catalog Browser Jump Mode Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** When an event is selected in the catalog browser's event table, panels in JUMP mode adjust their time range to center on that event (event = 10% of visible range).

**Architecture:** Add jump logic to `PanelCatalogManager.select_event`. No new UI, no new wiring — the existing `event_selected` signal already calls `select_event` on connected panels.

**Tech Stack:** PySide6, SciQLopPlots (TimeRange)

---

### Task 1: Write failing test for jump-on-select

**Files:**
- Modify: `tests/test_panel_catalog_manager.py`

**Step 1: Write the failing test**

Add to end of `tests/test_panel_catalog_manager.py`:

```python
def test_manager_jump_mode_sets_time_range_on_select(qtbot, qapp):
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
    manager.mode = InteractionMode.JUMP

    event = provider.events(cat)[0]
    event_duration = event.stop.timestamp() - event.start.timestamp()
    margin = event_duration * 4.5

    manager.select_event(event)

    tr = panel.time_range
    assert abs(tr.start - (event.start.timestamp() - margin)) < 1.0
    assert abs(tr.stop - (event.stop.timestamp() + margin)) < 1.0
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_panel_catalog_manager.py::test_manager_jump_mode_sets_time_range_on_select -v`
Expected: FAIL — time range is unchanged because `select_event` doesn't jump yet.

---

### Task 2: Implement jump logic in select_event

**Files:**
- Modify: `SciQLop/components/catalogs/backend/panel_manager.py:74-76`

**Step 1: Replace the `select_event` method body**

In `panel_manager.py`, replace the `select_event` method (lines 74-76) with:

```python
    def select_event(self, event: CatalogEvent) -> None:
        for overlay in self._overlays.values():
            overlay.select_event(event)
        if self._mode == InteractionMode.JUMP:
            from SciQLop.core import TimeRange
            duration = event.stop.timestamp() - event.start.timestamp()
            if duration <= 0:
                margin = 3600.0  # 1 hour fallback for zero-duration events
            else:
                margin = duration * 4.5
            tr = TimeRange(
                event.start.timestamp() - margin,
                event.stop.timestamp() + margin,
            )
            self._panel.time_range = tr
```

**Step 2: Run test to verify it passes**

Run: `uv run pytest tests/test_panel_catalog_manager.py::test_manager_jump_mode_sets_time_range_on_select -v`
Expected: PASS

---

### Task 3: Add test for zero-duration event fallback

**Files:**
- Modify: `tests/test_panel_catalog_manager.py`

**Step 1: Write the test**

```python
def test_manager_jump_mode_zero_duration_event(qtbot, qapp):
    from SciQLop.components.catalogs.backend.panel_manager import (
        PanelCatalogManager, InteractionMode,
    )
    from SciQLop.components.catalogs.backend.provider import Catalog, CatalogEvent
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())

    provider = DummyProvider(num_catalogs=1, events_per_catalog=1)
    cat = provider.catalogs()[0]

    manager = PanelCatalogManager(panel)
    manager.add_catalog(cat)
    manager.mode = InteractionMode.JUMP

    # Create a zero-duration event
    t = datetime(2020, 6, 15, 12, 0, tzinfo=timezone.utc)
    zero_event = CatalogEvent(uuid="zero-dur", start=t, stop=t)

    manager.select_event(zero_event)

    tr = panel.time_range
    assert abs(tr.start - (t.timestamp() - 3600)) < 1.0
    assert abs(tr.stop - (t.timestamp() + 3600)) < 1.0
```

**Step 2: Run test**

Run: `uv run pytest tests/test_panel_catalog_manager.py::test_manager_jump_mode_zero_duration_event -v`
Expected: PASS (already handled by the implementation)

---

### Task 4: Add test that VIEW mode does NOT jump

**Files:**
- Modify: `tests/test_panel_catalog_manager.py`

**Step 1: Write the test**

```python
def test_manager_view_mode_does_not_jump(qtbot, qapp):
    from SciQLop.components.catalogs.backend.panel_manager import (
        PanelCatalogManager, InteractionMode,
    )
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    original_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())
    panel.time_range = original_range

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    cat = provider.catalogs()[0]

    manager = PanelCatalogManager(panel)
    manager.add_catalog(cat)
    assert manager.mode == InteractionMode.VIEW  # default

    event = provider.events(cat)[0]
    manager.select_event(event)

    tr = panel.time_range
    assert abs(tr.start - original_range.start) < 1.0
    assert abs(tr.stop - original_range.stop) < 1.0
```

**Step 2: Run test**

Run: `uv run pytest tests/test_panel_catalog_manager.py::test_manager_view_mode_does_not_jump -v`
Expected: PASS

---

### Task 5: Run full test suite and commit

**Step 1: Run all catalog-related tests**

Run: `uv run pytest tests/test_panel_catalog_manager.py tests/test_catalog_plot_integration.py -v`
Expected: All PASS

**Step 2: Commit**

```bash
git add tests/test_panel_catalog_manager.py SciQLop/components/catalogs/backend/panel_manager.py
git commit -m "feat(catalogs): jump to event when selected in browser with panel in JUMP mode"
```
