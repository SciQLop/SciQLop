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


def test_manager_drops_overlay_when_provider_removes_catalog(qtbot, qapp):
    """When a provider emits catalog_removed (e.g. catalog deleted from the
    tree or from a collaborative backend), any panel displaying that catalog
    must drop its overlay. Regression: overlay would stay live, referencing
    a deleted catalog."""
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
    assert cat.uuid in manager.catalog_uuids

    provider.remove_catalog(cat)

    assert cat.uuid not in manager.catalog_uuids


def test_manager_syncs_with_provider_registered_after_construction(qtbot, qapp):
    """A provider registered after the PanelCatalogManager is created must
    still have its catalog_removed signal honored by the panel."""
    from SciQLop.components.catalogs.backend.panel_manager import PanelCatalogManager
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())

    manager = PanelCatalogManager(panel)

    provider = DummyProvider(num_catalogs=1, events_per_catalog=1)
    cat = provider.catalogs()[0]
    manager.add_catalog(cat)
    assert cat.uuid in manager.catalog_uuids

    provider.remove_catalog(cat)
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
    from SciQLop.components.catalogs.backend.panel_manager import InteractionMode
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.components.plotting.ui.panel_container import PanelContainer
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())
    container = PanelContainer(panel)
    qtbot.addWidget(container)

    provider = DummyProvider(num_catalogs=2, events_per_catalog=0)
    cats = provider.catalogs()

    manager = panel.catalog_manager
    manager.add_catalog(cats[0])
    manager.add_catalog(cats[1])
    manager.mode = InteractionMode.EDIT

    bar = panel._time_range_bar
    assert bar._catalog_combo.count() == 2
    assert not bar._catalog_combo.isHidden()


def test_view_mode_hides_catalog_combo(qtbot, qapp):
    from SciQLop.components.catalogs.backend.panel_manager import InteractionMode
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.components.plotting.ui.panel_container import PanelContainer
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())
    container = PanelContainer(panel)
    qtbot.addWidget(container)

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0)
    cat = provider.catalogs()[0]

    manager = panel.catalog_manager
    manager.add_catalog(cat)
    manager.mode = InteractionMode.EDIT
    manager.mode = InteractionMode.VIEW

    bar = panel._time_range_bar
    assert bar._catalog_combo.isHidden()


def test_span_created_adds_event_to_target_catalog(qtbot, qapp):
    from SciQLop.components.catalogs.backend.panel_manager import InteractionMode
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.components.plotting.ui.panel_container import PanelContainer
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())
    container = PanelContainer(panel)
    qtbot.addWidget(container)

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0)
    cat = provider.catalogs()[0]

    manager = panel.catalog_manager
    manager.add_catalog(cat)
    manager.mode = InteractionMode.EDIT

    span_start = base + timedelta(days=10)
    span_stop = base + timedelta(days=11)
    fake_tr = TimeRange(span_start.timestamp(), span_stop.timestamp())
    manager._on_span_created(FakeSpan(fake_tr))

    events = provider.events(cat)
    assert len(events) == 1
    assert abs(events[0].start.timestamp() - span_start.timestamp()) < 1.0
    assert abs(events[0].stop.timestamp() - span_stop.timestamp()) < 1.0


def test_span_created_ignored_when_not_in_edit_mode(qtbot, qapp):
    from SciQLop.components.catalogs.backend.panel_manager import InteractionMode
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.components.plotting.ui.panel_container import PanelContainer
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())
    container = PanelContainer(panel)
    qtbot.addWidget(container)

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0)
    cat = provider.catalogs()[0]

    manager = panel.catalog_manager
    manager.add_catalog(cat)
    # Stay in VIEW mode (default)

    fake_tr = TimeRange(base.timestamp(), (base + timedelta(days=1)).timestamp())
    manager._on_span_created(FakeSpan(fake_tr))

    events = provider.events(cat)
    assert len(events) == 0


def test_edit_mode_enables_span_creation_on_panel(qtbot, qapp):
    from SciQLop.components.catalogs.backend.panel_manager import InteractionMode
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.components.plotting.ui.panel_container import PanelContainer
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())
    container = PanelContainer(panel)
    qtbot.addWidget(container)

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0)
    cat = provider.catalogs()[0]

    manager = panel.catalog_manager
    manager.add_catalog(cat)

    assert not panel.span_creation_enabled()

    manager.mode = InteractionMode.EDIT
    assert panel.span_creation_enabled()

    manager.mode = InteractionMode.VIEW
    assert not panel.span_creation_enabled()


def test_removing_catalog_updates_combo(qtbot, qapp):
    from SciQLop.components.catalogs.backend.panel_manager import InteractionMode
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.components.plotting.ui.panel_container import PanelContainer
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())
    container = PanelContainer(panel)
    qtbot.addWidget(container)

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
