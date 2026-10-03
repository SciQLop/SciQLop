"""A catalog can drive Jump mode on a panel without drawing its spans."""
from .fixtures import *  # noqa: F401, F403

from datetime import datetime, timedelta, timezone

import pytest

BASE = datetime(2020, 1, 1, tzinfo=timezone.utc)


@pytest.fixture
def panel_and_catalog(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("hidden-spans-panel")
    panel.time_range = TimeRange(BASE.timestamp(), (BASE + timedelta(days=200)).timestamp())
    provider = DummyProvider(num_catalogs=1, events_per_catalog=3)
    yield panel, provider, provider.catalogs()[0]
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    CatalogRegistry.instance().unregister(provider)


def _visible(overlay):
    return [span.visible for span in overlay._span_collection.spans()]


# A hidden overlay draws no span at all rather than invisible ones: SciQLopPlots
# re-shows any span scrolled into view (MultiPlotsVSpanCollection::updateVisibleSpans).
def test_hiding_spans_removes_existing_and_later_spans(panel_and_catalog):
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    panel, provider, catalog = panel_and_catalog
    panel.catalog_manager.add_catalog(catalog)
    overlay = panel.catalog_manager.overlay(catalog.uuid)

    overlay.spans_visible = False
    provider.add_event(catalog, CatalogEvent(uuid="late", start=BASE + timedelta(days=50),
                                             stop=BASE + timedelta(days=50, hours=1)))

    assert overlay.span_count == 0
    overlay.spans_visible = True
    assert _visible(overlay) == [True] * 4


def test_catalog_attached_without_spans_still_jumps(panel_and_catalog):
    from SciQLop.components.catalogs.backend.panel_manager import InteractionMode
    panel, provider, catalog = panel_and_catalog
    manager = panel.catalog_manager
    manager.add_catalog(catalog, show_spans=False)
    manager.mode = InteractionMode.JUMP
    event = provider.events(catalog)[2]

    manager.select_event(event)

    assert manager.overlay(catalog.uuid).span_count == 0
    assert panel.time_range.start() < event.start.timestamp() < event.stop.timestamp() < panel.time_range.stop()
    assert panel.time_range.stop() - panel.time_range.start() < 86400


def test_loaded_catalog_menu_toggles_spans(panel_and_catalog):
    from PySide6.QtWidgets import QMenu
    panel, provider, catalog = panel_and_catalog
    manager = panel.catalog_manager
    manager.add_catalog(catalog)
    menu = QMenu()
    manager.build_catalogs_menu(menu)

    loaded = menu.findChild(QMenu, f"loaded_catalog_{catalog.uuid}")
    (show_spans,) = [a for a in loaded.actions() if a.text() == "Show spans"]
    assert show_spans.isCheckable() and show_spans.isChecked()
    show_spans.trigger()

    assert manager.overlay(catalog.uuid).span_count == 0


def test_user_api_attaches_a_catalog_without_spans(panel_and_catalog):
    from SciQLop.user_api.catalogs import add_catalog_overlay
    from SciQLop.user_api.plot import PlotPanel
    panel, provider, catalog = panel_and_catalog
    path = f"{provider.name}//{catalog.name}"

    handle = add_catalog_overlay(PlotPanel(panel), path, show_spans=False)

    overlay = panel.catalog_manager.overlay(catalog.uuid)
    assert handle.show_spans is False and overlay.span_count == 0
    handle.show_spans = True
    assert handle.show_spans is True and _visible(overlay) == [True] * 3
