"""SciQLop's 'Edit attributes…' popup (the plot panel's span menu) on cocat-rs catalogues."""
import cocat_rs
import pytest
from PySide6.QtCore import Qt

from SciQLop.components.catalogs import CatalogEvent
from .conftest import HOUR, T0
from .test_provider_rooms import FakeSession, make_provider, opened, run  # noqa: F401

event_menu = pytest.importorskip("SciQLop.components.catalogs.ui.event_menu")
START_TITLE = getattr(pytest.importorskip("SciQLop.components.catalogs.ui.event_table"),
                      "_FIXED_COLUMN_TITLES", ("start",))[0]  # "Start (UTC)" since SciQLop 6c23dbd08

PROJECTS = [cocat_rs.ProjectInfo("a", "Mine", "owner", personal=True),
            cocat_rs.ProjectInfo("b", "Team", "viewer")]


@pytest.fixture
def provider(make_provider):
    p = make_provider(FakeSession(rooms=PROJECTS))
    run(p.connect())
    return p


def popup_for(qtbot, catalog, event):
    popup = event_menu.EventAttributesPopup(catalog, event)
    qtbot.addWidget(popup)
    return popup


def row(popup, name):
    model = popup.view.model()
    return model.index(next(r for r in range(model.rowCount())
                            if model.headerData(r, Qt.Orientation.Vertical, Qt.ItemDataRole.DisplayRole) == name), 0)


def an_event(p, project):
    catalog = p.create_catalog("shocks", [project])
    p.add_event(catalog, CatalogEvent(uuid="e1", start=T0, stop=T0 + HOUR, meta={"label": "shock", "tags": ["s"]}))
    return catalog, p.events(catalog)[0]


def test_an_edit_in_the_popup_is_stored_in_the_project(qtbot, provider, opened):
    catalog, event = an_event(provider, "a")
    popup = popup_for(qtbot, catalog, event)
    model = popup.view.model()
    assert model.flags(row(popup, "label")) & Qt.ItemFlag.ItemIsEditable
    assert model.setData(row(popup, "label"), "bow shock", Qt.ItemDataRole.EditRole)
    assert opened["a"].event("e1").attributes["label"] == "bow shock"


def test_the_popup_is_read_only_in_a_viewer_project(qtbot, provider, opened):
    catalog, event = an_event(provider, "a")
    opened["a"].role = "viewer"  # as when an owner demotes the person
    provider.room_status_changed("a", "synced")
    popup = popup_for(qtbot, catalog, event)
    assert not popup.view.model().flags(row(popup, "label")) & Qt.ItemFlag.ItemIsEditable


def test_the_popup_is_read_only_for_a_smart_catalogue(qtbot, provider, opened):
    an_event(provider, "a")
    smart = opened["a"].create_catalogue(name="all", author="me")
    smart.rule = {"filter": {"all": True}, "where": {"contains": ["tags", "s"]}}
    provider._rewrap_room("a")
    catalog = next(c for c in provider.catalogs() if c.uuid == smart.uuid)
    [event] = provider.events(catalog)
    popup = popup_for(qtbot, catalog, event)
    assert not popup.view.model().flags(row(popup, "label")) & Qt.ItemFlag.ItemIsEditable


def test_a_new_start_in_the_popup_is_stored_in_the_project(qtbot, provider, opened):
    catalog, event = an_event(provider, "a")
    popup = popup_for(qtbot, catalog, event)
    model = popup.view.model()
    index = row(popup, START_TITLE)
    later = T0 + HOUR / 2
    assert model.setData(index, later, Qt.ItemDataRole.EditRole)
    provider.flush_ranges()  # the plugin batches range edits for 100 ms
    assert opened["a"].event("e1").range[0] == later
