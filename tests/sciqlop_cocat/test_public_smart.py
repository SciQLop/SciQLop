"""Smart catalogues whose rule searches the public catalogues (cocat-rs 0.10.1): every project is
given the server before its first read, those catalogues are read again on a slow timer since the
public catalogues change with no change here, and without a server their tooltip says to sign in."""
import itertools

import cocat_rs
import pytest

from SciQLop.components.catalogs import CatalogRegistry
from SciQLop.components.catalogs.backend.provider import NodeType
from SciQLop.plugins.sciqlop_cocat import provider as provider_module
from SciQLop.plugins.sciqlop_cocat.provider import PUBLIC_REFRESH_MS, CocatRsProvider
from .test_provider_rooms import ROOMS, FakeSession, RecordingRoom, run

PUBLIC_RULE = {"filter": {"public": True}, "where": {"contains": ["tags", "shock"]}}


_numbers = itertools.count()


class Watched(RecordingRoom):
    """Records the order of the calls this test cares about."""

    def __init__(self, room, calls):
        super().__init__(room)
        self.__dict__["calls"] = calls
        self.__dict__["number"] = next(_numbers)  # not id(): it is reused once a room is freed

    def use_server(self, url, cookie=None):
        self.calls.append(("use_server", self.number, url, cookie))
        self._room.use_server(url, cookie)

    def catalogues(self):
        self.calls.append(("read", self.number))
        return self._room.catalogues()


@pytest.fixture
def calls(monkeypatch):
    recorded = []
    monkeypatch.setattr(provider_module, "open_room",
                        lambda folder, room_id: Watched(cocat_rs.Project.open(folder, room_id), recorded))
    monkeypatch.setattr(provider_module.questions, "ask_move", lambda *a: False)
    return recorded


@pytest.fixture
def make(qapp, tmp_path):
    made = []

    def make(session):
        p = CocatRsProvider(author="me", session=session, cache_dir=tmp_path / "cache", local_dir=tmp_path / "local")
        made.append(p)
        return p

    yield make
    for p in made:
        run(p.close())
        CatalogRegistry.instance()._forget_for_tests(p)


def a_local_project_with_catalogues(make):
    p = make(FakeSession(signed_in=False))
    run(p.show_signed_out())
    p.create_catalog("shocks")
    run(p.close())


def test_a_project_kept_here_is_given_the_server_before_its_first_read(make, calls):
    a_local_project_with_catalogues(make)
    calls.clear()
    run(make(FakeSession(rooms=ROOMS)).connect())
    given = [c[1] for c in calls if c[0] == "use_server" and c[2:] == ("https://h", "token")]
    assert len(given) == 3  # the project kept here, and the two server projects
    for room in given:  # (the sign-in's emptiness check opens and closes the file: not given one)
        mine = [c[0] for c in calls if c[1] == room]
        assert mine.index("use_server") < mine.index("read")


def test_signed_out_no_project_is_given_a_server(make, calls):
    a_local_project_with_catalogues(make)
    assert not [c for c in calls if c[0] == "use_server"]


@pytest.fixture
def with_public_smart(make, calls):
    p = make(FakeSession(signed_in=False))
    run(p.show_signed_out())
    [room_id] = p._room_infos
    plain = p.create_catalog("plain")
    smart = p.create_catalog("everywhere")
    p._rooms[room_id].catalogue(smart.uuid).rule = PUBLIC_RULE
    p.reload_catalog(smart)
    return p, plain, smart


def test_catalogues_searching_the_public_ones_are_known(with_public_smart):
    p, plain, smart = with_public_smart
    assert p._public_smart == {smart.uuid}


def test_they_are_read_again_on_a_slow_timer(with_public_smart, monkeypatch):
    p, plain, smart = with_public_smart
    reread = []
    monkeypatch.setattr(p, "reload_catalog", lambda catalog: reread.append(catalog.name))
    assert p._public_timer.interval() == PUBLIC_REFRESH_MS == 5 * 60 * 1000
    assert p._public_timer.isActive()
    p._public_timer.timeout.emit()
    assert reread == ["everywhere"]


def test_without_a_server_the_tooltip_says_to_sign_in(with_public_smart):
    p, plain, smart = with_public_smart
    tip = p.node_tooltip(NodeType.CATALOG, catalog=smart)
    assert "sign in to search the public catalogues" in tip
    assert "sign in" not in p.node_tooltip(NodeType.CATALOG, catalog=plain)


def test_the_timer_stops_when_no_catalogue_searches_the_public_ones(with_public_smart):
    p, plain, smart = with_public_smart
    p.remove_catalog(smart)
    assert not p._public_timer.isActive()
