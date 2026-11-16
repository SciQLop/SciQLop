"""tscat database -> cocat-rs project: what a project can hold comes through equal to what tscat
says, what it cannot is said in the notes, and the tscat database is never written."""
import asyncio
import hashlib
import shutil
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import cocat_rs
import pytest

from SciQLop.plugins.sciqlop_cocat.tscat_import import (
    TscatUnreadable, import_tscat_text, read_tscat_database,
)
from .tscat_databases import LISTS, PAPER_LIST_SIZES, PAPER_LISTS, build, edge_cases, hours

PROJECT_ID = "75ca7000-0000-4000-8000-000000000000"


def read(database: Path) -> str | None:
    return asyncio.run(read_tscat_database(database))


@pytest.fixture(scope="module")
def filled(tmp_path_factory):
    """The database of every case and of the published lists: its file, what tscat says it holds,
    and its text as read for the import."""
    database, held = build(tmp_path_factory.mktemp("tscat"), edge_cases, *PAPER_LISTS)
    return database, held, read(database)


@pytest.fixture
def project(tmp_path):
    opened = cocat_rs.Project.open(tmp_path / "project", PROJECT_ID)
    yield opened
    opened.close()


@pytest.fixture
def imported(filled, project):
    _, held, text = filled
    return project, held, import_tscat_text(project, text)


def small(tmp_path, write):
    """A database holding only what `write` adds, as read for the import."""
    database, _ = build(tmp_path / "tscat", write)
    return read(database)


def utc(time: datetime) -> datetime:
    return time.replace(tzinfo=timezone.utc)


def as_cocat_holds(value):
    """tscat hands a datetime attribute back as text; a project keeps it as a date."""
    if isinstance(value, str) and value.endswith("+00:00"):
        return datetime.fromisoformat(value)
    return value


def members(catalogue) -> set[str]:
    return {event.uuid for event in catalogue.events}


# ---- what comes through equal ----

def test_every_event_comes_through_as_tscat_has_it(imported):
    project, held, _ = imported
    assert len(held.events) == 8 + sum(PAPER_LIST_SIZES.values())
    for uuid, theirs in held.events.items():
        ours = project.event(uuid)
        assert (ours.start, ours.stop) == (utc(theirs["start"]), utc(theirs["stop"]))
        assert ours.author == (theirs["author"] or None)
        assert ours.tags == set(theirs["tags"]) and ours.products == set(theirs["products"])
        assert ours.confidence == (None if theirs["rating"] is None else theirs["rating"] / 10)
        assert ours.status == ("deleted" if theirs["removed"] else "confirmed")
        assert ours.attributes == {k: as_cocat_holds(v) for k, v in theirs["attributes"].items()}
        assert ours.origin == "tscat"


def test_every_catalogue_comes_through_as_tscat_has_it(imported):
    project, held, _ = imported
    assert len(held.catalogues) == 11 + len(PAPER_LISTS)
    for uuid, theirs in held.catalogues.items():
        ours = project.catalogue(uuid)
        assert ours.name == theirs["name"]
        assert ours.author == (theirs["author"] or None)
        assert ours.tags == set(theirs["tags"])
        assert ours.attributes == theirs["attributes"]
        assert ours.deleted == theirs["removed"]
        assert (ours.rule is not None) == theirs["dynamic"]
        assert members(ours) == theirs["members"], theirs["name"]


def test_the_published_lists_keep_every_row(imported):
    project, held, _ = imported
    for name, size in PAPER_LIST_SIZES.items():
        [catalogue] = [c for c in project.catalogues() if c.name == name]
        assert len(catalogue.events) == size


def test_a_dynamic_catalogue_is_a_smart_one_that_selects_the_same_events(imported):
    project, held, _ = imported
    dynamic = [c for c in held.catalogues.values() if c["dynamic"]]
    assert len(dynamic) == 7 and all(c["members"] for c in dynamic)
    listed_too = held.catalogue("By Toto, and one listed")
    assert len(listed_too["members"]) == 2


def test_an_event_shared_by_two_catalogues_is_one_event(imported):
    project, held, _ = imported
    a, b = (members(next(c for c in project.catalogues() if c.name == name))
            for name in ("Catalogue A", "Catalogue B"))
    [shared] = a & b
    assert project.event(shared).author == "Toto"


def test_what_tscat_removed_is_in_the_trash(imported):
    project, held, _ = imported
    [event] = [uuid for uuid, e in held.events.items() if e["removed"]]
    [catalogue] = [uuid for uuid, c in held.catalogues.items() if c["removed"]]
    assert project.event(event).status == "deleted"
    assert project.catalogue(catalogue).deleted
    assert "In the trash" not in [c.name for c in project.catalogues()]
    assert event not in members(next(c for c in project.catalogues() if c.name == "Catalogue A"))


def test_an_event_in_no_catalogue_is_kept_and_counted(imported):
    project, held, result = imported
    [nobody] = [uuid for uuid, e in held.events.items() if e["author"] == "Nobody"]
    assert project.event(nobody).attributes == {"note": "in no catalogue"}
    assert result.unlisted == 1


def test_the_result_counts_what_was_imported(imported):
    _, held, result = imported
    assert (result.catalogues, result.events) == (len(held.catalogues), len(held.events))
    assert "14 catalogue(s) and 239 event(s) imported from tscat into My catalogues." in \
        result.summary("My catalogues")


# ---- what cannot come across as it was is said ----

def test_an_attribute_holding_two_kinds_of_value_is_said_and_kept(imported):
    project, held, result = imported
    [note] = [n for n in result.notes if "mm_type" in n]
    assert "number" in note and '"1, 2"' in note
    odd = [uuid for uuid, e in held.events.items() if e["attributes"].get("mm_type") == "1, 2"]
    assert len(odd) == 2 and all(project.event(uuid).attributes["mm_type"] == "1, 2" for uuid in odd)
    assert result.notes == (note,)


def test_an_event_outside_the_years_a_project_holds_is_left_out_and_said(tmp_path, project):
    def write(tscat):
        tscat.create_catalogue("History", "me", events=[
            tscat.create_event(datetime(1600, 1, 1), datetime(1600, 1, 2), "me"),
            tscat.create_event(hours(0), datetime(9999, 12, 31), "me"),
            tscat.create_event(hours(0), hours(1), "me")])

    result = import_tscat_text(project, small(tmp_path, write))

    [catalogue] = project.catalogues()
    assert [(e.start, e.stop) for e in catalogue.events] == [(utc(hours(0)), utc(hours(1)))]
    assert result.events == 1 and len(result.notes) == 2
    assert all("History" in note and "1677 to 2262" in note for note in result.notes)
    assert "1600-01-01T00:00:00" in result.notes[0] and "9999-12-31T00:00:00" in result.notes[1]


def test_an_attribute_named_as_cocat_names_its_own_comes_in_renamed_and_said(tmp_path, project):
    def write(tscat):
        tscat.create_catalogue("Shapes", "me", shape_axis="frequency", events=[
            tscat.create_event(hours(0), hours(1), "me", shape="round", size=3)])

    result = import_tscat_text(project, small(tmp_path, write))

    [catalogue] = project.catalogues()
    assert catalogue.attributes == {"tscat_shape_axis": "frequency"}
    assert [e.attributes for e in catalogue.events] == [{"tscat_shape": "round", "size": 3}]
    assert len(result.notes) == 2 and "'shape'" in result.notes[0] and "'shape_axis'" in result.notes[1]


def test_a_predicate_a_rule_cannot_say_is_said_and_keeps_its_events(tmp_path, project):
    def write(tscat):
        from tscat import filtering as f
        tscat.create_event(hours(0), hours(1), "me")
        tscat.create_catalogue("Since 1600", "me",
                               predicate=f.Comparison(">", f.Field("start"), datetime(1600, 1, 1)))

    result = import_tscat_text(project, small(tmp_path, write))

    [catalogue] = project.catalogues()
    assert catalogue.rule is None and len(catalogue.events) == 1
    [note] = result.notes
    assert "Since 1600" in note and "no rule" in note


def test_values_tscat_allows_and_a_project_holds_too(tmp_path, project):
    def write(tscat):
        tscat.create_catalogue("Same name", "me")
        tscat.create_catalogue("Same name", "you", events=[
            tscat.create_event(hours(0), hours(1), "me", nothing=None, items=[1, 2], table={"k": 1})])

    result = import_tscat_text(project, small(tmp_path, write))

    assert sorted(c.author for c in project.catalogues()) == ["me", "you"]
    [event] = [e for c in project.catalogues() for e in c.events]
    assert event.attributes == {"nothing": None, "items": [1, 2], "table": {"k": 1}}
    assert result.notes == ()


# ---- safe to run again ----

def test_importing_again_makes_no_duplicates(imported, filled):
    project, held, first = imported
    again = import_tscat_text(project, filled[2])
    assert (again.catalogues, again.events) == (first.catalogues, first.events)
    assert len(project.catalogues()) == sum(not c["removed"] for c in held.catalogues.values())
    for uuid, theirs in held.catalogues.items():
        assert members(project.catalogue(uuid)) == theirs["members"]


def test_importing_again_brings_what_changed_in_tscat(tmp_path, project):
    def write(tscat):
        tscat.create_catalogue("Shocks", "me", events=[tscat.create_event(hours(0), hours(1), "me")])

    def more(tscat):
        [catalogue] = tscat.get_catalogues()
        catalogue.name = "Bow shocks"
        tscat.add_events_to_catalogue(catalogue, [tscat.create_event(hours(2), hours(3), "me")])

    import_tscat_text(project, small(tmp_path, write))
    import_tscat_text(project, small(tmp_path, more))

    [catalogue] = project.catalogues()
    assert catalogue.name == "Bow shocks" and len(catalogue.events) == 2


# ---- the tscat database itself ----

def fingerprint(folder: Path) -> dict:
    return {path.name: (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
            for path in folder.iterdir()}


def test_reading_leaves_the_database_as_it_was(tmp_path):
    database, _ = build(tmp_path / "tscat", edge_cases)
    before = fingerprint(database.parent)
    assert read(database) is not None
    assert fingerprint(database.parent) == before


def test_a_database_of_an_older_tscat_is_read_without_being_upgraded_in_place(tmp_path, project):
    (tmp_path / "tscat").mkdir()
    database = Path(shutil.copy(LISTS / "tscat_0_2_database.sqlite", tmp_path / "tscat" / "backend.sqlite"))
    before = fingerprint(database.parent)

    result = import_tscat_text(project, read(database))

    assert fingerprint(database.parent) == before
    assert (result.catalogues, result.events) == (2, 2)  # of each, one is in tscat's trash
    [catalogue] = project.catalogues()
    assert catalogue.tags == {"tag1", "#tag2", "", "'as"} and catalogue.rule is not None


def test_a_database_left_with_an_old_version_mark_is_read_all_the_same(tmp_path, project):
    """Seen on a real database: next to its current version, the version table still names the first
    one, and tscat then refuses to open it. The copy is repaired, the database is left as it is."""
    database, held = build(tmp_path / "tscat", edge_cases)
    with closing(sqlite3.connect(database)) as db, db:
        db.execute("INSERT INTO alembic_version VALUES ('0c057a8951ba')")
    before = fingerprint(database.parent)

    result = import_tscat_text(project, read(database))

    assert (result.catalogues, result.events) == (len(held.catalogues), len(held.events))
    assert fingerprint(database.parent) == before


def test_no_database_is_nothing_to_import(tmp_path):
    assert read(tmp_path / "backend.sqlite") is None
    assert list(tmp_path.iterdir()) == []


def test_a_file_tscat_cannot_read_is_an_error_that_says_why(tmp_path):
    (tmp_path / "backend.sqlite").write_text("not a database")
    with pytest.raises(TscatUnreadable, match="not a database"):
        read(tmp_path / "backend.sqlite")
