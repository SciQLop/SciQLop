"""Double-clicking the color swatch of a catalog row opens the color picker;
double-clicking the name still renames (2026-09-08).
"""
from .fixtures import *
import pytest
from PySide6.QtCore import Qt, QModelIndex, QPoint
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QAbstractItemView


@pytest.fixture
def setup(qtbot, qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR", str(tmp_path))
    from SciQLop.components.catalogs.backend import color_palette
    monkeypatch.setattr(color_palette, "_overrides", None)
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    provider = DummyProvider(num_catalogs=1, events_per_catalog=0, name="SwatchDClick")
    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    browser.show()
    qtbot.waitExposed(browser)
    browser._catalog_tree.expandAll()
    return browser, provider.catalogs()[0]


def _catalog_proxy_index(browser, catalog):
    model = browser._tree_model
    for row in range(model.rowCount(QModelIndex())):
        prov_idx = model.index(row, 0, QModelIndex())
        if model.node_from_index(prov_idx).provider is catalog.provider:
            for crow in range(model.rowCount(prov_idx)):
                cat_idx = model.index(crow, 0, prov_idx)
                if model.node_from_index(cat_idx).catalog is catalog:
                    return browser._proxy_model.mapFromSource(cat_idx)
    raise AssertionError("catalog node not found")


def _patch_color_dialog(monkeypatch, color, calls):
    from PySide6.QtWidgets import QColorDialog

    def fake(*args, **kwargs):
        calls.append(args)
        return color
    monkeypatch.setattr(QColorDialog, "getColor", staticmethod(fake))


def test_double_click_on_swatch_opens_the_color_picker(setup, qtbot, monkeypatch):
    from SciQLop.components.catalogs.backend.color_palette import color_for_catalog
    browser, catalog = setup
    calls = []
    _patch_color_dialog(monkeypatch, QColor("#123456"), calls)
    idx = _catalog_proxy_index(browser, catalog)
    tree = browser._catalog_tree

    qtbot.mouseDClick(tree.viewport(), Qt.MouseButton.LeftButton,
                      pos=browser._swatch_rect(idx).center())

    assert len(calls) == 1
    c = color_for_catalog(catalog.uuid)
    assert (c.red(), c.green(), c.blue()) == (0x12, 0x34, 0x56)
    assert tree.state() != QAbstractItemView.State.EditingState


def test_double_click_on_name_renames_instead(setup, qtbot, monkeypatch):
    browser, catalog = setup
    calls = []
    _patch_color_dialog(monkeypatch, QColor("#123456"), calls)
    idx = _catalog_proxy_index(browser, catalog)
    tree = browser._catalog_tree
    rect = tree.visualRect(idx)
    name_pos = QPoint(rect.right() - 4, rect.center().y())
    assert not browser._swatch_rect(idx).contains(name_pos)

    qtbot.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=name_pos)
    qtbot.mouseDClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=name_pos)

    assert calls == []
    assert tree.state() == QAbstractItemView.State.EditingState
