"""At the first start, the person's tscat catalogues come into their account's own project, or signed
out into the project kept on this computer."""
import asyncio
import json

import pytest

from SciQLop.components.catalogs import CatalogRegistry
from SciQLop.plugins.sciqlop_cocat import provider as provider_module
from SciQLop.plugins.sciqlop_cocat.provider import CocatRsProvider
from SciQLop.plugins.sciqlop_cocat.remembered import Remembered
from SciQLop.plugins.sciqlop_cocat.tscat_import import TscatBusy, TscatUnreadable, read_tscat_database
from .test_provider_rooms import ROOMS, FakeSession, _call_and_settle, opened, run  # noqa: F401
from .tscat_databases import build, edge_cases

EVENT, CATALOGUE = "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222"
SHOCKS = json.dumps({
    "events": [{"start": "2021-03-01T00:00:00", "stop": "2021-03-01T01:00:00", "author": "me", "uuid": EVENT,
                "tags": [], "products": [], "rating": None}],
    "catalogues": [{"name": "Shocks", "author": "me", "uuid": CATALOGUE, "tags": [], "predicate": None,
                    "events": [EVENT]}],
    "removed": [], "members": {CATALOGUE: [EVENT]}})
NOTHING = json.dumps({"events": [], "catalogues": [], "removed": [], "members": {}})


class Tscat:
    """Stands for the tscat database: what reading it gives, and how often it was read."""

    def __init__(self, *answers):
        self.answers, self.reads = list(answers), 0

    async def __call__(self):
        self.reads += 1
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        return answer


@pytest.fixture
def start(qapp, tmp_path, monkeypatch):
    """Starts SciQLop's provider afresh on the same folders: returns it with what it told the person."""
    made = []
    monkeypatch.setattr(provider_module.questions, "ask_move", lambda names, target: False)

    def start(tscat, session=None):
        p = CocatRsProvider(author="me", session=session or FakeSession(signed_in=False),
                            cache_dir=tmp_path / "cache", local_dir=tmp_path / "local", read_tscat=tscat)
        made.append(p)
        p.notices, p.errors = [], []
        p.notice.connect(p.notices.append)
        p.error_occurred.connect(p.errors.append)
        run(p._start())
        return p

    yield start
    for p in made:
        run(p.close())
        CatalogRegistry.instance()._forget_for_tests(p)


def shown(p) -> list[tuple[str, str]]:
    return [(p.folder_display_name(c.path[:1]), c.name) for c in p.catalogs()]


def test_the_first_start_brings_the_tscat_catalogues_into_my_catalogues(start):
    tscat = Tscat(SHOCKS)
    p = start(tscat)
    assert shown(p) == [("My catalogues", "Shocks")]
    assert len(p.events(p.catalogs()[0])) == 1
    assert p.notices == ["1 catalogue(s) and 1 event(s) imported from tscat into My catalogues."]
    assert p.errors == [] and tscat.reads == 1


def test_the_next_starts_do_not_import_again(start):
    tscat = Tscat(SHOCKS)
    run(start(tscat).close())
    again = start(tscat)
    assert shown(again) == [("My catalogues", "Shocks")]
    assert tscat.reads == 1 and again.notices == []


def test_a_catalogue_deleted_after_the_import_does_not_come_back(start):
    tscat = Tscat(SHOCKS)
    p = start(tscat)
    p.remove_catalog(p.catalogs()[0])
    run(p.close())
    assert shown(start(tscat)) == []


def test_without_a_tscat_database_nothing_happens_and_it_is_not_looked_for_again(start):
    tscat = Tscat(None)
    p = start(tscat)
    assert shown(p) == [] and p.notices == [] and p.errors == []
    run(p.close())
    start(tscat)
    assert tscat.reads == 1


def test_an_empty_tscat_database_is_not_announced(start):
    p = start(Tscat(NOTHING))
    assert shown(p) == [] and p.notices == [] and p.errors == []


def test_a_database_that_cannot_be_read_is_said_and_tried_again_at_the_next_start(start):
    tscat = Tscat(TscatUnreadable("database is locked"), SHOCKS)
    p = start(tscat)
    assert p.errors == ["Cannot import your tscat catalogues: database is locked"]
    assert shown(p) == []
    run(p.close())
    again = start(tscat)
    assert shown(again) == [("My catalogues", "Shocks")] and again.errors == []


def test_a_database_another_program_holds_is_said_once_and_tried_again_quietly(start):
    """Only an older SciQLop, or another tscat tool, holds it now: no reason to say it at every start."""
    tscat = Tscat(TscatBusy(), TscatBusy(), SHOCKS)
    first = start(tscat)
    [error] = first.errors
    assert "older SciQLop" in error
    run(first.close())

    second = start(tscat)

    assert second.errors == [] and shown(second) == [] and tscat.reads == 2
    run(second.close())
    third = start(tscat)
    assert shown(third) == [("My catalogues", "Shocks")] and third.errors == []


def test_the_menu_entry_always_says_that_the_database_is_held(start):
    tscat = Tscat(TscatBusy())
    p = start(tscat)
    [local_id] = p._room_infos
    [entry] = [a for a in p.folder_actions([local_id]) if a.name == "Import tscat catalogues"]
    run(_call_and_settle(entry.callback, [local_id]))
    assert len(p.errors) == 2 and p.errors[0] == p.errors[1]


def test_what_did_not_come_across_is_told(start):
    ancient = json.loads(SHOCKS)
    ancient["events"][0]["start"] = "1600-01-01T00:00:00"
    p = start(Tscat(json.dumps(ancient)))
    [notice] = p.notices
    assert notice.startswith("1 catalogue(s) and 0 event(s) imported from tscat into My catalogues. "
                             "1 thing(s) did not come across as they were")
    assert "event 1600-01-01T00:00:00 to 2021-03-01T01:00:00 of Shocks is left out" in notice


@pytest.fixture
def asked(monkeypatch):
    """The offers to move local catalogues into the account, each declined."""
    asked = []
    monkeypatch.setattr(provider_module.questions, "ask_move",
                        lambda names, target: asked.append((names, target)) or False)
    return asked


def test_signed_in_they_go_straight_into_the_account_s_own_project(start, asked):
    p = start(Tscat(SHOCKS), FakeSession(rooms=ROOMS))
    assert shown(p) == [("My catalogues", "Shocks")]
    assert [c.path for c in p.catalogs()] == [["a"]]
    assert p._local_ids == set() and asked == []
    assert p.notices == ["1 catalogue(s) and 1 event(s) imported from tscat into My catalogues."]


def test_signed_in_while_the_server_cannot_be_reached_they_stay_on_this_computer(start, asked):
    session = FakeSession(rooms=ROOMS)
    session.reachable = False
    p = start(Tscat(SHOCKS), session)
    assert shown(p) == [("My catalogues", "Shocks")]
    assert [c.path[0] for c in p.catalogs()] == list(p._local_ids)


def test_imported_signed_out_they_are_offered_to_the_account_at_sign_in(start, asked):
    tscat = Tscat(SHOCKS)
    run(start(tscat).close())
    p = start(tscat, FakeSession(rooms=ROOMS))
    assert asked == [(["My catalogues"], "My catalogues")]
    assert shown(p) == [("On this computer", "Shocks")]


def test_they_are_offered_at_sign_in_even_when_the_move_was_offered_before_the_import(start, asked, tmp_path):
    """The offer is made once per computer: an import that came after it would stay local unasked."""
    Remembered(tmp_path / "local").note_move_offered()
    tscat = Tscat(SHOCKS)
    run(start(tscat).close())
    start(tscat, FakeSession(rooms=ROOMS))
    assert asked == [(["My catalogues"], "My catalogues")]


def test_once_declined_the_move_is_not_offered_again(start, asked):
    tscat = Tscat(SHOCKS)
    run(start(tscat).close())
    run(start(tscat, FakeSession(rooms=ROOMS)).close())
    start(tscat, FakeSession(rooms=ROOMS))
    assert len(asked) == 1


def test_a_provider_given_no_tscat_reader_imports_nothing(qapp, tmp_path):
    p = CocatRsProvider(author="me", session=FakeSession(signed_in=False), cache_dir=tmp_path / "cache",
                        local_dir=tmp_path / "local")
    try:
        run(p._start())
        assert p.catalogs() == []
    finally:
        run(p.close())
        CatalogRegistry.instance()._forget_for_tests(p)


def test_the_menu_entry_imports_into_the_project_it_is_asked_from(start):
    tscat = Tscat(None, SHOCKS)
    p = start(tscat, FakeSession(rooms=ROOMS))
    [entry] = [a for a in p.folder_actions(["a"]) if a.name == "Import tscat catalogues"]
    run(_call_and_settle(entry.callback, ["a"]))
    assert [c.path for c in p.catalogs()] == [["a"]]
    assert p.notices == ["1 catalogue(s) and 1 event(s) imported from tscat into My catalogues."]


def test_the_menu_entry_says_when_there_is_nothing_to_import(start):
    p = start(Tscat(None))
    [local_id] = p._room_infos
    [entry] = [a for a in p.folder_actions([local_id]) if a.name == "Import tscat catalogues"]
    run(_call_and_settle(entry.callback, [local_id]))
    assert p.errors == ["Cannot import your tscat catalogues: there is no tscat catalogue on this computer"]


def test_a_real_tscat_database_comes_in_at_the_first_start(start, tmp_path):
    database, held = build(tmp_path / "tscat", edge_cases)
    p = start(lambda: read_tscat_database(database))
    names = {c["name"] for c in held.catalogues.values() if not c["removed"]}
    assert {c.name for c in p.catalogs()} == names and len(names) == 10
    [a] = [c for c in p.catalogs() if c.name == "Catalogue A"]
    assert len(p.events(a)) == len(held.catalogue("Catalogue A")["members"])
    assert p.errors == []


def test_closing_sciqlop_while_tscat_is_read_leaves_no_start_half_done(qapp, tmp_path):
    """Seen in batch mode: SciQLop quit before the read ended, and the start was destroyed pending."""
    async def never_ends():
        await asyncio.Event().wait()

    p = CocatRsProvider(author="me", session=FakeSession(signed_in=False), cache_dir=tmp_path / "cache",
                        local_dir=tmp_path / "local", read_tscat=never_ends)

    async def start_then_close():
        p.start()
        await asyncio.sleep(0.05)
        starting = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        await p.close()
        return [task.done() for task in starting]  # asked here: asyncio.run ends what is left itself

    try:
        assert run(start_then_close()) == [True]
        assert not Remembered(tmp_path / "local").tscat_imported  # tried again at the next start
    finally:
        CatalogRegistry.instance()._forget_for_tests(p)
