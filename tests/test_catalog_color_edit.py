"""User-editable per-catalog color (2026-09-07): the tree swatch showed the
hash-assigned color but there was no way to change it. The override is UI
state (like column visibility), stored outside the catalog so read-only
providers (speasy) get it too, and propagated live to the tree and to every
panel overlay through a module-level signal.
"""
from .fixtures import *
import pytest
from datetime import datetime, timezone, timedelta

from PySide6.QtGui import QColor


@pytest.fixture
def palette(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR", str(tmp_path))
    from SciQLop.components.catalogs.backend import color_palette
    monkeypatch.setattr(color_palette, "_overrides", None)
    return color_palette


def _rgb(c: QColor) -> tuple:
    return (c.red(), c.green(), c.blue())


def test_set_catalog_color_overrides_hash_color_keeping_span_alpha(qapp, palette):
    palette.set_catalog_color("uuid-x", QColor(10, 20, 30))
    color = palette.color_for_catalog("uuid-x")
    assert _rgb(color) == (10, 20, 30)
    assert color.alpha() == palette._PALETTE[0].alpha()
    assert palette.has_custom_color("uuid-x")


def test_custom_color_persists_across_reload(qapp, palette):
    palette.set_catalog_color("uuid-y", QColor("#112233"))
    palette._overrides = None
    assert _rgb(palette.color_for_catalog("uuid-y")) == (0x11, 0x22, 0x33)


def test_reset_restores_hash_color(qapp, palette):
    default = _rgb(palette.color_for_catalog("uuid-z"))
    palette.set_catalog_color("uuid-z", QColor("#ff0000"))
    palette.set_catalog_color("uuid-z", None)
    assert _rgb(palette.color_for_catalog("uuid-z")) == default
    assert not palette.has_custom_color("uuid-z")


def test_set_catalog_color_emits_changed(qapp, palette, qtbot):
    with qtbot.waitSignal(palette.catalog_color_changed, timeout=1000) as blocker:
        palette.set_catalog_color("uuid-s", QColor("#abcdef"))
    assert blocker.args == ["uuid-s"]


def test_swatch_icon_follows_custom_color(qapp, palette):
    from PySide6.QtCore import QSize
    palette.set_catalog_color("uuid-w", QColor("#336699"))
    center = palette.catalog_swatch_icon("uuid-w").pixmap(QSize(16, 16)).toImage().pixelColor(8, 8)
    assert _rgb(center) == (0x33, 0x66, 0x99)


def _tree_index(model, catalog):
    from PySide6.QtCore import QModelIndex
    for row in range(model.rowCount(QModelIndex())):
        prov_idx = model.index(row, 0, QModelIndex())
        if model.node_from_index(prov_idx).provider is catalog.provider:
            for crow in range(model.rowCount(prov_idx)):
                cat_idx = model.index(crow, 0, prov_idx)
                if model.node_from_index(cat_idx).catalog is catalog:
                    return cat_idx
    raise AssertionError("catalog node not found")


def test_tree_repaints_catalog_row_on_color_change(qtbot, qapp, palette):
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    provider = DummyProvider(num_catalogs=1, name="ColorEditTree")
    cat = provider.catalogs()[0]
    model = CatalogTreeModel()
    cat_idx = _tree_index(model, cat)

    with qtbot.waitSignal(model.dataChanged, timeout=1000) as blocker:
        palette.set_catalog_color(cat.uuid, QColor("#445566"))
    assert blocker.args[0] == cat_idx


def test_panel_overlay_recolors_live(qtbot, qapp, palette):
    from SciQLop.components.catalogs.backend.panel_manager import PanelCatalogManager
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange

    panel = TimeSyncPanel("color-edit-panel")
    base = datetime(2020, 1, 1, tzinfo=timezone.utc)
    panel.time_range = TimeRange(base.timestamp(), (base + timedelta(days=200)).timestamp())
    provider = DummyProvider(num_catalogs=1, events_per_catalog=3, name="ColorEditPanel")
    cat = provider.catalogs()[0]
    manager = PanelCatalogManager(panel)
    manager.add_catalog(cat)

    palette.set_catalog_color(cat.uuid, QColor("#778899"))

    assert _rgb(QColor(manager.overlay(cat.uuid).color)) == (0x77, 0x88, 0x99)


def _action_texts(menu) -> list[str]:
    return [a.text() for a in menu.actions()]


def test_tree_context_menu_offers_set_color_and_reset_only_when_custom(qtbot, qapp, palette):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser

    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, name="ColorEditMenu")
    cat = provider.catalogs()[0]
    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    proxy_idx = browser._proxy_model.mapFromSource(_tree_index(browser._tree_model, cat))

    texts = _action_texts(browser._build_tree_context_menu(proxy_idx))
    assert "Set color..." in texts
    assert "Reset color" not in texts

    palette.set_catalog_color(cat.uuid, QColor("#010203"))
    texts = _action_texts(browser._build_tree_context_menu(proxy_idx))
    assert "Reset color" in texts
