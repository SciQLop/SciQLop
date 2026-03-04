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


def test_overlay_reacts_to_add_event(qtbot, qapp):
    from SciQLop.components.catalogs.backend.overlay import CatalogOverlay
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())

    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    catalog = provider.catalogs()[0]

    overlay = CatalogOverlay(catalog=catalog, panel=panel)
    assert overlay.span_count == 3

    new_event = CatalogEvent(
        uuid="overlay-new-1",
        start=base + timedelta(days=50),
        stop=base + timedelta(days=50, hours=1),
    )
    provider.add_event(catalog, new_event)
    assert overlay.span_count == 4


def test_overlay_reacts_to_remove_event(qtbot, qapp):
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

    event_to_remove = provider.events(catalog)[2]
    provider.remove_event(catalog, event_to_remove)
    assert overlay.span_count == 4


def test_overlay_eager_for_small_catalogs(qtbot, qapp):
    """Catalogs with < 5000 events load all events eagerly."""
    from SciQLop.components.catalogs.backend.overlay import CatalogOverlay
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())

    provider = DummyProvider(num_catalogs=1, events_per_catalog=100)
    catalog = provider.catalogs()[0]

    overlay = CatalogOverlay(catalog=catalog, panel=panel)
    assert overlay.span_count == 100
    assert overlay._lazy is False


def test_overlay_lazy_flag_set_for_large_catalogs(qtbot, qapp):
    """Catalogs with >= 5000 events should set _lazy = True."""
    from SciQLop.components.catalogs.backend.overlay import CatalogOverlay
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("test-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    # Panel shows first 200 days; catalog has 5000 events (one per day)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())

    provider = DummyProvider(num_catalogs=1, events_per_catalog=5000)
    catalog = provider.catalogs()[0]

    overlay = CatalogOverlay(catalog=catalog, panel=panel)
    assert overlay._lazy is True
    # Should only have loaded events visible in the panel range (with margin),
    # not all 5000
    assert overlay.span_count < 5000
