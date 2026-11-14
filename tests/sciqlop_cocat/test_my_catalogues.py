"""'My catalogues': on this computer before any sign-in, the account's own project after."""
import asyncio

import cocat_rs
import pytest

from SciQLop.components.catalogs import CatalogEvent, CatalogRegistry
from SciQLop.components.catalogs.backend.provider import NodeType
from SciQLop.plugins.sciqlop_cocat import provider as provider_module
from SciQLop.plugins.sciqlop_cocat.provider import CocatRsProvider
from .conftest import HOUR, T0
from .test_provider_rooms import ROOMS, FakeSession, RecordingRoom, opened, run  # noqa: F401

SIGNED_OUT_ACTIONS = ["Sign in…", "Open CoCat in browser"]


@pytest.fixture
def make(qapp, tmp_path):
    made = []

    def make(session):
        p = CocatRsProvider(author="me", session=session, cache_dir=tmp_path / "cache",
                            local_dir=tmp_path / "local")
        made.append(p)
        return p

    yield make
    for p in made:
        run(p.close())
        CatalogRegistry.instance()._forget_for_tests(p)


@pytest.fixture
def answers(monkeypatch):
    asked = []

    def answer(reply):
        def ask(names, target):
            asked.append((names, target))
            return reply
        monkeypatch.setattr(provider_module.questions, "ask_move", ask)
    answer(False)
    return answer, asked


def local_with_shocks(make):
    """A signed-out first start, with one catalogue made there; returns the provider and its project id."""
    p = make(FakeSession(signed_in=False, rooms=ROOMS))
    run(p.show_signed_out())
    [local_id] = p._room_infos
    catalog = p.create_catalog("shocks", [local_id, "MMS"])
    p.add_event(catalog, CatalogEvent(uuid="e1", start=T0, stop=T0 + HOUR))
    return p, local_id, catalog


def test_a_first_start_signed_out_has_my_catalogues_on_this_computer(make, opened):
    p = make(FakeSession(signed_in=False))
    run(p.show_signed_out())
    [project] = p._room_infos.values()
    assert project.name == "My catalogues"
    assert p.folder_display_name([project.id]) == "My catalogues (default)"
    assert p.create_catalog("shocks").path == [project.id]
    assert opened[project.id].connected_with is None
    assert [a.name for a in p.actions()] == SIGNED_OUT_ACTIONS
    assert p.node_icon(NodeType.FOLDER, [project.id]) is None
    assert p.name == "Catalogs (cocat-rs)"


def test_local_catalogues_survive_a_restart(make):
    p, local_id, _ = local_with_shocks(make)
    run(p.close())
    again = make(FakeSession(signed_in=False))
    run(again.show_signed_out())
    [kept] = again.catalogs()
    assert list(again._room_infos) == [local_id]
    assert kept.path == [local_id, "MMS"] and len(again.events(kept)) == 1


def test_the_first_sign_in_moves_local_catalogues_to_the_account(make, opened, answers, tmp_path):
    answer, asked = answers
    answer(True)
    p, local_id, catalog = local_with_shocks(make)
    p._session.signed_in = True
    run(p.connect())
    assert asked == [(["My catalogues"], "My catalogues")]
    assert list(p._room_infos) == ["a", "b"]
    [moved] = [c for c in p.catalogs() if c.uuid == catalog.uuid]
    assert moved.path == ["a", "MMS"] and [e.uuid for e in p.events(moved)] == ["e1"]
    assert not list((tmp_path / "local").glob(f"{local_id}.*"))
    run(p.reconnect())
    assert len(asked) == 1


def test_declined_local_catalogues_stay_and_can_move_later(make, answers):
    _, asked = answers
    p, local_id, catalog = local_with_shocks(make)
    p._session.signed_in = True
    run(p.connect())
    assert p.folder_display_name([local_id]) == "My catalogues (on this computer)"
    assert [a.name for a in p.folder_actions([local_id])][0] == "Move into My catalogues"
    run(p.reconnect())
    assert len(asked) == 1
    p.folder_actions([local_id])[0].callback([local_id])
    assert local_id not in p._room_infos
    assert [c.path for c in p.catalogs() if c.uuid == catalog.uuid] == [["a", "MMS"]]


def test_an_empty_local_project_is_dropped_at_sign_in(make, answers, opened):
    _, asked = answers
    p = make(FakeSession(signed_in=False, rooms=ROOMS))
    run(p.show_signed_out())
    [local_id] = p._room_infos
    p._session.signed_in = True
    run(p.connect())
    assert asked == [] and local_id not in p._room_infos
    assert local_id not in opened or opened[local_id].connected_with is None


def test_signing_out_keeps_the_account_copy_offline(make, opened):
    p = make(FakeSession(rooms=ROOMS))
    run(p.connect())
    catalog = p.create_catalog("kept", ["a"])
    run(p.sign_out())
    assert list(p._room_infos) == ["a"]
    assert p.folder_display_name(["a"]) == "My catalogues (default)"
    assert [c.uuid for c in p.catalogs()] == [catalog.uuid]
    assert [a.name for a in p.actions()] == SIGNED_OUT_ACTIONS
    assert p.create_catalog("offline").path == ["a"]


def test_a_start_after_an_account_shows_its_copy_not_a_new_local_project(make, opened):
    p = make(FakeSession(rooms=ROOMS))
    run(p.connect())
    run(p.close())
    again = make(FakeSession(signed_in=False, rooms=ROOMS))
    run(again.show_signed_out())
    assert list(again._room_infos) == ["a"]
    assert opened["a"].connected_with is None


def test_my_catalogues_cannot_be_shared(make):
    p = make(FakeSession(rooms=ROOMS))
    run(p.connect())
    assert "Sharing…" not in [a.name for a in p.folder_actions(["a"])]
    assert "Sharing…" in [a.name for a in p.folder_actions(["b"])]


def test_a_failed_move_keeps_the_local_project(make, answers, monkeypatch):
    answer, _ = answers
    answer(True)
    p, local_id, _ = local_with_shocks(make)
    errors = []
    p.error_occurred.connect(errors.append)

    def refuse(self, source):
        raise RuntimeError("full")
    monkeypatch.setattr(RecordingRoom, "merge", refuse, raising=False)
    p._session.signed_in = True
    run(p.connect())
    assert local_id in p._room_infos and "full" in errors[-1]
