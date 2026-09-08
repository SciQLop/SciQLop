"""Clicking a span on the plot must reveal that event in the catalog list,
switching the tree to the event's catalog if another one is open, and must
not feed back into a jump (2026-09-08).
"""
from .fixtures import *
import pytest
from datetime import datetime, timezone, timedelta


@pytest.fixture
def scene(qtbot, qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR", str(tmp_path))
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange
    provider = DummyProvider(num_catalogs=2, events_per_catalog=3, name="HighlightProv")
    cat_a, cat_b = provider.catalogs()
    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel = TimeSyncPanel("highlight-panel",
                          time_range=TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp()))
    qtbot.addWidget(panel)
    browser.connect_to_panel(panel)
    panel.catalog_manager.add_catalog(cat_a)
    panel.catalog_manager.add_catalog(cat_b)
    return browser, panel, provider, cat_a, cat_b


def _open_in_browser(browser, catalog):
    node = browser._tree_model._find_node_by_uuid(browser._tree_model._root, catalog.uuid)
    src = browser._tree_model.createIndex(node.row(), 0, node)
    browser._catalog_tree.setCurrentIndex(browser._proxy_model.mapFromSource(src))
    assert browser._current_catalog is catalog


def _selected_event(browser):
    idx = browser._event_table.selectionModel().currentIndex()
    if not idx.isValid():
        return None
    return browser._event_model.event_at(browser._sort_proxy.mapToSource(idx).row())


def test_manager_reports_the_clicked_events_catalog(scene):
    browser, panel, provider, cat_a, cat_b = scene
    got = []
    panel.catalog_manager.catalog_event_clicked.connect(lambda c, e: got.append((c, e)))
    event = provider.events(cat_b)[1]

    panel.catalog_manager.overlay(cat_b.uuid).event_clicked.emit(event)

    assert got == [(cat_b, event)]


def test_plot_click_highlights_the_row_of_the_open_catalog(scene):
    browser, panel, provider, cat_a, cat_b = scene
    _open_in_browser(browser, cat_a)
    event = provider.events(cat_a)[2]

    panel.catalog_manager.overlay(cat_a.uuid).event_clicked.emit(event)

    assert _selected_event(browser).uuid == event.uuid


def test_plot_click_switches_the_browser_to_the_events_catalog(scene):
    browser, panel, provider, cat_a, cat_b = scene
    _open_in_browser(browser, cat_a)
    event = provider.events(cat_b)[0]

    panel.catalog_manager.overlay(cat_b.uuid).event_clicked.emit(event)

    assert browser._current_catalog is cat_b
    assert _selected_event(browser).uuid == event.uuid


def test_plot_click_does_not_feed_back_into_a_jump(scene):
    from SciQLop.components.catalogs.backend.panel_manager import InteractionMode
    browser, panel, provider, cat_a, cat_b = scene
    _open_in_browser(browser, cat_a)
    panel.catalog_manager.mode = InteractionMode.JUMP
    before = panel.time_range
    event = provider.events(cat_a)[1]

    panel.catalog_manager.overlay(cat_a.uuid).event_clicked.emit(event)

    tr = panel.time_range
    assert abs(tr.start() - before.start()) < 1.0 and abs(tr.stop() - before.stop()) < 1.0
    assert _selected_event(browser).uuid == event.uuid


def test_picking_in_the_list_still_jumps(scene):
    from SciQLop.components.catalogs.backend.panel_manager import InteractionMode
    browser, panel, provider, cat_a, cat_b = scene
    _open_in_browser(browser, cat_a)
    panel.catalog_manager.mode = InteractionMode.JUMP
    event = provider.events(cat_a)[1]

    row = browser._event_model.row_for_event(event)
    proxy = browser._sort_proxy.mapFromSource(browser._event_model.index(row, 0))
    browser._event_table.setCurrentIndex(proxy)

    tr = panel.time_range
    duration = event.stop.timestamp() - event.start.timestamp()
    assert abs((tr.stop() - tr.start()) - 2.0 * duration) < 1.0
