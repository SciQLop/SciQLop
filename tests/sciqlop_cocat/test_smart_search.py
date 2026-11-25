"""What SciQLop knows about a CoCat search, without Qt: the fields it can name, which part of it is
wrong, and what it would hold."""
from datetime import timedelta

import pytest

from SciQLop.plugins.sciqlop_cocat import smart_search as ss

from .conftest import HOUR, T0


@pytest.fixture
def project(room):
    events = [room.create_event(start=T0 + i * HOUR, stop=T0 + (i + 1) * HOUR, author="me",
                                tags=["shock"] if i % 2 else ["wave"], confidence=i / 10,
                                attributes={"density": i * 1.5, "note": f"n{i}"}) for i in range(6)]
    room.create_catalogue(name="Shocks 2019", author="me", events=events[:3])
    return room


def test_fields_are_cocat_s_with_the_project_s_attributes_after(project):
    fields = ss.fields(project)
    names = [f.name for f in fields]
    assert names[:2] == ["start", "stop"] and "tag" in names and "status" in names
    density = next(f for f in fields if f.name == "#density")
    assert (density.label, density.kind) == ("density (attribute)", "attribute")
    assert next(f for f in fields if f.name == "status").values[0] == "preliminary"


def test_a_wrong_search_says_why_and_where(project):
    wrong = ss.problem(project, "auhtor:bob tag:shock")
    assert (wrong.start, wrong.length) == (0, 6)
    assert "did you mean “author”" in wrong.message
    assert ss.problem(project, "tag:shock") is None


def test_a_misspelt_field_is_broken_in_the_filter_and_the_preview_alike(project):
    """cocat-rs 0.12.2+'s query_kind reads "auhtor:bob" as an attribute search; the project refuses it."""
    for answer in (ss.filter_answer(project, "auhtor:bob", [], []), ss.preview_answer(project, "auhtor:bob", None, 5)):
        assert answer.kind == "broken"
        assert (answer.problem.start, answer.problem.length) == (0, 6)
        assert "did you mean “author”" in answer.problem.message


def test_a_problem_with_no_length_underlines_the_word_it_points_at(project):
    wrong = ss.problem(project, "tag:x OR")
    assert wrong.start == 8 and wrong.length >= 1  # past the end: at least one character to see
    number = ss.problem(project, "confidence:>=abc")
    assert (number.start, number.length) == (13, 3)


def test_a_search_in_a_catalogue_is_checked_and_previewed_there(project):
    shocks = next(c for c in project.catalogues() if c.name == "Shocks 2019")
    preview = ss.preview(project, "tag:shock", source=shocks.uuid, limit=10)
    assert preview.count == 1 and len(preview.rows) == 1
    everywhere = ss.preview(project, "tag:shock", limit=2)
    assert everywhere.count == 3 and len(everywhere.rows) == 2
    first = everywhere.rows[0]
    assert first.meta["tags"] == ["shock"] and first.stop - first.start == timedelta(hours=1)
