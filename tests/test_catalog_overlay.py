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
