"""tscat databases for the import tests, written with tscat itself, and what tscat says they hold.

Two kinds of content: published event lists (realistic sizes and attributes, see tscat_lists/), and
the cases tscat's own tests exercise (typed attributes, trash, shared events, dynamic catalogues).
"""
from __future__ import annotations

import csv
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

LISTS = Path(__file__).parent / "tscat_lists"
DAY = datetime(2021, 3, 1)
NO_STOP = ("", "0001-01-01T00:00:00Z")  # how the lists write an event that is a single instant


def hours(n: float) -> datetime:
    return DAY + timedelta(hours=n)


@contextmanager
def tscat_at(folder: Path):
    """tscat on a database of its own, `folder`/backend.sqlite; then back on the one it had."""
    import tscat
    import tscat.base
    import tscat.orm_sqlalchemy as orm
    previous = (orm.user_data_dir, tscat.base._backend)
    orm.user_data_dir = lambda appname: str(folder)
    tscat.base._backend = orm.Backend()
    try:
        yield tscat
        tscat.save()
    finally:
        tscat.base._backend.close()
        orm.user_data_dir, tscat.base._backend = previous


@dataclass
class Held:
    """What tscat says a database holds, by uuid, read after writing it."""
    events: dict[str, dict] = field(default_factory=dict)
    catalogues: dict[str, dict] = field(default_factory=dict)

    def catalogue(self, name: str) -> dict:
        return next(c for c in self.catalogues.values() if c["name"] == name)


def _event_as_dict(event) -> dict:
    return {**event.fixed_attributes(), "attributes": event.variable_attributes(),
            "removed": event.is_removed()}


def _catalogue_as_dict(tscat, catalogue) -> dict:
    return {"name": catalogue.name, "author": catalogue.author, "tags": catalogue.tags,
            "attributes": catalogue.variable_attributes(), "removed": catalogue.is_removed(),
            "dynamic": catalogue.predicate is not None,
            "members": {event.uuid for event in tscat.get_events(catalogue)[0]}}


def held(tscat) -> Held:
    both = (False, True)
    return Held(
        events={e.uuid: _event_as_dict(e) for gone in both for e in tscat.get_events(removed_items=gone)},
        catalogues={c.uuid: _catalogue_as_dict(tscat, c)
                    for gone in both for c in tscat.get_catalogues(removed_items=gone)})


def build(folder: Path, *writers) -> tuple[Path, Held]:
    """A tscat database holding what each writer adds: its file, and what tscat says is in it."""
    with tscat_at(folder) as tscat:
        for write in writers:
            write(tscat)
        tscat.save()
        return folder / "backend.sqlite", held(tscat)


# ---- published event lists ----

def _time(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)


def _value(text: str):
    for read in (int, float):
        try:
            return read(text)
        except ValueError:
            pass
    return text


def _row_event(tscat, row: dict, author: str):
    start = _time(row.pop("start"))
    stop = row.pop("stop")
    attributes = {key: _value(text) for key, text in row.items() if text != ""}
    return tscat.create_event(start, start if stop in NO_STOP else _time(stop), author, **attributes)


def paper_list(file_name: str, author: str):
    """A writer: one catalogue named after the file, an event per row, a column per attribute."""
    def write(tscat) -> None:
        with open(LISTS / file_name, newline="") as rows:
            events = [_row_event(tscat, row, author) for row in csv.DictReader(rows)]
        catalogue = tscat.create_catalogue(Path(file_name).stem, author, tags=["paper"], source=file_name)
        tscat.add_events_to_catalogue(catalogue, events)
    return write


PAPER_LISTS = (
    paper_list("dimmock_2022_mirror_mode_storms.csv", "Dimmock"),
    paper_list("stawarz_2022_turbulence_intervals.csv", "Stawarz"),
    paper_list("fargette_2023_reconnection_exhausts.csv", "Fargette"),
)
PAPER_LIST_SIZES = {"dimmock_2022_mirror_mode_storms": 25, "stawarz_2022_turbulence_intervals": 60,
                    "fargette_2023_reconnection_exhausts": 146}


# ---- the cases tscat's own tests exercise ----

def edge_cases(tscat) -> None:
    from tscat import filtering as f
    typed = tscat.create_event(
        hours(0), hours(1), "Patrick", tags=["tag1", "tag2"], products=["productA", "productB"], rating=7,
        field=2, Field=3, field_with_underscores=2.5, text="str", flag=True, when=datetime(2021, 3, 2, 12),
        accents="é à ü")
    unrated = tscat.create_event(hours(2), hours(3), "Alexis", a=1, b=11, s="World")
    nameless = tscat.create_event(hours(4), hours(5), "", rating=1)
    instant = tscat.create_event(datetime(2000, 1, 1), datetime(2000, 1, 1), "Nicolas",
                                 tags=["Zero_duration_event"], rating=10)
    precise = tscat.create_event(datetime(1969, 7, 20, 20, 17, 40, 123456),
                                 datetime(1969, 7, 21, 2, 56, 15, 654321), "Patrick")
    shared = tscat.create_event(hours(6), hours(7), "Toto", b=10)
    trashed = tscat.create_event(hours(8), hours(9), "Patrick", tags=["gone"], rating=3)
    tscat.create_event(hours(10), hours(11), "Nobody", note="in no catalogue")
    # tscat 0.5.1 reads an InCatalogue predicate back as naming its first catalogue, whatever it
    # stored: "Catalogue A" is made first so that what tscat reports is right.
    a = tscat.create_catalogue("Catalogue A", "Alexis", tags=["tag1", "#tag2"], mission="MMS", order=2)
    b = tscat.create_catalogue("Catalogue B", "Patrick")
    tscat.add_events_to_catalogue(a, [typed, unrated, shared, trashed, instant])
    tscat.add_events_to_catalogue(b, [shared, nameless, precise])
    trashed.remove()
    binned = tscat.create_catalogue("In the trash", "Patrick")
    tscat.add_events_to_catalogue(binned, [unrated])
    binned.remove()
    tscat.create_catalogue("Empty", "")
    tscat.create_catalogue("By Patrick", "Patrick", predicate=f.Comparison("==", f.Field("author"), "Patrick"))
    with_listed = tscat.create_catalogue("By Toto, and one listed", "Patrick",
                                         predicate=f.Comparison("==", f.Field("author"), "Toto"))
    tscat.add_events_to_catalogue(with_listed, [unrated])
    tscat.create_catalogue("Well rated", "Patrick", predicate=f.Comparison(">=", f.Field("rating"), 7))
    tscat.create_catalogue("After the second hour", "Patrick",
                           predicate=f.Comparison(">", f.Field("start"), hours(2)))
    tscat.create_catalogue("Late attribute", "Patrick",
                           predicate=f.Comparison(">", f.Attribute("when"), datetime(2021, 3, 1)))
    tscat.create_catalogue("Every node", "Patrick", predicate=f.Any(
        f.All(f.Has(f.Attribute("b")), f.Not(f.Comparison("<", f.Attribute("b"), 11))),
        f.Match(f.Field("author"), "^Nic"),
        f.In("tag1", f.Field("tags")),
        f.All(f.InCatalogue(a), f.Comparison("==", f.Attribute("b"), 10))))
    tscat.create_catalogue("In no catalogue", "Patrick", predicate=f.InCatalogue(None))
