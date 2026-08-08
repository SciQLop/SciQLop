from .fixtures import *  # noqa: F401, F403

import pytest
from datetime import datetime, timezone, timedelta

from SciQLop.components.catalogs.backend.provider import (
    CatalogProvider,
    Catalog,
    CatalogEvent,
    Capability,
)
from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
from SciQLop.user_api.plot import PlotPanel
from SciQLop.user_api.catalogs import add_catalog_overlay
from SciQLop.core import TimeRange


class _TestOverlayProvider(CatalogProvider):
    """Minimal provider with one catalog for overlay API tests."""

    def __init__(self, parent=None):
        super().__init__(name="OverlayTest", parent=parent)
        self._catalog = Catalog(
            uuid="overlay-test-cat",
            name="events",
            provider=self,
            path=["room1"],
        )
        base = datetime(2024, 1, 1, tzinfo=timezone.utc)
        self._set_events(self._catalog, [
            CatalogEvent(
                uuid="evt-1",
                start=base,
                stop=base + timedelta(days=1),
                meta={"color": "#ff0000"},
            ),
        ])

    def catalogs(self):
        return [self._catalog]

    def capabilities(self, catalog=None):
        return {Capability.CREATE_EVENTS, Capability.DELETE_EVENTS}

    def create_catalog(self, name, path=None):
        raise NotImplementedError


@pytest.fixture
def overlay_provider(qtbot, qapp):
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    registry = CatalogRegistry.instance()
    provider = _TestOverlayProvider()
    yield provider
    registry.unregister(provider)


@pytest.fixture
def overlay_panel(qtbot, qapp):
    panel = TimeSyncPanel("overlay-test-panel")
    panel.time_range = TimeRange(
        datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp(),
        datetime(2024, 1, 10, tzinfo=timezone.utc).timestamp(),
    )
    yield PlotPanel(panel)


def test_add_and_remove_catalog_overlay(overlay_provider, overlay_panel):
    path = "OverlayTest//room1//events"
    overlay = overlay_panel.add_catalog_overlay(path)
    assert overlay.catalog_path == path
    overlay.remove()


def test_remove_via_helper(overlay_provider, overlay_panel):
    path = "OverlayTest//room1//events"
    overlay = add_catalog_overlay(overlay_panel, path, override_color="#00ff00")
    assert overlay.override_color == "#00ff00"
    overlay_panel.remove_catalog_overlay(overlay)
