"""Two providers sync through a real local cocat-server.

Run with: COCAT_SERVER=<path to a cocat-server binary> uv run pytest -m live tests/sciqlop_cocat
"""
import asyncio
import os
import socket
import subprocess
import time
import urllib.parse
import urllib.request
import uuid

import cocat_rs
import pytest

from SciQLop.components.catalogs import CatalogEvent, CatalogRegistry
from SciQLop.plugins.sciqlop_cocat.provider import CocatRsProvider
from SciQLop.plugins.sciqlop_cocat.session import Session
from .conftest import HOUR, T0

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not os.environ.get("COCAT_SERVER"), reason="COCAT_SERVER is not set"),
]

EMAIL = "scientist@example.org"
COLLEAGUE = "colleague@example.org"  # an editor of the owner's project
PASSWORD = "quartz-magnetopause-1987"  # the server refuses guessable passwords


def _signed_in(url: str, email: str = EMAIL) -> Session:
    """A password sign-in: it lasts while Python runs, and nothing goes to the keyring."""
    client = cocat_rs.Client(url)
    client.login(email, PASSWORD)
    return Session(url, client)


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_port(port: int, timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.02)
    raise TimeoutError(f"cocat-server did not listen on {port}")


@pytest.fixture
def server(tmp_path):
    binary = os.environ["COCAT_SERVER"]
    database = str(tmp_path / "cocat.db")
    updates = tmp_path / "updates"
    updates.mkdir()
    room_id = str(uuid.uuid4())

    def run(*arguments):
        subprocess.run([binary, *arguments, "--db_path", database], check=True, capture_output=True)

    run("create-user", "--email", EMAIL, "--password", PASSWORD)
    run("create-room", "--owner", EMAIL, "--room-id", room_id, "--name", "Personal")
    run("create-user", "--email", COLLEAGUE, "--password", PASSWORD)
    run("add-user-to-room", "--email", COLLEAGUE, "--room_id", room_id, "--role", "editor")
    run("set-curator", "--email", EMAIL)
    port = _free_port()
    process = subprocess.Popen(
        [binary, "serve", "--host", "127.0.0.1", "--port", str(port),
         "--update_dir", str(updates), "--db_path", database],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _wait_for_port(port)
        yield f"http://127.0.0.1:{port}", room_id
    finally:
        process.terminate()
        process.wait(timeout=15)


async def _until(condition, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() > deadline:
            raise TimeoutError("condition not met in time")
        await asyncio.sleep(0.05)


def _named(provider, name):
    return next((c for c in provider.catalogs() if c.name == name), None)


def test_two_providers_see_each_other(qapp, server, tmp_path):
    url, room_id = server
    providers = [CocatRsProvider(author=EMAIL, session=_signed_in(url),
                                 cache_dir=tmp_path / name) for name in ("a", "b")]
    a, b = providers

    async def scenario():
        for p in providers:
            assert await p.connect()
            await p.join_room(room_id)
        await _until(lambda: all(p.room_status(room_id) == "synced" for p in providers))

        mine = a.create_catalog("shared", [room_id])
        a.add_event(mine, CatalogEvent(uuid=str(uuid.uuid4()), start=T0, stop=T0 + HOUR))
        await _until(lambda: _named(b, "shared") is not None and len(b.events(_named(b, "shared"))) == 1)

        a.events(mine)[0].stop = T0 + 3 * HOUR
        a.flush_ranges()
        await _until(lambda: b.events(_named(b, "shared"))[0].stop == T0 + 3 * HOUR)

        b.rename_catalog(_named(b, "shared"), "renamed")
        await _until(lambda: mine.name == "renamed")

        for p in providers:
            await p.close()

    try:
        asyncio.run(scenario())
    finally:
        for p in providers:
            CatalogRegistry.instance()._forget_for_tests(p)


def test_joining_a_room_shows_what_the_server_already_holds(qapp, server, tmp_path):
    url, room_id = server
    seed = CocatRsProvider(author=EMAIL, session=_signed_in(url),
                           cache_dir=tmp_path / "seed")
    late = CocatRsProvider(author=EMAIL, session=_signed_in(url),
                           cache_dir=tmp_path / "late")

    async def scenario():
        assert await seed.connect()
        await seed.join_room(room_id)
        await _until(lambda: seed.room_status(room_id) == "synced")
        catalog = seed.create_catalog("already there", [room_id])
        seed.add_event(catalog, CatalogEvent(uuid=str(uuid.uuid4()), start=T0, stop=T0 + HOUR))
        await asyncio.sleep(0.5)
        await seed.close()

        assert await late.connect()
        await late.join_room(room_id)
        await _until(lambda: _named(late, "already there") is not None
                     and len(late.events(_named(late, "already there"))) == 1)
        await late.close()

    try:
        asyncio.run(scenario())
    finally:
        for p in (seed, late):
            CatalogRegistry.instance()._forget_for_tests(p)


def test_a_new_project_can_be_shared_by_link(qapp, server, tmp_path):
    from SciQLop.plugins.sciqlop_cocat.sharing import ProjectSharing
    url, _ = server
    session = _signed_in(url)
    provider = CocatRsProvider(author=EMAIL, session=session, cache_dir=tmp_path / "cache")

    async def scenario():
        assert await provider.connect()
        info = await provider.create_project("Shared from SciQLop")
        assert info is not None and info.role == "owner"
        await _until(lambda: provider.room_status(info.id) == "synced")
        sharing = ProjectSharing(session, info.id)
        state = await sharing.load()
        assert state.can_manage and [(m["email"], m["role"]) for m in state.members] == [(EMAIL, "owner")]
        created = await sharing.invite("viewer", "")
        assert "/ui/invitation#" in created["link"]
        [invitation] = (await sharing.load()).invitations
        await sharing.revoke(invitation["id"])
        assert (await sharing.load()).invitations == []
        assert state.editors_can_share is True
        await sharing.set_editors_can_share(False)
        assert (await sharing.load()).editors_can_share is False
        await provider.close()

    asyncio.run(scenario())


@pytest.fixture
def no_keyring():
    """cocat-rs then keeps the browser sign-in in memory, away from the real keyring."""
    import keyring
    import keyring.backends.fail
    previous = keyring.get_keyring()
    keyring.set_keyring(keyring.backends.fail.Keyring())
    yield
    keyring.set_keyring(previous)


def _allow_in_browser(url: str, code: str) -> None:
    cookie = cocat_rs.raw.login(url, EMAIL, PASSWORD)
    form = urllib.parse.urlencode({"code": code, "decision": "allow"}).encode()
    request = urllib.request.Request(f"{url}/ui/connect", data=form,
                                     headers={"Cookie": f"fastapiusersauth={cookie}"})
    with urllib.request.urlopen(request) as response:
        assert b"is signed in" in response.read()


def test_signing_in_through_the_browser_connects_as_the_account(qapp, server, tmp_path, no_keyring,
                                                                monkeypatch):
    from SciQLop.plugins.sciqlop_cocat import provider as provider_module
    url, room_id = server
    session = Session(url)
    provider = CocatRsProvider(session=session, cache_dir=tmp_path / "cache")
    monkeypatch.setattr(provider_module, "open_url",
                        lambda link: _allow_in_browser(url, urllib.parse.parse_qs(
                            urllib.parse.urlparse(link).query)["code"][0]))

    async def scenario():
        assert not session.signed_in
        assert await provider.sign_in()
        assert room_id in provider._room_infos
        assert provider._author == EMAIL
        await provider.sign_out()
        assert not session.signed_in

    try:
        with pytest.warns(UserWarning, match="no keyring"):
            asyncio.run(scenario())
    finally:
        CatalogRegistry.instance()._forget_for_tests(provider)


def test_an_editor_demoted_while_joined_can_no_longer_edit(qapp, server, tmp_path):
    from SciQLop.components.catalogs import Capability
    url, room_id = server
    owner = _signed_in(url)
    colleague = CocatRsProvider(session=_signed_in(url, COLLEAGUE), cache_dir=tmp_path / "colleague")

    async def scenario():
        assert await colleague.connect()
        await colleague.join_room(room_id)
        await _until(lambda: colleague.room_status(room_id) == "synced")
        catalog = colleague.create_catalog("shared", [room_id])
        assert Capability.EDIT_EVENTS in colleague.capabilities(catalog)

        members = await owner.call(cocat_rs.raw.members, room_id)
        [colleague_id] = [m["user_id"] for m in members if m["email"] == COLLEAGUE]
        await owner.call(cocat_rs.raw.set_role, room_id, colleague_id, "viewer")

        await _until(lambda: colleague._roles.get(room_id) == "viewer")
        [catalog] = [c for c in colleague.catalogs() if c.name == "shared"]
        assert colleague.capabilities(catalog) == set()
        [all_events] = [c for c in colleague.catalogs() if c.uuid == "all-events:" + room_id]
        assert colleague.capabilities(all_events) == set()
        assert colleague._session.signed_in
        assert colleague.project_state(room_id) == "read-only"
        await colleague.close()

    try:
        asyncio.run(scenario())
    finally:
        CatalogRegistry.instance()._forget_for_tests(colleague)


def test_a_member_removed_while_joined_loses_the_project_but_stays_signed_in(qapp, server, tmp_path):
    url, room_id = server
    owner = _signed_in(url)
    colleague = CocatRsProvider(session=_signed_in(url, COLLEAGUE), cache_dir=tmp_path / "colleague")
    notices = []
    colleague.notice.connect(notices.append)

    async def scenario():
        assert await colleague.connect()
        await colleague.join_room(room_id)
        await _until(lambda: colleague.room_status(room_id) == "synced")

        members = await owner.call(cocat_rs.raw.members, room_id)
        [colleague_id] = [m["user_id"] for m in members if m["email"] == COLLEAGUE]
        await owner.call(cocat_rs.raw.remove_member, room_id, colleague_id)

        await _until(lambda: room_id not in colleague._room_infos)
        assert colleague._session.signed_in
        assert [c for c in colleague.catalogs() if c.path and c.path[0] == room_id] == []
        assert any("no longer" in e for e in notices)
        await colleague.close()

    try:
        asyncio.run(scenario())
    finally:
        CatalogRegistry.instance()._forget_for_tests(colleague)


def test_a_saved_version_can_be_restored(qapp, server, tmp_path):
    from SciQLop.plugins.sciqlop_cocat.history import ProjectHistory
    url, room_id = server
    session = _signed_in(url)
    provider = CocatRsProvider(session=session, cache_dir=tmp_path / "cache")

    async def scenario():
        assert await provider.connect()
        await _until(lambda: provider.room_status(room_id) == "synced")
        catalog = provider.create_catalog("before", [room_id])
        assert await provider.save_version(room_id, "first draft")
        provider.rename_catalog(catalog, "after")
        await asyncio.to_thread(provider._rooms[room_id].save, 10)

        history = ProjectHistory(session, room_id)
        versions = await history.load()
        [saved] = [v for v in versions if v.name == "first draft"]
        assert saved.who == EMAIL
        await history.restore(saved.id)
        await _until(lambda: catalog.name == "before")
        await provider.close()

    try:
        asyncio.run(scenario())
    finally:
        CatalogRegistry.instance()._forget_for_tests(provider)


def _listed(provider, public_id: str) -> dict:
    return next(row for row in provider._public_views.values() if row["id"] == public_id)


@pytest.mark.parametrize("into_new_project", [True, False])
def test_a_public_catalogue_is_copied(qapp, server, tmp_path, monkeypatch, into_new_project):
    from SciQLop.plugins.sciqlop_cocat import questions
    url, room_id = server
    session = _signed_in(url)
    public_id = cocat_rs.raw.create_public_catalogue(url, session.cookie, "Bow shocks", folder="MMS", key="bow")
    public = cocat_rs.Project.open(str(tmp_path / "curator"), public_id)
    public.connect(url, session.cookie)
    public.wait_synced(10)
    shocks = public.create_catalogue(name="Bow shocks", author=EMAIL)
    shocks.add_events([public.create_event(start="2020-01-01T00:00:00Z", stop="2020-01-01T01:00:00Z",
                                           author=EMAIL)])
    public.save(10)
    public.close()
    provider = CocatRsProvider(session=session, cache_dir=tmp_path / "cache")
    monkeypatch.setattr(questions, "ask_choice",
                        lambda title, label, items: items.index("A new project" if into_new_project else "Personal"))

    async def scenario():
        assert await provider.connect()
        await _until(lambda: provider.room_status(room_id) == "synced")
        await provider.copy_public_catalogue(_listed(provider, public_id))
        copied = lambda: next((c for c in provider.catalogs() if c.name == "Bow shocks" and c.path[0] != "public"), None)
        await _until(lambda: copied() is not None and len(provider.events(copied())) == 1)
        copied = copied()
        assert (copied.path[0] != room_id) == into_new_project
        await provider.close()

    try:
        asyncio.run(scenario())
    finally:
        CatalogRegistry.instance()._forget_for_tests(provider)


def test_a_version_is_viewed_as_it_was(qapp, server, tmp_path):
    from SciQLop.plugins.sciqlop_cocat.history import ProjectHistory
    url, room_id = server
    session = _signed_in(url)
    provider = CocatRsProvider(session=session, cache_dir=tmp_path / "cache")

    async def scenario():
        assert await provider.connect()
        await _until(lambda: provider.room_status(room_id) == "synced")
        catalog = provider.create_catalog("before", [room_id])
        provider.add_event(catalog, CatalogEvent(uuid=str(uuid.uuid4()), start=T0, stop=T0 + HOUR))
        assert await provider.save_version(room_id, "first draft")
        provider.rename_catalog(catalog, "after")
        [saved] = [v for v in await ProjectHistory(session, room_id).load() if v.name == "first draft"]
        await provider.view_version(room_id, saved)
        [past] = provider._versions_provider.catalogs()
        assert past.name == "before" and len(provider._versions_provider.events(past)) == 1
        assert catalog.name == "after"
        await provider.close()

    try:
        asyncio.run(scenario())
    finally:
        CatalogRegistry.instance()._forget_for_tests(provider)
        if provider._versions_provider is not None:
            CatalogRegistry.instance()._forget_for_tests(provider._versions_provider)


def test_local_catalogues_move_into_the_account_at_the_first_sign_in(qapp, server, tmp_path, monkeypatch):
    from SciQLop.plugins.sciqlop_cocat import provider as provider_module
    monkeypatch.setattr(provider_module.questions, "ask_move", lambda names, target: True)
    url, _ = server
    here = CocatRsProvider(author=EMAIL, session=_signed_in(url), cache_dir=tmp_path / "here",
                           local_dir=tmp_path / "local")
    elsewhere = CocatRsProvider(author=EMAIL, session=_signed_in(url), cache_dir=tmp_path / "elsewhere")
    providers = [here, elsewhere]

    async def scenario():
        await here.show_signed_out()
        [local_id] = here._room_infos
        made = here.create_catalog("before sign-in", [local_id, "MMS"])
        here.add_event(made, CatalogEvent(uuid=str(uuid.uuid4()), start=T0, stop=T0 + HOUR))
        assert await here.connect()
        own = here._default_room_id
        assert here._room_infos[own].personal and local_id not in here._room_infos
        assert await elsewhere.connect()
        await _until(lambda: (c := _named(elsewhere, "before sign-in")) is not None and len(elsewhere.events(c)) == 1)
        assert _named(elsewhere, "before sign-in").path == [own, "MMS"]
        for p in providers:
            await p.close()

    try:
        asyncio.run(scenario())
    finally:
        for p in providers:
            CatalogRegistry.instance()._forget_for_tests(p)


def test_a_followed_public_catalogue_follows_the_curator_live(qapp, server, tmp_path):
    url, _ = server
    curator = cocat_rs.Client(url)
    curator.login(EMAIL, PASSWORD)
    public_id = curator.create_public_catalogue("Shocks", "MMS")
    published = curator.open(public_id, cache=tmp_path / "curator")
    shocks = published.create_catalogue(name="Shocks", author=EMAIL)
    published.save(10)
    reader = CocatRsProvider(author=COLLEAGUE, session=_signed_in(url, COLLEAGUE), cache_dir=tmp_path / "reader")

    async def scenario():
        assert await reader.connect()
        catalog = next(c for c in reader.catalogs() if reader._public_room_id(c) == public_id)
        assert reader.events(catalog) == [] and reader.is_loading(catalog)  # opening it starts the download
        await _until(lambda: not reader.is_loading(catalog))
        assert reader.capabilities(catalog) == set()
        event = published.create_event(start=T0, stop=T0 + HOUR, author=EMAIL)
        shocks.add_events([event.uuid])
        published.save(10)
        await _until(lambda: len(reader.events(catalog)) == 1)
        await reader.close()

    try:
        asyncio.run(scenario())
    finally:
        published.close()
        CatalogRegistry.instance()._forget_for_tests(reader)


def test_a_link_into_my_catalogues_reaches_my_other_computer(qapp, server, tmp_path):
    url, room_id = server
    here, there = (CocatRsProvider(author=EMAIL, session=_signed_in(url), cache_dir=tmp_path / name)
                   for name in ("here", "there"))
    providers = [here, there]

    async def scenario():
        assert await here.connect()
        await _until(lambda: here.room_status(room_id) == "synced")
        original = here.create_catalog("shocks", [room_id])
        here.add_event(original, CatalogEvent(uuid=str(uuid.uuid4()), start=T0, stop=T0 + HOUR))
        here.link_into_personal(original)
        assert _named(here, "shocks (from Personal)") is not None
        await asyncio.to_thread(here._rooms[here._links_home()].save, 10)
        assert await there.connect()
        await _until(lambda: (v := _named(there, "shocks (from Personal)")) is not None and len(there.events(v)) == 1,
                     timeout=15)
        for p in providers:
            await p.close()

    try:
        asyncio.run(scenario())
    finally:
        for p in providers:
            CatalogRegistry.instance()._forget_for_tests(p)


LIVE_PUBLIC = ["DONKI CMEs", "jet candidates", 'Bow "shocks" ☀']   # one named like a project catalogue
LIVE_PROJECT = ["jet candidates", "Événements 😀"]


@pytest.mark.parametrize("scope", ["This catalogue", "All events", "Public catalogues"])
def test_every_name_completion_offers_reads_in_its_scope(qapp, qtbot, server, tmp_path, scope):
    """Alexis's case: in Public catalogues, catalogue: offered the project's names, which the server's
    search then refused ("No catalogue is named “jet candidates”"). Each scope completes and checks with
    its own names, the public ones read from the server."""
    from .test_search_in import _scopes
    from .test_search_scopes import _accepted, _answered, _offered
    url, room_id = server
    curator = cocat_rs.Client(url)
    curator.login(EMAIL, PASSWORD)
    for name in LIVE_PUBLIC:
        public_id = curator.create_public_catalogue(name, "MMS")
        published = curator.open(public_id, cache=tmp_path / f"curator-{public_id}")
        listed = published.create_catalogue(name=name, author=EMAIL)
        listed.add_events([published.create_event(start=T0, stop=T0 + HOUR, author=EMAIL)])
        published.save(10)
        published.close()
    provider = CocatRsProvider(author=EMAIL, session=_signed_in(url), cache_dir=tmp_path / "reader")

    async def scenario():  # the Qt waits block the loop: the checks ask the server from worker threads
        assert await provider.connect()
        await _until(lambda: provider.room_status(room_id) == "synced")
        made = [provider.create_catalog(name, [room_id]) for name in LIVE_PROJECT]  # empty: names are enough
        box = provider.event_filter(made[0], None)
        qtbot.addWidget(box.widget())
        box.set_events(provider.events(made[0]))
        if scope != "This catalogue":
            _scopes(box)[scope].click()
        public = scope == "Public catalogues"
        suggestions = _offered(qtbot, box, public, LIVE_PUBLIC if public else LIVE_PROJECT)
        for suggestion in suggestions:
            box.line.setPlainText("catalogue:")
            box.line.moveCursor(box.line.textCursor().MoveOperation.End)
            box.line.complete_now()
            _answered(qtbot, box, _accepted(box, suggestion))
            assert box.line.extraSelections() == [], (scope, suggestion, box.problem.text())
            assert "No catalogue is named" not in box.problem.text(), (scope, suggestion)
            if scope != "This catalogue":
                assert box.count.isVisibleTo(box.widget()), (scope, suggestion, box.problem.text())
        box.dispose()
        await provider.close()

    try:
        asyncio.run(scenario())
    finally:
        CatalogRegistry.instance()._forget_for_tests(provider)
