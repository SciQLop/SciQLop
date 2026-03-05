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


def test_panel_has_catalog_manager(qtbot, qapp):
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel

    panel = TimeSyncPanel("test-panel")
    assert hasattr(panel, 'catalog_manager')
    from SciQLop.components.catalogs.backend.panel_manager import PanelCatalogManager
    assert isinstance(panel.catalog_manager, PanelCatalogManager)


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
    assert abs(tr.start() - (event.start.timestamp() - margin)) < 1.0
    assert abs(tr.stop() - (event.stop.timestamp() + margin)) < 1.0


def test_manager_jump_mode_zero_duration_event(qtbot, qapp):
    from SciQLop.components.catalogs.backend.panel_manager import (
        PanelCatalogManager, InteractionMode,
    )
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
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
    assert abs(tr.start() - (t.timestamp() - 3600)) < 1.0
    assert abs(tr.stop() - (t.timestamp() + 3600)) < 1.0


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
    assert abs(tr.start() - original_range.start()) < 1.0
    assert abs(tr.stop() - original_range.stop()) < 1.0
