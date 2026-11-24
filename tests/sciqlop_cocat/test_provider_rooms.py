import asyncio

import cocat_rs
import pytest

from SciQLop.components.catalogs import CatalogEvent, CatalogRegistry
from SciQLop.plugins.sciqlop_cocat import provider as provider_module
from SciQLop.plugins.sciqlop_cocat.provider import CocatRsProvider
from .conftest import HOUR, T0, own_catalogs


class FakeSignIn:
    url, code = "https://h/ui/sign-in#K7QM", "K7QM-2XRD"

    def __init__(self, session, answer):
        self._session, self._answer, self.cancelled = session, answer, False

    def wait(self):
        if self._answer != "approved":
            raise cocat_rs.NotSignedIn(f"The sign-in was {self._answer}.")
        self._session.signed_in = True

    def cancel(self):
        self.cancelled = True


class FakeSession:
    url = "https://h"
    cookie = "token"

    def __init__(self, signed_in=True, rooms=(), sign_in_answer="approved"):
        self.signed_in = signed_in
        self._rooms = list(rooms)
        self._sign_in_answer = sign_in_answer
        self.sign_outs = 0
        self.reachable = True
        self.calls = []
        self.public = []  # what the server lists as public catalogues

    async def start_sign_in(self):
        self.sign_in = FakeSignIn(self, self._sign_in_answer)
        return self.sign_in

    async def sign_out(self):
        self.sign_outs += 1
        self.signed_in = False

    async def projects(self):
        if not self.signed_in or not self.reachable:  # the real session forgets a refused token
            return None
        return self._rooms

    async def email(self):
        return "me@h"

    async def call(self, function, *args, **kwargs):
        if function is cocat_rs.raw.create_project:
            if args[0] == "refused":
                raise cocat_rs.Forbidden("no")
            return cocat_rs.ProjectInfo("new-id", args[0], "owner")
        if function is cocat_rs.raw.public_catalogues:  # at every connect: not recorded
            return self.public
        self.calls.append((function.__name__, *args, *kwargs.values()))
        if function == cocat_rs.Project.at:
            assert args == ("a", 3)
            return self.past
        if function is cocat_rs.raw.copy_public_catalogue:
            return {"project_id": args[1] or "copy-id", "name": "Bow shocks", "catalogue": "u1"}


class RecordingRoom:
    """A real offline room that records what would have gone to the server."""

    def __init__(self, room):
        self._room = room
        self.connected_with = None

    def __getattr__(self, name):
        return getattr(self._room, name)

    def connect(self, url, cookie):
        self.connected_with = (url, cookie)

    def save(self, timeout=None):
        self.saved = True


PROJECT_ACTIONS = ["Leave", "Save version…", "History…", "Import…", "Import tscat catalogues", "Open in browser"]
SHARED_ACTIONS = ["Leave", "History…", "Sharing…", "Open in browser"]  # a project shared with the person, read-only
CONNECTED_ACTIONS = ["Sign out", "New project…", "Open CoCat in browser"]
PUBLIC = [{"id": "public.bow-shocks", "name": "Bow shocks", "folder": "MMS", "source": "", "description": "",
           "role": "viewer", "changed": "", "count": 12}]

ROOMS = [cocat_rs.ProjectInfo("b", "Team", "viewer"),
         cocat_rs.ProjectInfo("a", "My catalogues", "owner", personal=True)]


@pytest.fixture(autouse=True)
def opened(monkeypatch):
    rooms = {}

    def open_room(cache_dir, room_id):
        rooms[room_id] = RecordingRoom(cocat_rs.Project.open(cache_dir, room_id))
        return rooms[room_id]

    monkeypatch.setattr(provider_module, "open_room", open_room)
    yield rooms
    for r in rooms.values():
        r.close()


@pytest.fixture
def make_provider(qapp, tmp_path):
    made = []

    def make(session):
        p = CocatRsProvider(author="me", session=session, cache_dir=tmp_path / "cache")
        made.append(p)
        return p

    yield make
    for p in made:
        CatalogRegistry.instance()._forget_for_tests(p)


def run(coroutine):
    return asyncio.run(coroutine)


def test_connect_lists_rooms_with_personal_first(make_provider):
    p = make_provider(FakeSession(rooms=ROOMS))
    folders = []
    p.folder_added.connect(folders.append)
    assert run(p.connect()) is True
    assert folders == [["a"], ["b"]]
    assert p.folder_display_name(["a"]) == "My catalogues"
    assert p.folder_display_name(["b"]) == "Team"
    assert [a.name for a in p.actions()] == CONNECTED_ACTIONS
    assert [a.name for a in p.folder_actions(["a"])] == PROJECT_ACTIONS


def test_the_own_project_is_the_default_whatever_its_name(make_provider):
    p = make_provider(FakeSession(rooms=[cocat_rs.ProjectInfo("b", "Personal", "owner"),
                                         cocat_rs.ProjectInfo("a", "Renamed", "owner", personal=True)]))
    run(p.connect())
    assert p.folder_display_name(["a"]) == "Renamed"
    assert p.folder_display_name(["b"]) == "Personal"


def test_without_an_own_project_the_first_one_is_the_default(make_provider):
    p = make_provider(FakeSession(rooms=[cocat_rs.ProjectInfo("b", "Team", "editor"),
                                         cocat_rs.ProjectInfo("c", "Other", "editor")]))
    run(p.connect())
    assert p.folder_display_name(["b"]) == "Team"
    assert p.folder_display_name(["c"]) == "Other"


def test_without_a_sign_in_connect_says_how_and_offers_sign_in(make_provider):
    p = make_provider(FakeSession(signed_in=False))
    errors = []
    p.error_occurred.connect(errors.append)
    assert run(p.connect()) is False
    assert len(errors) == 1 and "Sign in" in errors[0]
    assert [a.name for a in p.actions()] == ["Sign in…", "Open CoCat in browser"]


def test_the_author_is_the_signed_in_email(make_provider):
    p = make_provider(FakeSession(rooms=ROOMS))
    run(p.connect())
    assert p._author == "me@h"


def test_sign_in_opens_the_browser_then_connects(make_provider, monkeypatch):
    opened_urls = []
    monkeypatch.setattr(provider_module, "open_url", opened_urls.append)
    p = make_provider(FakeSession(signed_in=False, rooms=ROOMS))
    assert run(p.sign_in()) is True
    assert opened_urls == [FakeSignIn.url]
    assert [a.name for a in p.actions()] == CONNECTED_ACTIONS


def test_a_denied_sign_in_is_reported_and_stays_signed_out(make_provider, monkeypatch):
    monkeypatch.setattr(provider_module, "open_url", lambda url: None)
    p = make_provider(FakeSession(signed_in=False, rooms=ROOMS, sign_in_answer="denied"))
    errors = []
    p.error_occurred.connect(errors.append)
    assert run(p.sign_in()) is False
    assert errors == ["The sign-in was denied."]
    assert [a.name for a in p.actions()] == ["Sign in…", "Open CoCat in browser"]


def test_sign_out_disconnects_and_forgets_the_sign_in(make_provider):
    session = FakeSession(rooms=ROOMS)
    p = make_provider(session)
    run(p.connect())
    run(p.sign_out())
    assert session.sign_outs == 1
    assert [a.name for a in p.actions()] == ["Sign in…", "Open CoCat in browser"]


def test_join_room_opens_local_copy_and_connects(make_provider, opened, tmp_path):
    seed = cocat_rs.Project.open(tmp_path / "cache", "a")
    seed.create_catalogue(name="kept", author="t")
    seed.close()
    p = make_provider(FakeSession(rooms=ROOMS))

    async def go():
        await p.connect()
        await p.join_room("a")
    run(go())
    assert [c.name for c in own_catalogs(p)] == ["kept"]
    assert opened["a"].connected_with == ("https://h", "token")
    assert [a.name for a in p.folder_actions(["a"])] == PROJECT_ACTIONS
    assert p.create_catalog("n").path == ["a"]


def test_leave_room_flushes_pending_ranges_first(make_provider, opened, tmp_path):
    from SciQLop.components.catalogs import CatalogEvent
    p = make_provider(FakeSession(rooms=ROOMS))

    async def go():
        await p.connect()
        await p.join_room("a")
    run(go())
    c = p.create_catalog("n", ["a"])
    p.add_event(c, CatalogEvent(uuid="e1", start=T0, stop=T0 + HOUR))
    p.events(c)[0].stop = T0 + 3 * HOUR
    p.leave_room("a")
    reopened = cocat_rs.Project.open(tmp_path / "cache", "a")
    assert reopened.event("e1").stop == T0 + 3 * HOUR
    reopened.close()
    assert own_catalogs(p) == []


async def _settle():
    for _ in range(5):
        await asyncio.sleep(0)


def test_an_ended_sign_in_is_reported_once_and_signs_out(make_provider, opened):
    session = FakeSession(rooms=ROOMS)
    p = make_provider(session)
    errors = []
    p.error_occurred.connect(errors.append)

    async def go():
        await p.connect()
        await p.join_room("a")
        p.room_status_changed("a", "unauthorized")
        p.room_status_changed("a", "unauthorized")
        await _settle()
    run(go())
    assert len(errors) == 1 and "Sign in" in errors[0]
    assert session.sign_outs == 1 and own_catalogs(p) == []
    assert [a.name for a in p.actions()] == ["Sign in…", "Open CoCat in browser"]


def test_a_role_change_makes_the_project_read_only(make_provider, opened):
    session = FakeSession(rooms=[cocat_rs.ProjectInfo("a", "Mine", "editor", personal=True)])
    p = make_provider(session)

    async def go():
        await p.connect()
        await p.join_room("a")
        p.create_catalog("kept", ["a"])
        opened["a"].role = "viewer"  # cocat-rs reconnects at once and learns the new role
        p.room_status_changed("a", "connecting")
        p.room_status_changed("a", "synced")
    run(go())
    [catalog] = own_catalogs(p)
    assert catalog.name == "kept" and p.capabilities(catalog) == set()
    assert p.folder_display_name(["a"]) == "Mine"
    assert session.sign_outs == 0 and [a.name for a in p.actions()] == CONNECTED_ACTIONS


def test_a_promotion_makes_the_project_writable(make_provider, opened):
    p = make_provider(FakeSession(rooms=ROOMS))

    async def go():
        await p.connect()
        await p.join_room("b")
        opened["b"].role = "editor"
        p.room_status_changed("b", "synced")
    run(go())
    assert p.folder_display_name(["b"]) == "Team"
    assert p.create_catalog("new", ["b"]).path == ["b"]


def test_the_listener_passes_a_new_role_on(make_provider, opened):
    from SciQLop.plugins.sciqlop_cocat.remote import RoomListener
    p = make_provider(FakeSession(rooms=ROOMS))

    async def go():
        await p.connect()
        await p.join_room("a")
        RoomListener(p, "a").role("viewer")
    run(go())
    assert p.folder_display_name(["a"]) == "My catalogues"


def test_a_project_you_were_removed_from_leaves_the_tree(make_provider, opened):
    session = FakeSession(rooms=ROOMS)
    p = make_provider(session)
    removed, notices = [], []
    p.folder_removed.connect(removed.append)
    p.notice.connect(notices.append)

    async def go():
        await p.connect()
        await p.join_room("a")
        p.room_status_changed("a", "no_access")
    run(go())
    assert removed == [["a"]] and own_catalogs(p) == []
    assert len(notices) == 1 and "no longer" in notices[0]
    assert "a" not in p._room_infos and session.sign_outs == 0


def test_disconnect_leaves_rooms_and_folders(make_provider, opened):
    p = make_provider(FakeSession(rooms=ROOMS))

    async def go():
        await p.connect()
        await p.join_room("a")
    run(go())
    removed = []
    p.folder_removed.connect(removed.append)
    p.disconnect()
    assert own_catalogs(p) == [] and sorted(removed) == [["a"], ["b"]]
    assert [a.name for a in p.actions()] == ["Connect", "Sign out", "Open CoCat in browser"]


def test_projects_listing_failure_is_a_connect_failure(make_provider):
    session = FakeSession(rooms=ROOMS)

    async def broken():
        return None
    session.projects = broken
    p = make_provider(session)
    errors = []
    p.error_occurred.connect(errors.append)
    assert run(p.connect()) is False
    assert len(errors) == 1 and [a.name for a in p.actions()] == ["Connect", "Sign out", "Open CoCat in browser"]


def test_join_failure_reports_and_leaves_nothing_behind(make_provider, opened, monkeypatch):
    p = make_provider(FakeSession(rooms=ROOMS))
    errors = []
    p.error_occurred.connect(errors.append)

    monkeypatch.setattr(RecordingRoom, "connect", lambda self, url, cookie: (_ for _ in ()).throw(RuntimeError("bad url")))
    run(p.connect())
    assert len(errors) == 2  # one per project
    assert p._rooms == {} and p._listen_handles == {}
    assert [a.name for a in p.folder_actions(["a"])] == ["Join", "History…", "Open in browser"]
    assert [a.name for a in p.folder_actions(["b"])] == ["Join", "History…", "Sharing…", "Open in browser"]


def test_join_records_the_status_the_listener_reports_first(make_provider, opened):
    p = make_provider(FakeSession(rooms=ROOMS))

    async def go():
        await p.connect()
        await p.join_room("a")
        await asyncio.sleep(0.05)
    run(go())
    assert p.room_status("a") == opened["a"].status


def test_each_room_that_never_syncs_is_reported_once(make_provider, opened, monkeypatch, qtbot):
    monkeypatch.setattr(provider_module, "SYNC_STALL_MS", 50)
    p = make_provider(FakeSession(rooms=ROOMS))
    errors = []
    p.error_occurred.connect(errors.append)

    run(p.connect())
    qtbot.waitUntil(lambda: len(errors) == 2)
    assert sorted(e.split("'")[1] for e in errors) == ["My catalogues", "Team"]
    qtbot.wait(150)
    assert len(errors) == 2


def test_no_stall_report_for_a_room_that_synced_or_was_left(make_provider, opened, monkeypatch, qtbot):
    monkeypatch.setattr(provider_module, "SYNC_STALL_MS", 50)
    p = make_provider(FakeSession(rooms=ROOMS))
    errors = []
    p.error_occurred.connect(errors.append)

    async def go():
        await p.connect()
        await p.join_room("a")
        await p.join_room("b")
    run(go())
    p.room_status_changed("a", "synced")
    p.leave_room("b")
    qtbot.wait(150)
    assert errors == []


def _joined(make_provider, *room_ids):
    p = make_provider(FakeSession(rooms=ROOMS))

    run(p.connect())
    for room_id in set(p._rooms) - set(room_ids):
        p.leave_room(room_id)
    return p


def _seed(tmp_path, room_id, name):
    seed = cocat_rs.Project.open(tmp_path / "cache", room_id)
    seed.create_catalogue(name=name, author="t")
    seed.close()


def test_a_viewer_project_is_read_only(make_provider, opened, tmp_path):
    _seed(tmp_path, "a", "mine")
    _seed(tmp_path, "b", "shared")
    p = _joined(make_provider, "a", "b")
    by_name = {c.name: c for c in own_catalogs(p)}
    assert p.capabilities(by_name["shared"]) == set()
    assert p.capabilities(by_name["mine"]) == set(provider_module.CAPABILITIES)
    assert p.capabilities() == set(provider_module.CAPABILITIES)


def test_no_catalogue_can_be_created_when_only_viewer_projects_are_joined(make_provider, opened):
    p = _joined(make_provider, "b")
    assert p.capabilities() == set()
    with pytest.raises(PermissionError):
        p.create_catalog("n")
    with pytest.raises(PermissionError):
        p.create_catalog("n", ["b"])


def test_a_new_catalogue_skips_a_read_only_default(make_provider, opened):
    p = make_provider(FakeSession(rooms=[cocat_rs.ProjectInfo("v", "Shared", "viewer", personal=True),
                                         cocat_rs.ProjectInfo("e", "Team", "editor")]))

    async def go():
        await p.connect()
        await p.join_room("v")
        await p.join_room("e")
    run(go())
    assert p.create_catalog("n").path == ["e"]


def test_a_project_and_the_web_app_open_in_the_browser(make_provider, monkeypatch):
    urls = []
    monkeypatch.setattr(provider_module, "open_url", urls.append)
    session = FakeSession(rooms=[cocat_rs.ProjectInfo("Bepi MSA", "Bepi MSA", "editor")])
    session.url = "https://h/cocat-dev/"
    p = make_provider(session)
    run(p.connect())
    [project] = [a for a in p.folder_actions(["Bepi MSA"]) if a.name == "Open in browser"]
    project.callback(["Bepi MSA"])
    [home] = [a for a in p.actions() if a.name == "Open CoCat in browser"]
    home.callback(None)
    assert urls == ["https://h/cocat-dev/ui/rooms/Bepi%20MSA/browse", "https://h/cocat-dev/ui/"]


def test_sharing_opens_the_dialog_for_that_project(make_provider, monkeypatch):
    shown = []
    monkeypatch.setattr(provider_module, "show_sharing_dialog", lambda *args, **kw: shown.append(args))
    p = make_provider(FakeSession(rooms=ROOMS))
    run(p.connect())
    [sharing] = [a for a in p.folder_actions(["b"]) if a.name == "Sharing…"]
    sharing.callback(["b"])
    [(session, project_id, name, url, opener, _parent)] = shown
    assert (project_id, name, url) == ("b", "Team", "https://h/ui/rooms/b/browse#share")
    assert opener is provider_module.open_url


def test_a_new_project_is_listed_and_joined(make_provider, opened):
    p = make_provider(FakeSession(rooms=ROOMS))
    folders = []
    p.folder_added.connect(folders.append)

    async def go():
        await p.connect()
        return await p.create_project("Fresh")
    info = run(go())
    assert info.id == "new-id" and ["new-id"] in folders
    assert "new-id" in opened and p.folder_display_name(["new-id"]) == "Fresh"
    assert p.create_catalog("c", ["new-id"]).path == ["new-id"]


def test_a_refused_new_project_is_reported(make_provider, opened):
    p = make_provider(FakeSession(rooms=ROOMS))
    errors = []
    p.error_occurred.connect(errors.append)

    async def go():
        await p.connect()
        return await p.create_project("refused")
    assert run(go()) is None
    assert len(errors) == 1 and "refused" in errors[0]


def test_connect_joins_every_project(make_provider, opened):
    p = make_provider(FakeSession(rooms=ROOMS))
    run(p.connect())
    assert sorted(p._rooms) == ["a", "b"]


def test_a_project_left_stays_left_on_the_next_start(make_provider, opened):
    p = make_provider(FakeSession(rooms=ROOMS))
    run(p.connect())
    [leave] = [a for a in p.folder_actions(["b"]) if a.name == "Leave"]
    leave.callback(["b"])
    p.disconnect()
    again = make_provider(FakeSession(rooms=ROOMS))
    run(again.connect())
    assert sorted(again._rooms) == ["a"]
    [join] = [a for a in again.folder_actions(["b"]) if a.name == "Join"]
    run(_call_and_settle(join.callback, ["b"]))
    third = make_provider(FakeSession(rooms=ROOMS))
    run(third.connect())
    assert sorted(third._rooms) == ["a", "b"]


async def _call_and_settle(callback, *args):
    callback(*args)
    await _settle()


def an_earlier_session(make_provider) -> None:
    """Signed in, then closed: a SciQLop still open would be another window, not the last session."""
    earlier = make_provider(FakeSession(rooms=ROOMS))
    run(earlier.connect())
    run(earlier.close())


def test_an_unreachable_server_shows_the_projects_of_the_last_session(make_provider, opened):
    an_earlier_session(make_provider)
    session = FakeSession(rooms=ROOMS)
    session.reachable = False
    p = make_provider(session)
    notices = []
    p.notice.connect(notices.append)
    assert run(p.connect()) is True
    assert sorted(p._rooms) == ["a", "b"]
    assert p.folder_display_name(["b"]) == "Team"
    assert len(notices) == 1 and "last session" in notices[0]
    assert [a.name for a in p.actions()][0] == "Reconnect"


def test_start_connects_only_when_signed_in(make_provider, opened):
    signed_out = make_provider(FakeSession(signed_in=False, rooms=ROOMS))
    errors = []
    signed_out.error_occurred.connect(errors.append)
    run(_call_and_settle(signed_out.start))
    assert errors == [] and signed_out._rooms == {}
    signed_in = make_provider(FakeSession(rooms=ROOMS))
    run(_call_and_settle(signed_in.start))
    assert sorted(signed_in._rooms) == ["a", "b"]


def _icon_colour(icon):
    image = icon.pixmap(16, 16).toImage()
    return image.pixelColor(12, 12).name()  # the badge, bottom right


def test_each_project_shows_its_sync_state(make_provider, opened):
    from SciQLop.components.catalogs.backend.provider import NodeType
    p = make_provider(FakeSession(rooms=ROOMS))
    run(p.connect())
    p.leave_room("b")
    p.room_status_changed("a", "synced")
    synced = _icon_colour(p.node_icon(NodeType.FOLDER, ["a"]))
    p.room_status_changed("a", "connecting")
    connecting = _icon_colour(p.node_icon(NodeType.FOLDER, ["a"]))
    left = _icon_colour(p.node_icon(NodeType.FOLDER, ["b"]))
    assert len({synced, connecting, left}) == 3
    assert p.node_icon(NodeType.FOLDER, ["a", "sub"]) is None


def test_offline_only_local_actions_are_offered(make_provider, opened):
    an_earlier_session(make_provider)
    session = FakeSession(rooms=ROOMS)
    session.reachable = False
    p = make_provider(session)
    run(p.connect())
    assert [a.name for a in p.folder_actions(["a"])] == ["Leave", "Import…", "Import tscat catalogues",
                                                         "Open in browser"]
    catalog = p.create_catalog("c", ["a"])
    assert [a.name for a in p.actions(catalog)] == ["Export…"]


def test_a_catalogue_has_its_history(make_provider, opened, monkeypatch):
    shown = []
    monkeypatch.setattr(provider_module, "show_history_dialog",
                        lambda session, project_id, title, catalogue=None, on_copied=None, parent=None:
                        shown.append((project_id, title, catalogue)) or _Visible())
    p = make_provider(FakeSession(rooms=ROOMS))
    run(p.connect())
    catalog = p.create_catalog("shocks", ["a"])
    [history] = [a for a in p.actions(catalog) if a.name == "History…"]
    history.callback(catalog)
    [project_history] = [a for a in p.folder_actions(["a"]) if a.name == "History…"]
    project_history.callback(["a"])
    assert shown == [("a", "shocks", catalog.uuid), ("a", "My catalogues", None)]


class _Visible:
    def isVisible(self):
        return True

    def raise_(self):
        pass

    def activateWindow(self):
        pass


def test_saving_a_version_sends_local_changes_first(make_provider, opened):
    session = FakeSession(rooms=ROOMS)
    p = make_provider(session)
    run(p.connect())
    assert run(p.save_version("a", "before cleanup")) is True
    assert opened["a"].saved and session.calls == [("commit", "a", "before cleanup")]


def test_a_copied_version_is_listed_and_joined(make_provider, opened):
    p = make_provider(FakeSession(rooms=ROOMS))
    run(p.connect())
    run(p.add_project(cocat_rs.ProjectInfo("c", "trial", "owner")))
    assert "c" in p._rooms and p.folder_display_name(["c"]) == "trial"
    again = make_provider(FakeSession(rooms=[]))
    again._session.reachable = False
    run(again.connect())
    assert "c" in again._room_infos  # remembered for an offline start


WRITABLE = [cocat_rs.ProjectInfo("a", "Mine", "owner", personal=True),
            cocat_rs.ProjectInfo("c", "Shared", "editor")]


def test_an_exported_catalogue_imports_into_another_project(make_provider, opened, monkeypatch, tmp_path):
    from SciQLop.plugins.sciqlop_cocat import questions
    from SciQLop.plugins.sciqlop_cocat.transfer import FORMATS
    p = make_provider(FakeSession(rooms=WRITABLE))
    run(p.connect())
    catalog = p.create_catalog("shocks", ["a"])
    p.add_event(catalog, CatalogEvent(uuid="e1", start=T0, stop=T0 + HOUR))
    votable = FORMATS[0]
    monkeypatch.setattr(questions, "ask_export_path", lambda name: (votable, tmp_path / "s.xml"))
    monkeypatch.setattr(questions, "ask_import_path", lambda: (votable, tmp_path / "s.xml"))
    [export] = [a for a in p.actions(catalog) if a.name == "Export…"]
    export.callback(catalog)
    [import_] = [a for a in p.folder_actions(["c"]) if a.name == "Import…"]
    import_.callback(["c"])
    [imported] = [c for c in own_catalogs(p) if c.path == ["c"]]
    assert imported.name == "shocks" and len(p.events(imported)) == 1


def test_tfcat_export_asks_for_a_band(make_provider, opened, monkeypatch, tmp_path):
    from SciQLop.plugins.sciqlop_cocat import questions
    from SciQLop.plugins.sciqlop_cocat.transfer import FORMATS
    p = make_provider(FakeSession(rooms=WRITABLE))
    run(p.connect())
    catalog = p.create_catalog("bursts", ["a"])
    p.add_event(catalog, CatalogEvent(uuid="e1", start=T0, stop=T0 + HOUR))
    asked = []
    monkeypatch.setattr(questions, "ask_export_path", lambda name: (FORMATS[2], tmp_path / "b.json"))
    monkeypatch.setattr(questions, "ask_value_range", lambda axis: asked.append(axis) or (1.0, 5.0))
    [export] = [a for a in p.actions(catalog) if a.name == "Export…"]
    export.callback(catalog)
    assert len(asked) == 1 and (tmp_path / "b.json").exists()


def test_a_failed_import_is_reported(make_provider, opened, monkeypatch, tmp_path):
    from SciQLop.plugins.sciqlop_cocat import questions
    from SciQLop.plugins.sciqlop_cocat.transfer import FORMATS
    (tmp_path / "bad.xml").write_text("not a votable")
    monkeypatch.setattr(questions, "ask_import_path", lambda: (FORMATS[0], tmp_path / "bad.xml"))
    p = make_provider(FakeSession(rooms=WRITABLE))
    run(p.connect())
    errors = []
    p.error_occurred.connect(errors.append)
    [import_] = [a for a in p.folder_actions(["a"]) if a.name == "Import…"]
    import_.callback(["a"])
    assert len(errors) == 1 and "bad.xml" in errors[0]


def test_read_only_projects_offer_no_import(make_provider, opened):
    p = make_provider(FakeSession(rooms=ROOMS))
    run(p.connect())
    names = [a.name for a in p.folder_actions(["b"])]
    assert "Import…" not in names and "Import tscat catalogues" not in names


def test_a_public_catalogue_is_copied_into_a_new_project(make_provider, opened, monkeypatch):
    from SciQLop.plugins.sciqlop_cocat import questions
    asked = []
    monkeypatch.setattr(questions, "ask_choice", lambda title, label, items: asked.append(items) or 0)
    session = FakeSession(rooms=WRITABLE)
    p = make_provider(session)
    run(p.connect())
    run(p.copy_public_catalogue(PUBLIC[0]))
    assert asked == [["A new project", "Mine", "Shared"]]
    assert ("copy_public_catalogue", "public.bow-shocks", None) in session.calls
    assert "copy-id" in p._rooms and p.folder_display_name(["copy-id"]) == "Bow shocks"


def test_a_public_catalogue_is_copied_into_a_chosen_project(make_provider, opened, monkeypatch):
    from SciQLop.plugins.sciqlop_cocat import questions
    monkeypatch.setattr(questions, "ask_choice", lambda title, label, items: 2)
    session = FakeSession(rooms=WRITABLE)
    p = make_provider(session)
    run(p.connect())
    run(p.copy_public_catalogue(PUBLIC[0]))
    assert ("copy_public_catalogue", "public.bow-shocks", "c") in session.calls
    assert sorted(p._rooms) == ["a", "c"]  # the copy reaches the joined project as a remote change


def test_a_version_is_viewed_read_only_beside_the_live_project(make_provider, opened, tmp_path):
    from datetime import datetime
    from SciQLop.plugins.sciqlop_cocat.history import Version
    session = FakeSession(rooms=WRITABLE)
    session.past = cocat_rs.Project.open(tmp_path / "past", "a")
    session.past.create_catalogue(name="as it was", author="a")
    p = make_provider(session)
    run(p.connect())
    live = p.create_catalog("as it is", ["a"])
    version = Version(3, datetime(2026, 11, 9, 15, 10), "a@x.org", "", "")
    run(p.view_version("a", version))
    versions = p._versions_provider
    [past] = versions.catalogs()
    assert past.name == "as it was" and past.path == ["a@3"]
    assert versions.folder_display_name(["a@3"]) == "Mine as of 2026-11-09 15:10"
    assert [c.name for c in own_catalogs(p)] == ["as it is"] and live.provider is p
    run(p.close())
    assert versions.catalogs() == []
    CatalogRegistry.instance()._forget_for_tests(versions)


def _tscat_file(tmp_path):
    import cocat_rs.tscat
    source = cocat_rs.Project.open(tmp_path / "tscat_source", "s")
    flybys = source.create_catalogue(name="flybys", author="x", attributes={"path__": ["Mercury", "MSA"]})
    cocat_rs.tscat.export_json(source, [flybys], tmp_path / "t.json")
    source.close()
    return tmp_path / "t.json"


def test_an_imported_tscat_catalogue_keeps_its_folder(make_provider, opened, tmp_path):
    from SciQLop.plugins.sciqlop_cocat.transfer import FORMATS, import_file
    p = make_provider(FakeSession(rooms=WRITABLE))
    run(p.connect())
    path = _tscat_file(tmp_path)
    assert p.import_into("a", lambda project: import_file(FORMATS[1], project, path), "t.json")
    [flybys] = own_catalogs(p)
    assert flybys.path == ["a", "Mercury", "MSA"]


def test_a_tscat_catalogue_moved_to_the_root_stays_there(make_provider, opened, tmp_path):
    from SciQLop.plugins.sciqlop_cocat.transfer import FORMATS, import_file
    p = make_provider(FakeSession(rooms=WRITABLE))
    run(p.connect())
    path = _tscat_file(tmp_path)
    p.import_into("a", lambda project: import_file(FORMATS[1], project, path), "t.json")
    [flybys] = own_catalogs(p)
    p.move_catalog(flybys, ["a"])
    p._rewrap_room("a")  # as when the project is shown afresh
    [flybys] = own_catalogs(p)
    assert flybys.path == ["a"]


# ---- event lifetime: an event the plugin stops showing must be freed, not kept until exit ----

def _live_events() -> int:
    import gc
    gc.collect()
    return sum(isinstance(o, provider_module.CocatRsEvent) for o in gc.get_objects())


def test_events_are_freed_once_no_longer_shown(make_provider):
    p = make_provider(FakeSession(rooms=ROOMS))
    run(p.connect())
    before = _live_events()
    room = p._rooms["a"]
    big = room.create_catalogue(name="big", author="me")
    big.add_events([room.create_event(start=T0, stop=T0 + HOUR, author="me").uuid for _ in range(200)])
    for _ in range(3):  # an import or a role change shows the project afresh
        p._rewrap_room("a")
    assert _live_events() - before == 200
    p.leave_room("a")
    assert _live_events() == before
