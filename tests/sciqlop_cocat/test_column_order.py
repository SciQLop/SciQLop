"""A cocat-rs catalogue keeps its file's column order (Catalogue.columns, filled by the AMDA relay):
the event table shows its columns in that order, not sorted ("Col 10" before "Col 2")."""
from PySide6.QtCore import Qt

from SciQLop.components.catalogs import CatalogEvent

from ..helpers import windows_shown_while
from .conftest import HOUR, T0

COLUMNS = [f"Col {i}" for i in range(1, 13)]


def _amda_like(provider, room):
    catalog = provider.create_catalog("amda", ["r"])
    room.catalogue(catalog.uuid).columns = ["Start Time", "Stop Time", *COLUMNS]
    for k in range(3):
        provider.add_event(catalog, CatalogEvent(uuid=f"e{k}", start=T0 + k * HOUR, stop=T0 + (k + 1) * HOUR,
                                                 meta={c: f"{k}.{i}" for i, c in enumerate(COLUMNS, 1)}))
    return catalog


def _headers(view):
    model = view.model()
    return [model.headerData(c, Qt.Orientation.Horizontal) for c in range(model.columnCount())]


def test_a_catalogue_s_columns_are_its_column_order(attached, room):
    c = attached.create_catalog("c", ["r"])
    room.catalogue(c.uuid).columns = ["Col 2", "Col 10", "Col 1"]
    assert attached.columns(c) == ["Col 2", "Col 10", "Col 1"]


def test_all_events_has_no_column_order(attached, tagged):
    [all_events] = [c for c in attached.catalogs() if c.uuid.startswith("all-events:")]
    assert attached.columns(all_events) == []


def test_the_browser_shows_the_catalogue_columns_in_its_order_without_a_window(attached, room, qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    catalog = _amda_like(attached, room)
    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    browser.show()
    qtbot.waitExposed(browser)
    assert windows_shown_while(qapp, lambda: attached.open_requested.emit(catalog)) == []
    assert browser._current_catalog is catalog
    assert _headers(browser._event_table)[2:] == COLUMNS
