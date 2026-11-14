"""The SciQLop hooks the plugin uses when SciQLop has them: tooltips, capabilities_changed, notice."""
import cocat_rs
import pytest

from SciQLop.components.catalogs.backend.provider import NodeType
from SciQLop.plugins.sciqlop_cocat import provider as provider_module
from .test_provider_rooms import ROOMS, FakeSession, make_provider, opened, run  # noqa: F401


@pytest.fixture
def connected(make_provider):
    p = make_provider(FakeSession(rooms=ROOMS))
    run(p.connect())
    return p


def tip(p, node_type, path=None, catalog=None):
    return p.node_tooltip(node_type, path=path, catalog=catalog) or ""


def test_projects_say_their_role_state_and_size(connected):
    p = connected
    p.create_catalog("shocks", ["a"])
    p.room_status_changed("a", "synced")
    mine = tip(p, NodeType.FOLDER, ["a"])
    assert "your own project" in mine and "Synced" in mine and "1 catalogue" in mine
    assert "owner" in mine
    team = tip(p, NodeType.FOLDER, ["b"])
    assert "viewer" in team and "read-only" in team


def test_a_project_tip_is_formatted_and_counts_its_events_once(connected):
    import uuid
    from SciQLop.components.catalogs import CatalogEvent
    from .conftest import HOUR, T0
    p = connected
    shocks, crossings = p.create_catalog("shocks", ["a"]), p.create_catalog("crossings", ["a"])
    event = CatalogEvent(uuid=str(uuid.uuid4()), start=T0, stop=T0 + HOUR)
    p.add_event(shocks, event)
    p.add_event(crossings, CatalogEvent(uuid=event.uuid, start=T0, stop=T0 + HOUR))
    p.room_status_changed("a", "synced")
    text = tip(p, NodeType.FOLDER, ["a"])
    assert text.startswith("<") and "<b>My catalogues</b>" in text
    assert "2 catalogues" in text and "1 event" in text


def test_a_project_name_is_escaped(make_provider):
    p = make_provider(FakeSession(rooms=[cocat_rs.ProjectInfo("x", "A<B & C", "editor")]))
    run(p.connect())
    assert "A&lt;B &amp; C" in tip(p, NodeType.FOLDER, ["x"])


def test_a_left_project_says_how_to_join(connected):
    connected.leave_room("b")
    assert "Join" in tip(connected, NodeType.FOLDER, ["b"])


def test_sub_folders_have_no_tooltip(connected):
    assert connected.node_tooltip(NodeType.FOLDER, ["a", "MMS"]) is None


def test_catalogues_say_their_size_author_and_rule(connected):
    p = connected
    catalog = p.create_catalog("shocks", ["a"])
    text = tip(p, NodeType.CATALOG, catalog=catalog)
    assert "0 events" in text and "me" in text and "Created" in text
    assert "rule" not in text


def test_the_provider_says_who_is_signed_in(connected, make_provider):
    assert "me@h" in tip(connected, NodeType.PROVIDER)
    signed_out = make_provider(FakeSession(signed_in=False))
    assert "Not signed in" in tip(signed_out, NodeType.PROVIDER)


def test_actions_carry_a_tooltip(connected):
    actions = connected.folder_actions(["a"]) + connected.actions()
    assert all(a.tooltip for a in actions), [a.name for a in actions if not a.tooltip]


def test_a_role_change_keeps_the_catalogues_and_announces_new_capabilities(make_provider, opened):
    p = make_provider(FakeSession(rooms=[cocat_rs.ProjectInfo("a", "Mine", "editor", personal=True)]))
    announced, removed = [], []
    p.capabilities_changed.connect(announced.append)
    p.catalog_removed.connect(removed.append)
    run(p.connect())
    catalog = p.create_catalog("kept", ["a"])
    opened["a"].role = "viewer"
    p.room_status_changed("a", "synced")
    assert announced == [None] and removed == []
    assert p.catalogs() == [catalog] and p.capabilities(catalog) == set()


def test_an_unreachable_server_is_a_notice_not_an_error(make_provider):
    run(make_provider(FakeSession(rooms=ROOMS)).connect())
    session = FakeSession(rooms=ROOMS)
    session.reachable = False
    p = make_provider(session)
    notices, errors = [], []
    p.notice.connect(notices.append)
    p.error_occurred.connect(errors.append)
    run(p.connect())
    assert errors == [] and "last session" in notices[0]


# ---- rich tooltips ----

def _event(start, stop):
    import uuid
    from SciQLop.components.catalogs import CatalogEvent
    return CatalogEvent(uuid=str(uuid.uuid4()), start=start, stop=stop)


def test_a_catalogue_tip_names_it_and_gives_the_span_of_its_events(connected):
    from datetime import timedelta
    from .conftest import HOUR, T0
    p = connected
    catalog = p.create_catalog("<shocks>", ["a"])
    p.add_event(catalog, _event(T0, T0 + HOUR))
    p.add_event(catalog, _event(T0 + timedelta(days=40), T0 + timedelta(days=40) + HOUR))
    text = tip(p, NodeType.CATALOG, catalog=catalog)
    assert text.startswith("<b>&lt;shocks&gt;</b>") and "2 events" in text
    assert f"{T0:%Y-%m-%d} → {T0 + timedelta(days=40):%Y-%m-%d}" in text


def test_a_copied_catalogue_says_where_it_comes_from():
    from SciQLop.plugins.sciqlop_cocat.tips import catalogue_tip

    class Copied:
        name, author, created, rule, shape_axis, tags = "shocks", "me", None, None, None, ["mms", "bow"]
        copied_from = [{"project_name": "Old", "catalogue_name": "first", "at": None, "by": None},
                       {"project_name": "Team", "catalogue_name": "bow shocks", "at": None, "by": "ana"}]
    text = catalogue_tip(Copied(), [])
    assert "bow shocks in Team" in text and "ana" in text and "first" not in text
    assert "bow, mms" in text


def test_every_tip_is_rich_text(connected):
    p = connected
    assert tip(p, NodeType.PROVIDER).startswith("<") and "https://h" in tip(p, NodeType.PROVIDER)
