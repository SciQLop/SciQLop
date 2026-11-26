""""Search in" under the CoCat box, as the web app has it: This catalogue (a filter, nothing saved),
All events (the whole project, becomes the catalogue's own search) and Public catalogues (the server's,
the same way); on a project's "All events", a Public catalogues switch. A text that does not read yet
leaves the table as it was before it."""
import pytest
from PySide6.QtWidgets import QMenu, QWidget

from SciQLop.components.catalogs import CatalogEvent, CatalogSearch

from ..helpers import windows_shown_while
from .conftest import HOUR, T0, answer_public_from, loaded
from .test_search_filter import _box, _browser_on, _type

PUBLIC_ID, PUBLIC_NAME = "pub-1", "DONKI CMEs"


@pytest.fixture
def elsewhere(attached, tagged):
    """An event of the project outside the shown catalogue."""
    other = attached.create_catalog("other", ["r"])
    attached.add_event(other, CatalogEvent(uuid="e3", start=T0 + 5 * HOUR, stop=T0 + 6 * HOUR, meta={"tags": ["w"]}))
    return other


@pytest.fixture
def public_server(attached, public_names, monkeypatch):
    """The server's public catalogues, as cocat-rs would answer: one event of the DONKI CMEs catalogue."""
    from SciQLop.plugins.sciqlop_cocat import smart_search
    from SciQLop.plugins.sciqlop_cocat.convert import EventRow
    real = smart_search.preview
    asked = []

    def preview(project, search, source=None, limit=50, public=False):
        if not public:
            return real(project, search, source, limit)
        asked.append(search)
        row = EventRow("derived:pub", T0, T0 + HOUR, {"public catalogue": PUBLIC_ID}, derived=True)
        return smart_search.Preview(1, [row])

    monkeypatch.setattr(smart_search, "preview", preview)
    monkeypatch.setattr(attached, "_public_views", {"view": {"id": PUBLIC_ID, "name": PUBLIC_NAME}})
    public_names.create_catalogue(name=PUBLIC_NAME, author="curator")
    answer_public_from(attached, public_names, monkeypatch)
    return asked


def _scopes(box):
    return {b.text(): b for b in box._scopes.buttons() if not b.isHidden()}


# ---- the choice ----

def test_a_catalogue_offers_the_three_places_to_search_in(attached, tagged, qtbot):
    box = _box(attached, tagged, qtbot)
    assert list(_scopes(box)) == ["This catalogue", "All events", "Public catalogues"]
    assert box.scope() == "catalogue" and box.mode() == "filter"
    assert not box.public_switch.isVisibleTo(box.widget())


def test_a_smart_catalogue_opens_on_where_its_search_looks(attached, smart, qtbot):
    box = _box(attached, smart, qtbot)
    assert box.scope() == "all" and box.mode() == "search"
    assert _scopes(box)["All events"].isChecked()


def test_a_search_looking_in_a_catalogue_names_it(attached, tagged, qtbot):
    looking = attached.create_smart_catalog("in plain", ["r"], "tag:w", tagged)
    box = _box(attached, looking, qtbot)
    assert box.scope() == "source" and _scopes(box)["In “plain”"].isChecked()


# ---- All events: the whole project, becomes the catalogue's own search ----

def test_all_events_previews_the_whole_project_and_save_makes_it_the_catalogue_s_search(
        attached, tagged, elsewhere, qtbot):
    box = _box(attached, tagged, qtbot)
    _type(qtbot, box, "tag:w")
    assert box.kept() == {"e2"}
    with qtbot.waitSignal(box.shown_events, timeout=3000) as shown:
        _scopes(box)["All events"].click()
    assert box.line.toPlainText() == "tag:w"           # the same text, now searching the project
    assert sorted(e.uuid for e in shown.args[0]) == ["e2", "e3"]
    assert attached.catalog_search(tagged) is None      # nothing saved yet
    with qtbot.waitSignal(box.shown_events, timeout=3000):
        box.save.click()
    saved = attached.catalog_search(tagged)
    assert (saved.query, saved.source, saved.public) == ("tag:w", None, False)
    qtbot.waitUntil(lambda: {"e0", "e1", "e2", "e3"} <= {e.uuid for e in attached.events(tagged)}, timeout=5000)


def test_revert_on_a_catalogue_without_a_search_goes_back_to_filtering(attached, tagged, elsewhere, qtbot):
    box = _box(attached, tagged, qtbot)
    _type(qtbot, box, "tag:w")
    with qtbot.waitSignal(box.shown_events, timeout=3000):
        _scopes(box)["All events"].click()
    with qtbot.waitSignal(box.shown_events, timeout=3000) as back:
        box.revert.click()
    assert back.args == [None] and box.scope() == "catalogue" and box.line.toPlainText() == "tag:w"
    qtbot.waitUntil(lambda: box.kept() == {"e2"}, timeout=3000)


# ---- Public catalogues: the server's, becomes the catalogue's own search ----

def test_public_catalogues_offline_says_to_sign_in_and_leaves_the_table(attached, tagged, qtbot):
    box = _box(attached, tagged, qtbot)
    shown = []
    box.shown_events.connect(shown.append)
    _scopes(box)["Public catalogues"].click()
    box.line.setPlainText("tag:icme")
    qtbot.waitUntil(lambda: box.problem.isVisibleTo(box.widget()), timeout=3000)
    assert box.problem.text() == "Sign in to search the public catalogues."
    assert shown == [] and box.kept() is None


def test_public_catalogues_shows_what_the_server_finds_named_by_its_catalogue(
        attached, tagged, public_server, qtbot, monkeypatch):
    box = _box(attached, tagged, qtbot)
    _scopes(box)["Public catalogues"].click()
    [shown] = _type(qtbot, box, "tag:icme", signal="shown_events")
    assert public_server == ["tag:icme"]
    assert [e.meta["public catalogue"] for e in shown] == [PUBLIC_NAME]
    saved = []
    monkeypatch.setattr(attached, "set_catalog_search", lambda catalog, query=None, source=None, rule=None,
                        public=False: saved.append((catalog, query, source, public)))
    box.save.click()
    assert saved == [(tagged, "tag:icme", None, True)]


def test_a_saved_public_search_opens_on_public_catalogues(attached, smart, qtbot, monkeypatch):
    monkeypatch.setattr(attached, "catalog_search", lambda c: CatalogSearch("tag:icme", None, {}, public=True))
    box = _box(attached, smart, qtbot)
    assert box.scope() == "public" and _scopes(box)["Public catalogues"].isChecked()


def test_a_read_public_catalogue_event_names_its_public_catalogue(attached, monkeypatch):
    from SciQLop.plugins.sciqlop_cocat.convert import rows_of
    import numpy as np
    monkeypatch.setattr(attached, "_public_views", {"view": {"id": PUBLIC_ID, "name": PUBLIC_NAME}})
    times = np.array(["2020-01-01T00:00", "2020-01-01T01:00"], dtype="datetime64[us]")
    [row] = rows_of({"uuid": [None], "start": times[:1], "stop": times[1:], "attributes": [{}],
                     "sources": [["s1"]], "catalogue": [PUBLIC_ID]})
    event = attached._row_event("r", row, {})
    assert event.meta["public catalogue"] == PUBLIC_NAME


# ---- the project's All events: a Public catalogues switch ----

def test_all_events_has_a_public_catalogues_switch(attached, tagged, public_server, qtbot):
    from SciQLop.plugins.sciqlop_cocat.all_events import ALL_EVENTS_PREFIX
    every = attached._catalogs[ALL_EVENTS_PREFIX + "r"]
    box = _box(attached, every, qtbot)
    assert _scopes(box) == {} and box.public_switch.isVisibleTo(box.widget())
    _type(qtbot, box, "tag:s")
    assert box.kept() == {"e0", "e1"}
    with qtbot.waitSignal(box.shown_events, timeout=3000) as shown:
        box.public_switch.click()
    assert [e.meta["public catalogue"] for e in shown.args[0]] == [PUBLIC_NAME]
    assert not box.save.isVisibleTo(box.widget())       # nothing to save: All events has no search
    with qtbot.waitSignal(box.shown_events, timeout=3000) as back:
        box.public_switch.click()
    assert back.args == [None] and box.scope() == "catalogue"
    qtbot.waitUntil(lambda: box.kept() == {"e0", "e1"}, timeout=3000)


# ---- a text that does not read yet ----

def test_a_half_typed_search_leaves_the_table_as_it_was_not_empty(attached, tagged, qtbot):
    box = _box(attached, tagged, qtbot)
    _type(qtbot, box, "B_jump")                          # plain words, on the way to B_jump:>1
    assert box.kept() == set()
    _type(qtbot, box, "B_jump:")                         # does not read
    assert box.kept() is None and box.problem.isVisibleTo(box.widget())
    _type(qtbot, box, "tag:s")
    _type(qtbot, box, "tag:s AND")
    assert box.kept() == {"e0", "e1"} and box.problem.isVisibleTo(box.widget())


def test_a_half_typed_search_of_its_own_ends_a_words_preview(attached, smart, qtbot):
    box = _box(attached, smart, qtbot)
    _type(qtbot, box, "B_jump", signal="shown_events")
    with qtbot.waitSignal(box.shown_events, timeout=3000) as back:
        box.line.setPlainText("B_jump:")
    assert back.args == [None]
    qtbot.waitUntil(lambda: box.problem.isVisibleTo(box.widget()), timeout=3000)
    assert box.revert.isVisibleTo(box.widget())


# ---- in the shown browser ----

def test_search_in_sits_visible_in_the_browser_never_in_windows_of_its_own(
        attached, tagged, smart, elsewhere, qtbot, qapp):
    from SciQLop.plugins.sciqlop_cocat.all_events import ALL_EVENTS_PREFIX
    loaded(attached, smart, qtbot)
    browser = _browser_on(attached, tagged, qtbot)
    browser.show()
    qtbot.waitExposed(browser)
    every = attached._catalogs[ALL_EVENTS_PREFIX + "r"]

    def go_everywhere():
        for scope in ("All events", "Public catalogues", "This catalogue"):
            _scopes(browser._event_filter)[scope].click()
        attached.open_requested.emit(smart)
        attached.open_requested.emit(every)
        browser._event_filter.public_switch.click()
        attached.open_requested.emit(tagged)

    assert windows_shown_while(qapp, go_everywhere) == []
    box = browser._event_filter
    parts = [box.search_in_label, *_scopes(box).values()]
    assert all(part.window() is browser for part in parts)
    qtbot.waitUntil(lambda: all(part.isVisible() for part in parts), timeout=3000)
    assert not [w for w in box.widget().findChildren(QWidget) if w.isWindow() and not isinstance(w, QMenu)]
