"""Links: bookmarks in My catalogues to catalogues of other projects, shown read-only."""
import cocat_rs
import pytest

from SciQLop.components.catalogs import CatalogEvent
from SciQLop.components.catalogs.backend.provider import NodeType
from .conftest import HOUR, T0
from .test_provider_rooms import FakeSession, make_provider, opened, run  # noqa: F401

PROJECTS = [cocat_rs.ProjectInfo("a", "My catalogues", "owner", personal=True),
            cocat_rs.ProjectInfo("c", "Shared", "editor")]


@pytest.fixture
def p(make_provider):
    provider = make_provider(FakeSession(rooms=PROJECTS))
    run(provider.connect())
    return provider


def shocks_in_shared(p):
    catalog = p.create_catalog("shocks", ["c"])
    p.add_event(catalog, CatalogEvent(uuid="e1", start=T0, stop=T0 + HOUR))
    return catalog


def named(p, name):
    return next((c for c in p.catalogs() if c.name == name), None)


def link(p, catalog):
    [action] = [a for a in p.actions(catalog) if a.name == "Link into My catalogues"]
    action.callback(catalog)
    return named(p, f"{catalog.name} (from Shared)")


def test_a_catalogue_of_another_project_can_be_linked_into_my_catalogues(p):
    original = shocks_in_shared(p)
    view = link(p, original)
    assert view.path == ["a", "Linked"]
    assert [e.uuid for e in p.events(view)] == ["e1"]
    assert p.events(view)[0] is p.events(original)[0]  # one event, shown twice
    assert p.capabilities(view) == set()


def test_my_own_catalogues_and_links_offer_no_link(p):
    view = link(p, shocks_in_shared(p))
    mine = p.create_catalog("mine", ["a"])
    assert "Link into My catalogues" not in [a.name for a in p.actions(mine)]
    assert [a.name for a in p.actions(view)] == ["Unlink", "Export…"]


def test_a_link_follows_what_its_catalogue_holds(p, qtbot):
    original = shocks_in_shared(p)
    view = link(p, original)
    p.add_event(original, CatalogEvent(uuid="e2", start=T0 + HOUR, stop=T0 + 2 * HOUR))
    p.refresh_smart_catalogs()  # read in the background
    qtbot.waitUntil(lambda: sorted(e.uuid for e in p.events(view)) == ["e1", "e2"], timeout=5000)


def test_unlink_removes_only_the_link(p, opened):
    original = shocks_in_shared(p)
    view = link(p, original)
    [unlink] = [a for a in p.actions(view) if a.name == "Unlink"]
    unlink.callback(view)
    assert named(p, "shocks (from Shared)") is None and opened["a"].links() == []
    assert [e.uuid for e in p.events(original)] == ["e1"]


def test_links_are_shown_again_at_the_next_start(p, make_provider):
    link(p, shocks_in_shared(p))
    run(p.close())
    again = make_provider(FakeSession(rooms=PROJECTS))
    run(again.connect())
    view = named(again, "shocks (from Shared)")
    assert view is not None and [e.uuid for e in again.events(view)] == ["e1"]


def test_a_link_to_a_left_project_is_empty_and_says_how_to_see_it(p):
    view_name = link(p, shocks_in_shared(p)).name
    p._choose_to_leave("c")
    view = named(p, view_name)
    assert p.events(view) == []
    assert "Join Shared" in p.node_tooltip(NodeType.CATALOG, catalog=view)


def test_a_link_to_a_project_i_am_not_in_says_so(p, make_provider):
    link(p, shocks_in_shared(p))
    run(p.close())
    alone = make_provider(FakeSession(rooms=PROJECTS[:1]))
    run(alone.connect())
    view = named(alone, "shocks (from Shared)")
    assert alone.events(view) == []
    assert "not a member of Shared" in alone.node_tooltip(NodeType.CATALOG, catalog=view)


def test_a_link_tooltip_says_where_it_comes_from(p):
    view = link(p, shocks_in_shared(p))
    text = p.node_tooltip(NodeType.CATALOG, catalog=view)
    assert "Linked from" in text and "Shared" in text and "edit it there" in text
    assert text.startswith(f"<b>{view.name}</b>")


def test_linking_twice_is_reported(p):
    original = shocks_in_shared(p)
    link(p, original)
    errors = []
    p.error_occurred.connect(errors.append)
    [action] = [a for a in p.actions(original) if a.name == "Link into My catalogues"]
    action.callback(original)
    assert errors and "already linked" in errors[0]


def test_a_link_made_elsewhere_shows_after_the_next_remote_changes(p, opened):
    from SciQLop.plugins.sciqlop_cocat.remote import RoomListener
    original = shocks_in_shared(p)
    opened["a"].link(opened["c"].catalogue(original.uuid))  # as from the web app or another computer
    assert named(p, "shocks (from Shared)") is None
    RoomListener(p, "a").changes_done()
    assert named(p, "shocks (from Shared)") is not None


def test_a_link_whose_catalogue_arrives_later_fills_in(p):
    from SciQLop.plugins.sciqlop_cocat.remote import RoomListener
    view = link(p, shocks_in_shared(p))
    p._set_events(view, [])  # as before its catalogue reached this computer
    RoomListener(p, "c").changes_done()
    assert [e.uuid for e in p.events(named(p, "shocks (from Shared)"))] == ["e1"]
