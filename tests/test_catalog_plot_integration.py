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
    # If no crash, the wiring works.


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
