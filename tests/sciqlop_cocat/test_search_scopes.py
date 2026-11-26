"""Each "Search in" scope completes and checks a search with its own names: the project's catalogues in
"This catalogue" and "All events", the server's public catalogues in "Public catalogues". While the
line has a mistake there is no count and no Save. A capped public preview says so.

The server's public names stand in as a second cocat-rs project holding catalogues of those names:
its completion and its checks are cocat-rs's own. A real server: test_live_server.py."""
import threading

import cocat_rs
import pytest

from SciQLop.components.catalogs import CatalogEvent

from .conftest import HOUR, T0, answer_public_from
from .test_search_filter import _box
from .test_search_in import _scopes

PROJECT_NAMES = ["jet candidates", 'Bow "shocks"', "Événements ☀"]
PUBLIC_NAMES = ["DONKI CMEs", "jet candidates", "Cas 😀 étrange"]
SCOPES = ("This catalogue", "All events", "Public catalogues")


@pytest.fixture
def public_project(public_names):
    for name in PUBLIC_NAMES:
        public_names.create_catalogue(name=name, author="curator")
    return public_names


@pytest.fixture
def named(attached):
    """The project's catalogues with odd names; the first holds one event."""
    made = [attached.create_catalog(name, ["r"]) for name in PROJECT_NAMES]
    attached.add_event(made[0], CatalogEvent(uuid="j0", start=T0, stop=T0 + HOUR, meta={"tags": ["jet"]}))
    return made


@pytest.fixture
def server(attached, named, public_project, monkeypatch):
    """The project's room, answering its public calls from the public names; public previews faked."""
    from SciQLop.plugins.sciqlop_cocat import smart_search
    real_preview = smart_search.preview

    def preview(project, search, source=None, limit=50, public=False):
        if not public:
            return real_preview(project, search, source, limit)
        project.parse_query(search, public=True)  # as cocat-rs does: a name the server lacks is refused
        return smart_search.Preview(1, [])

    monkeypatch.setattr(smart_search, "preview", preview)
    return answer_public_from(attached, public_project, monkeypatch)


def _scoped_box(attached, catalog, qtbot, scope):
    box = _box(attached, catalog, qtbot)
    if scope != "This catalogue":
        _scopes(box)[scope].click()
    return box


def _offered(qtbot, box, public: bool, expected=None):
    """The catalogue names completion offers after catalogue:, once the scope's names have arrived."""
    expected = expected or (PUBLIC_NAMES if public else PROJECT_NAMES)
    box.line.setPlainText("catalogue:")
    box.line.moveCursor(box.line.textCursor().MoveOperation.End)

    def offered():
        box.line.complete_now()
        return box.line.completion_words()

    qtbot.waitUntil(lambda: len(offered()) == len(expected), timeout=3000)
    return offered()


def _answered(qtbot, box, text):
    """Type text and wait for the scope's answer to it: the filter's, or the preview's (or its failure).
    Asked at once, past the typing delay: the background jobs deliver only the last request's answer."""
    jobs = box._worker if box.scope() == "catalogue" else box._previewer
    got = []
    box.line.setPlainText(text)
    box.refilter()
    jobs.done.connect(got.append)
    jobs.failed.connect(got.append)
    try:
        qtbot.waitUntil(lambda: bool(got), timeout=3000)
    finally:
        jobs.done.disconnect(got.append)
        jobs.failed.disconnect(got.append)


# ---- 1. completion per scope ----

def test_completion_offers_the_catalogue_names_of_the_scope(attached, named, server, qtbot):
    box = _box(attached, named[0], qtbot)
    project_words = _offered(qtbot, box, public=False)
    _scopes(box)["Public catalogues"].click()
    public_words = _offered(qtbot, box, public=True)
    assert "DONKI CMEs" in "".join(public_words) and "Événements" not in "".join(public_words)
    _scopes(box)["All events"].click()
    assert _offered(qtbot, box, public=False) == project_words


def test_switching_scope_offers_none_of_the_old_scope_s_names_meanwhile(attached, named, server, qtbot):
    box = _box(attached, named[0], qtbot)
    _offered(qtbot, box, public=False)
    [room] = server.values()
    room.gate = threading.Event()
    _scopes(box)["Public catalogues"].click()
    assert box.line._vocabulary.get("catalogues", []) == []   # not the project's, while the server's are asked
    room.gate.set()
    _offered(qtbot, box, public=True)


def test_a_late_answer_for_a_scope_left_is_dropped(attached, named, server, qtbot):
    box = _box(attached, named[0], qtbot)
    _offered(qtbot, box, public=False)
    [room] = server.values()
    room.gate = threading.Event()
    _scopes(box)["Public catalogues"].click()
    _scopes(box)["All events"].click()
    project = _offered(qtbot, box, public=False)
    room.gate.set()
    qtbot.wait(200)  # the public answer arrives, and must not replace the project's names
    assert sorted(box.line._vocabulary["catalogues"]) == sorted(PROJECT_NAMES)
    assert _offered(qtbot, box, public=False) == project


# ---- 2. the red mark per scope ----

def test_a_public_name_reads_in_the_public_scope_only(attached, named, server, qtbot):
    box = _scoped_box(attached, named[0], qtbot, "Public catalogues")
    _answered(qtbot, box, 'catalogue:"DONKI CMEs"')
    assert not box.problem.isVisibleTo(box.widget()) and box.line.extraSelections() == []
    _answered(qtbot, box, 'catalogue:"Événements ☀"')
    assert box.problem.isVisibleTo(box.widget()) and box.line.extraSelections() != []
    _scopes(box)["All events"].click()
    _answered(qtbot, box, 'catalogue:"DONKI CMEs"')
    assert box.problem.isVisibleTo(box.widget())


def test_a_public_check_that_cannot_be_made_is_said_with_no_count_and_no_save(attached, named, server, qtbot):
    box = _scoped_box(attached, named[0], qtbot, "Public catalogues")
    _answered(qtbot, box, "tag:jet")
    assert box.count.isVisibleTo(box.widget()) and box.save.isVisibleTo(box.widget())
    [room] = server.values()
    room._broken = "the server did not list the public catalogues: try again"
    _answered(qtbot, box, "tag:jets")
    assert box.problem.text() == "The server did not list the public catalogues: try again"
    assert not box.count.isVisibleTo(box.widget()) and not box.save.isVisibleTo(box.widget())


# ---- 3. no count and no Save while the line has a mistake ----

def test_a_mistake_shows_no_count_and_no_save(attached, named, server, qtbot):
    box = _scoped_box(attached, named[0], qtbot, "All events")
    _answered(qtbot, box, "tag:jet")
    assert box.count.text() == "1 event would match" and box.save.isVisibleTo(box.widget())
    _answered(qtbot, box, "tag:jet AND")
    assert box.problem.isVisibleTo(box.widget())
    assert not box.count.isVisibleTo(box.widget()) and not box.save.isVisibleTo(box.widget())
    assert box.revert.isVisibleTo(box.widget())
    _answered(qtbot, box, "tag:jet")
    assert box.count.isVisibleTo(box.widget()) and box.save.isVisibleTo(box.widget())


# ---- 6. a capped public preview ----

def test_a_capped_public_preview_says_only_the_first_events_are_shown(attached, named, server, qtbot, monkeypatch):
    from SciQLop.plugins.sciqlop_cocat import smart_search
    monkeypatch.setattr(smart_search, "preview",
                        lambda project, search, source=None, limit=50, public=False:
                        smart_search.Preview(92649, [], capped=True))
    box = _scoped_box(attached, named[0], qtbot, "Public catalogues")
    _answered(qtbot, box, "start:>2024")
    assert box.count.text().startswith("92,649 events would match")
    assert "only the first" in box.count.text()


def test_the_preview_reads_whether_the_server_capped_it(monkeypatch):
    from SciQLop.plugins.sciqlop_cocat import smart_search
    monkeypatch.setattr(smart_search, "event_rows", lambda found: [])

    class Project:
        def preview(self, search, **_):
            return {"count": 92649, "capped": True}

    assert smart_search.preview(Project(), "start:>2024", public=True).capped


# ---- 7. every name completion offers reads in its scope ----

@pytest.mark.parametrize("scope", SCOPES)
def test_every_name_completion_offers_reads_in_its_scope(attached, named, server, qtbot, scope):
    box = _scoped_box(attached, named[0], qtbot, scope)
    suggestions = _offered(qtbot, box, public=scope == "Public catalogues")
    for suggestion in suggestions:
        box.line.setPlainText("catalogue:")
        box.line.moveCursor(box.line.textCursor().MoveOperation.End)
        box.line.complete_now()
        _answered(qtbot, box, _accepted(box, suggestion))
        assert box.line.extraSelections() == [], (scope, suggestion, box.problem.text())
        assert "No catalogue is named" not in box.problem.text(), (scope, suggestion)


def _accepted(box, suggestion: str) -> str:
    completion = box.line._completion
    taken = next(s for s in completion["suggestions"] if s["insert"] == suggestion)
    text, _ = cocat_rs.accept(box.line.toPlainText(), completion, taken)
    return text

