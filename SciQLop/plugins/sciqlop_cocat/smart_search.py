"""What SciQLop knows about a CoCat search, without Qt: the fields it can name, which part of it is
wrong, and what it would hold. The words and errors are cocat-rs's, the CoCat web app's own."""
from __future__ import annotations

from dataclasses import dataclass

import cocat_rs

from .convert import DERIVED_PREFIX, EventRow, rows_of as event_rows


@dataclass(frozen=True)
class Field:
    name: str          # as the search writes it: "tag", "#density"
    label: str         # as the web app shows it: "Tag", "density (attribute)"
    kind: str          # cocat-rs's kind of field
    values: tuple = ()  # a choice field's values (status)


@dataclass(frozen=True)
class Problem:
    message: str
    start: int   # characters from 0, where to underline
    length: int


@dataclass(frozen=True)
class Preview:
    count: int               # every event the search holds
    rows: list[EventRow]     # the first of them, in time order


def fields(project) -> list[Field]:
    """cocat-rs's fields, then the project's attributes: one kind for all, as the web app has it,
    offering both text and number tests."""
    fixed = [Field(f["name"], f["label"], f["kind"], tuple(f.get("values", ()))) for f in cocat_rs.query_fields()]
    attributes = [Field(f"#{key}", f"{key} (attribute)", "attribute") for key in sorted(project.attribute_types())]
    return fixed + attributes


def problem(project, text: str, source: str | None = None) -> Problem | None:
    try:
        project.parse_query(text, source=source)
    except cocat_rs.QueryError as error:
        return Problem(_sentence(error.message), error.position, _length(text, error.position, error.length))
    return None


def _length(text: str, position: int, length: int | None) -> int:
    """cocat-rs gives no length for a grammar error: the word it points at, or one character."""
    if length:
        return length
    end = position
    while end < len(text) and not text[end].isspace():
        end += 1
    return max(1, end - position)


def _sentence(text: str) -> str:
    return text[:1].upper() + text[1:]


def preview(project, search, source: str | None = None, limit: int = 50, public: bool = False) -> Preview:
    """What a search (text, or a rule dict) would hold, saving nothing; ``public``: in the public
    catalogues, which the server searches (cocat-rs raises when signed out). Safe off the GUI thread:
    cocat-rs evaluates without the GIL and touches nothing of SciQLop's."""
    found = project.preview(search, source=source, public=public, limit=limit, attributes=True) \
        if not isinstance(search, dict) else project.preview(search, limit=limit, attributes=True)
    return Preview(found["count"], event_rows(found))


def match_items(events) -> list:
    """What Project.matches and filter_words test for each event: its uuid, or the range of an
    interval a rule derived, which has no event behind it."""
    return [(e.start, e.stop) if e.uuid.startswith(DERIVED_PREFIX) else e.uuid for e in events]


def kept_ids(project, kind: str, text: str, items: list, ids: list[str]) -> set[str] | None:
    """The ids a search box text keeps (kind from Project.query_kind): plain words as the web app's
    table filter, a search as a smart catalogue would; None when the text is empty. Safe off the GUI
    thread: cocat-rs tests without the GIL."""
    if kind == "empty":
        return None
    mask = project.filter_words(text, items) if kind == "words" else project.matches(text, items)
    return {i for i, keep in zip(ids, mask) if keep}


@dataclass(frozen=True)
class Answer:
    """What the search box shows for a text, worked out off the GUI thread: reading a text in a
    project reads all of it (about 45 ms on 100 000 events)."""
    kind: str                       # Project.query_kind's
    problem: Problem | None = None  # when broken
    kept: set[str] | None = None    # a filter's
    preview: Preview | None = None  # a smart catalogue's search's


def filter_answer(project, text: str, items: list, ids: list[str]) -> Answer:
    kind = project.query_kind(text)
    if kind == "broken":
        return Answer(kind, problem(project, text))
    return Answer(kind, kept=kept_ids(project, kind, text, items, ids))


def preview_answer(project, text: str, source: str | None, limit: int, public: bool = False) -> Answer:
    kind = project.query_kind(text)
    if kind == "broken":
        return Answer(kind, problem(project, text, source))
    if kind == "empty":
        return Answer(kind)
    return Answer(kind, preview=preview(project, text, source, limit, public=public))
