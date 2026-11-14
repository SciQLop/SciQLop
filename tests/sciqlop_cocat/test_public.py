"""Public catalogues: all listed under one folder, read-only, each downloaded when first opened."""
import asyncio

import pytest

from SciQLop.components.catalogs.backend.provider import NodeType
from SciQLop.plugins.sciqlop_cocat.remote import RoomListener
from .conftest import HOUR, T0
from .test_provider_rooms import PUBLIC, ROOMS, FakeSession, make_provider, opened, run  # noqa: F401

DONKI = {"id": "public.donki.cme", "name": "CMEs", "folder": "DONKI", "source": "", "description": "",
         "role": "viewer", "changed": "", "count": 40,
         "relay": {"source": "NASA DONKI", "url": "https://kauai.ccmc.gsfc.nasa.gov/DONKI/",
                   "refreshed_at": "2026-11-10T20:00:00Z", "published": True}}


def server(reachable=True):
    session = FakeSession(rooms=ROOMS)
    session.public, session.reachable = [*PUBLIC, DONKI], reachable
    return session


@pytest.fixture
def session():
    return server()


@pytest.fixture
def p(make_provider, session):
    provider = make_provider(session)
    run(provider.connect())
    return provider


def listed(p, name="CMEs"):
    return next(c for c in p.catalogs() if c.name == name and c.path[0] == "public")


def publish_one_event(room):
    cmes = room.create_catalogue(name="CMEs", author="curator")
    cmes.add_events([room.create_event(start=T0, stop=T0 + HOUR, author="curator").uuid])


def opened_once(p, opened):
    """Selects it, as the catalogue browser does, and lets the server's copy arrive."""
    async def scenario():
        p.events(listed(p))
        await asyncio.sleep(0)
        publish_one_event(opened[DONKI["id"]])
        RoomListener(p, DONKI["id"]).changes_done()
        p.room_status_changed(DONKI["id"], "synced")
    run(scenario())
    return listed(p)


def test_every_public_catalogue_is_listed_at_sign_in_without_downloading_any(p, opened):
    assert sorted((c.path, c.name) for c in p.catalogs() if c.path[0] == "public") == [
        (["public", "DONKI"], "CMEs"), (["public", "MMS"], "Bow shocks")]
    assert p.folder_display_name(["public"]) == "Public catalogues"
    assert DONKI["id"] not in opened and not p._events.get(listed(p).uuid)


def test_opening_one_downloads_it_and_shows_its_events(p, opened, qtbot):
    with qtbot.waitSignals([p.loading_started, p.loading_finished]):
        view = opened_once(p, opened)
    assert opened[DONKI["id"]].connected_with == ("https://h", "token")
    assert len(p.events(view)) == 1 and not p.is_loading(view)


def test_the_browser_is_told_when_its_events_arrive(p, opened):
    """The browser shows what events() returned at selection, then waits for events_changed."""
    changed = []
    p.events_changed.connect(lambda c: changed.append(c.uuid))
    view = opened_once(p, opened)
    assert view.uuid in changed


def test_it_is_read_only_and_gets_no_folder_of_its_own(p, opened):
    folders = []
    p.folder_added.connect(folders.append)
    view = opened_once(p, opened)
    assert p.capabilities(view) == set()
    assert [DONKI["id"]] not in folders
    assert not [c for c in p.catalogs() if c.path[0] == DONKI["id"]]


def test_an_opened_one_is_kept_up_to_date_from_the_next_start(p, opened, make_provider):
    opened_once(p, opened)
    run(p.close())
    again = make_provider(server())
    run(again.connect())
    assert DONKI["id"] in again._rooms and len(again.events(listed(again))) == 1


def test_a_listed_one_offers_a_copy_and_once_opened_what_a_reader_can_do(p, opened):
    assert [a.name for a in p.actions(listed(p))] == ["Copy into a project…"]
    view = opened_once(p, opened)
    assert [a.name for a in p.actions(view)] == ["Unfollow", "History…", "Export…", "Copy into a project…"]


def test_unfollow_deletes_its_copy_and_keeps_it_listed(p, opened, make_provider, tmp_path):
    view = opened_once(p, opened)
    [unfollow] = [a for a in p.actions(view) if a.name == "Unfollow"]
    unfollow.callback(view)
    assert DONKI["id"] not in p._rooms and not p._events.get(listed(p).uuid)
    assert listed(p) is not view  # removed and listed again: the browser lets go of it
    assert not list((tmp_path / "cache").glob(f"{DONKI['id']}.*"))
    again = make_provider(server())
    run(again.connect())
    assert DONKI["id"] not in again._rooms


def test_its_tooltip_says_where_it_comes_from_and_how_to_load_it(p, opened):
    text = p.node_tooltip(NodeType.CATALOG, catalog=listed(p))
    assert "NASA DONKI" in text and "2026-11-10" in text and "select it to load it" in text and "40 events" in text
    assert "1 event" in p.node_tooltip(NodeType.CATALOG, catalog=opened_once(p, opened))
    assert "read-only" in p.node_tooltip(NodeType.FOLDER, ["public"])
    assert text.startswith("<b>CMEs</b>") and "2 listed" in p.node_tooltip(NodeType.FOLDER, ["public"])


def test_a_list_its_source_stopped_says_so():
    from SciQLop.plugins.sciqlop_cocat.tips import public_tip
    stopped = {**DONKI, "relay": {**DONKI["relay"], "published": False}}
    assert "NASA DONKI, no longer published" in public_tip(stopped, state="synced", events=[])
    assert "Source" not in public_tip({**DONKI, "relay": None}, state="synced", events=[])


def test_offline_only_the_opened_ones_are_listed(p, opened, make_provider):
    opened_once(p, opened)
    run(p.close())
    again = make_provider(server(reachable=False))
    run(again.connect())
    assert [c.name for c in again.catalogs() if c.path[0] == "public"] == ["CMEs"]
    assert again.events(listed(again)) and not again.is_loading(listed(again))


def test_one_no_longer_public_leaves_the_list(p, opened):
    opened_once(p, opened)
    p.room_status_changed(DONKI["id"], "no_access")
    assert "CMEs" not in [c.name for c in p.catalogs()] and DONKI["id"] not in p._rooms


def test_signed_out_lists_none(p):
    run(p.sign_out())
    assert not [c for c in p.catalogs() if c.path and c.path[0] == "public"]


# ---- drag and drop ----

def dropped(p, catalog, path):
    """As SciQLop's tree does for a drop inside the provider, then lets the server calls run."""
    async def scenario():
        p.move_catalog(catalog, path)
        for _ in range(3):
            await asyncio.sleep(0)
    run(scenario())


def test_dropping_a_public_catalogue_on_a_project_copies_it_there(p, session):
    dropped(p, listed(p), ["a"])
    assert ("copy_public_catalogue", DONKI["id"], "a") in session.calls
    assert listed(p).path == ["public", "DONKI"]


def test_dropping_it_on_the_root_copies_it_into_a_new_project(p, session):
    dropped(p, listed(p), [])
    assert ("copy_public_catalogue", DONKI["id"], None) in session.calls and "copy-id" in p._rooms


def test_it_cannot_be_dropped_on_a_project_i_only_read(p, session):
    with pytest.raises(PermissionError):
        p.move_catalog(listed(p), ["b"])
    assert not session.calls


@pytest.fixture
def form(monkeypatch):
    from SciQLop.plugins.sciqlop_cocat import submission
    asked = []

    def answer(filled):
        monkeypatch.setattr(submission, "ask_submission",
                            lambda name, folders, folder: asked.append((name, folders, folder)) or filled)
    return answer, asked


def test_dropping_my_catalogue_on_public_catalogues_submits_it_for_review(p, session, form):
    answer, asked = form
    answer({"title": "Shocks 2020", "folder": "MMS", "description": "By eye", "note": "Please"})
    mine = p.create_catalog("shocks", ["a"])
    dropped(p, mine, ["public", "MMS"])
    assert asked == [("shocks", ["DONKI", "MMS"], "MMS")]  # the folder it was dropped on
    assert ("submit_catalogue", "a", mine.uuid, "Shocks 2020", "MMS", "By eye", "Please") in session.calls
    assert mine.path == ["a"]  # a submission is a copy: the catalogue stays mine


def test_a_cancelled_form_submits_nothing(p, session, form):
    answer, _ = form
    answer(None)
    dropped(p, p.create_catalog("shocks", ["a"]), ["public"])
    assert not [c for c in session.calls if c[0] == "submit_catalogue"]


def test_my_catalogues_offer_the_submission_from_their_menu_too(p):
    mine = p.create_catalog("shocks", ["a"])
    assert "Submit as a public catalogue…" in [a.name for a in p.actions(mine)]
    assert "Submit as a public catalogue…" not in [a.name for a in p.actions(listed(p))]


def test_the_form_starts_from_the_catalogue_name_and_leaves_out_what_is_empty(qapp, monkeypatch):
    from PySide6.QtWidgets import QDialog
    from SciQLop.plugins.sciqlop_cocat.submission import ask_submission
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    assert ask_submission("shocks", ["MMS"]) == {"title": "shocks", "folder": None, "description": None,
                                                 "note": None}
    assert ask_submission("shocks", ["MMS"], "MMS")["folder"] == "MMS"


def test_a_catalogue_of_another_provider_dropped_on_public_says_how_to_submit(p):
    with pytest.raises(PermissionError, match="submit"):
        p.create_catalog("from tscat", ["public"])


# ---- nested folders ----

AKR = {"id": "public.literature.wind-akr-bursts", "name": "AKR bursts", "folder": "Literature/Earth",
       "source": "", "description": "", "role": "viewer", "changed": "", "count": 9031}


@pytest.fixture
def nested(make_provider):
    session = server()
    session.public = [*session.public, AKR]
    provider = make_provider(session)
    run(provider.connect())
    return provider, session


def test_a_folder_path_is_a_folder_in_a_folder(nested):
    p, _ = nested
    assert listed(p, "AKR bursts").path == ["public", "Literature", "Earth"]


def test_dropping_on_a_nested_folder_submits_to_its_whole_path(nested, form):
    p, session = nested
    answer, asked = form
    answer({"title": "Shocks 2020", "folder": "Literature/Earth", "description": None, "note": None})
    mine = p.create_catalog("shocks", ["a"])
    dropped(p, mine, ["public", "Literature", "Earth"])
    assert asked[0][2] == "Literature/Earth"
