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
