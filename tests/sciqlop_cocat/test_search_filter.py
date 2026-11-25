"""The CoCat search box above a cocat-rs catalogue's events: the cocat-rs search language and the web
app's plain words as a live filter, errors in plain words, presets, "Save as smart catalogue…", and a
smart catalogue's own search edited in place ("Its search": preview, Save changes, Revert)."""
import cocat_rs
import pytest

from SciQLop.components.catalogs import CatalogEvent

from .conftest import HOUR, T0, loaded


@pytest.fixture
def tagged(attached):
    plain = attached.create_catalog("plain", ["r"])
    for i, tag in enumerate(["s", "s", "w"]):
        attached.add_event(plain, CatalogEvent(uuid=f"e{i}", start=T0 + i * HOUR, stop=T0 + (i + 1) * HOUR,
                                               meta={"tags": [tag]}))
    return plain


def _box(provider, catalog, qtbot):
    box = provider.event_filter(catalog, None)
    qtbot.addWidget(box.widget())
    box.set_events(loaded(provider, catalog, qtbot))
    return box


def _type(qtbot, box, text, signal="changed"):
    with qtbot.waitSignal(getattr(box, signal), timeout=3000) as blocker:
        box.line.setPlainText(text)
    return blocker.args


def _wait_problem(qtbot, box, text):
    box.line.setPlainText(text)
    qtbot.waitUntil(lambda: box.problem.isVisibleTo(box.widget()), timeout=3000)


# ---- any cocat-rs catalogue: the live filter ----

def test_a_cocat_catalogue_gets_the_cocat_search_box(attached, tagged, qtbot):
    from SciQLop.plugins.sciqlop_cocat.search_filter import CocatSearchFilter
    box = _box(attached, tagged, qtbot)
    assert isinstance(box, CocatSearchFilter)
    assert box.line.placeholderText() == "Filter or search: tag:shock confidence:>=0.7"
    assert box.kept() is None


def test_a_search_keeps_what_it_matches(attached, tagged, qtbot):
    box = _box(attached, tagged, qtbot)
    _type(qtbot, box, "tag:s")
    assert box.kept() == {"e0", "e1"}


def test_plain_words_filter_as_the_web_app_s_table(attached, tagged, qtbot):
    box = _box(attached, tagged, qtbot)
    _type(qtbot, box, "w")
    assert box.kept() == {"e2"}
    _type(qtbot, box, "")
    assert box.kept() is None


def test_a_broken_search_says_why_and_keeps_the_last_filter(attached, tagged, qtbot):
    box = _box(attached, tagged, qtbot)
    _type(qtbot, box, "tag:s")
    _wait_problem(qtbot, box, "auhtor:me")
    assert "did you mean “author”" in box.problem.text()
    [wrong] = box.line.extraSelections()
    assert (wrong.cursor.selectionStart(), wrong.cursor.selectionEnd()) == (0, 6)
    assert box.kept() == {"e0", "e1"}
    _type(qtbot, box, "tag:w")
    assert not box.problem.isVisibleTo(box.widget()) and box.line.extraSelections() == []


def test_completion_knows_the_project(attached, tagged, qtbot):
    box = _box(attached, tagged, qtbot)
    qtbot.waitUntil(lambda: bool(box.line._vocabulary.get("tags")), timeout=3000)  # read in the background
    box.line.setPlainText("tag:")
    box.line.moveCursor(box.line.textCursor().MoveOperation.End)
    box.line.complete_now()
    assert {"tag:s ", "tag:w "} <= set(box.line.completion_words())


def test_the_presets_fill_the_box(attached, tagged, qtbot):
    box = _box(attached, tagged, qtbot)
    menu = box.presets.menu()
    assert [a.text() for a in menu.actions()] == [p["name"] for p in cocat_rs.presets("me")]
    next(a for a in menu.actions() if a.text() == "Low confidence").trigger()
    assert box.line.toPlainText() == "confidence:<0.5"


def test_a_derived_interval_is_tested_by_its_range(attached, tagged, qtbot):
    merged = attached.create_smart_catalog("merged", ["r"], "tag:s")
    rule = {"merge": {"filter": {"all": True}, "where": {"contains": ["tags", "s"]}}, "gap": 0}
    attached.set_catalog_search(merged, rule=rule)
    qtbot.waitUntil(lambda: len(attached.events(merged)) == 1, timeout=5000)
    [interval] = attached.events(merged)                     # e0 and e1 merged: two hours
    box = _box(attached, merged, qtbot)
    box.show_filter()
    _type(qtbot, box, "duration:>1h")
    assert box.kept() == {interval.uuid}
    _type(qtbot, box, "duration:>3h")
    assert box.kept() == set()


# ---- Save as smart catalogue… ----

def test_save_as_smart_catalogue_is_offered_once_the_text_reads(attached, tagged, qtbot):
    box = _box(attached, tagged, qtbot)
    assert not box.save_as.isVisibleTo(box.widget())
    _type(qtbot, box, "tag:s")
    assert box.save_as.isVisibleTo(box.widget())
    _wait_problem(qtbot, box, "tag:")
    assert not box.save_as.isVisibleTo(box.widget())


def test_save_as_smart_catalogue_makes_it_and_opens_it(attached, tagged, qtbot, monkeypatch):
    from SciQLop.plugins.sciqlop_cocat import search_filter
    box = _box(attached, tagged, qtbot)
    _type(qtbot, box, "tag:s")
    monkeypatch.setattr(search_filter, "ask_smart_catalogue", lambda parent, name, can_look_in: ("shocks", True))
    with qtbot.waitSignal(attached.open_requested, timeout=3000) as opened:
        box.save_as.click()
    [made] = opened.args
    assert made.name == "shocks" and made.path == tagged.path
    search = attached.catalog_search(made)
    assert (search.query, search.source) == ("tag:s", tagged)


def test_from_all_events_the_new_search_looks_at_every_event(attached, tagged, qtbot, monkeypatch):
    from SciQLop.plugins.sciqlop_cocat import search_filter
    view = next(c for c in attached.catalogs() if c.name == "All events")
    box = _box(attached, view, qtbot)
    _type(qtbot, box, "tag:w")
    asked = {}

    def ask(parent, name, can_look_in):
        asked["can_look_in"] = can_look_in
        return "w", True

    monkeypatch.setattr(search_filter, "ask_smart_catalogue", ask)
    with qtbot.waitSignal(attached.open_requested, timeout=3000) as opened:
        box.save_as.click()
    assert asked["can_look_in"] is False
    assert attached.catalog_search(opened.args[0]).source is None


def test_a_read_only_project_offers_no_save_as(attached, tagged, qtbot, monkeypatch):
    monkeypatch.setattr(attached, "_can_write", lambda room_id: False)
    box = _box(attached, tagged, qtbot)
    _type(qtbot, box, "tag:s")
    assert box.kept() == {"e0", "e1"} and not box.save_as.isVisibleTo(box.widget())


# ---- a smart catalogue: its search, edited in place ----

@pytest.fixture
def smart(attached, tagged):
    return attached.create_smart_catalog("shocks", ["r"], "tag:s")


def test_a_smart_catalogue_opens_on_its_search(attached, smart, qtbot):
    box = _box(attached, smart, qtbot)
    assert box.mode() == "search" and box.line.toPlainText() == "tag:s"
    assert box.kept() is None
    assert not box.save.isVisibleTo(box.widget()) and not box.revert.isVisibleTo(box.widget())


def test_editing_its_search_previews_what_it_would_hold(attached, smart, qtbot):
    box = _box(attached, smart, qtbot)
    [shown] = _type(qtbot, box, "tag:w", signal="shown_events")
    assert [e.uuid for e in shown] == ["e2"]
    assert box.count.text() == "1 event would match"
    assert box.save.isVisibleTo(box.widget()) and box.revert.isVisibleTo(box.widget())
    assert box.kept() is None
    assert attached.catalog_search(smart).query == "tag:s"   # nothing saved yet


def test_save_changes_saves_the_search(attached, smart, qtbot):
    box = _box(attached, smart, qtbot)
    _type(qtbot, box, "tag:w", signal="shown_events")
    with qtbot.waitSignal(box.shown_events, timeout=3000) as back:
        box.save.click()
    assert back.args == [None]
    assert attached.catalog_search(smart).query == "tag:w"
    assert not box.save.isVisibleTo(box.widget())
    qtbot.waitUntil(lambda: [e.uuid for e in attached.events(smart)] == ["e2"], timeout=5000)


def test_revert_gives_the_saved_search_back(attached, smart, qtbot):
    box = _box(attached, smart, qtbot)
    _type(qtbot, box, "tag:w", signal="shown_events")
    with qtbot.waitSignal(box.shown_events, timeout=3000) as back:
        box.revert.click()
    assert back.args == [None] and box.line.toPlainText() == "tag:s"
    assert not box.count.isVisibleTo(box.widget())


def test_filter_narrows_what_it_holds_without_changing_it(attached, smart, qtbot):
    attached.set_catalog_search(smart, "tag:s OR tag:w")
    qtbot.waitUntil(lambda: len(attached.events(smart)) == 3, timeout=5000)
    box = _box(attached, smart, qtbot)
    box.show_filter()
    assert box.mode() == "filter" and box.line.toPlainText() == ""
    _type(qtbot, box, "tag:w")
    assert box.kept() == {"e2"} and attached.catalog_search(smart).query == "tag:s OR tag:w"
    box.show_search()
    assert box.line.toPlainText() == "tag:s OR tag:w" and box.kept() is None


def test_a_rule_with_no_text_form_offers_edit_as_json(attached, smart, qtbot):
    rule = {"merge": {"filter": {"all": True}, "where": {"contains": ["tags", "s"]}}, "gap": 0}
    attached.set_catalog_search(smart, rule=rule)
    box = _box(attached, smart, qtbot)
    assert box.no_text.isVisibleTo(box.widget()) and not box.line.isVisibleTo(box.widget())
    assert "This search has no text form" in box.no_text.text()
    from SciQLop.plugins.sciqlop_cocat.rule_editor import RuleEditor
    box.edit_json.click()
    [dialog] = attached._open_dialogs
    assert isinstance(dialog, RuleEditor)
    dialog.close()


def test_a_read_only_project_shows_its_search_without_editing_it(attached, smart, qtbot, monkeypatch):
    monkeypatch.setattr(attached, "_can_write", lambda room_id: False)
    box = _box(attached, smart, qtbot)
    assert box.line.toPlainText() == "tag:s" and box.line.isReadOnly()
    box.show_filter()
    assert not box.line.isReadOnly()


def test_its_mode_and_filter_are_remembered(attached, smart, qtbot):
    box = _box(attached, smart, qtbot)
    box.show_filter()
    _type(qtbot, box, "tag:s")
    state = box.state()
    again = _box(attached, smart, qtbot)
    again.restore(state)
    assert again.mode() == "filter" and again.line.toPlainText() == "tag:s"
    qtbot.waitUntil(lambda: again.kept() == {"e0", "e1"}, timeout=3000)


def test_focus_goes_to_its_search(attached, smart, qtbot):
    box = _box(attached, smart, qtbot)
    box.show_filter()
    box.focus()
    assert box.mode() == "search"


# ---- the tree, and Python ----

def _action(actions, name):
    return next(a for a in actions if a.name == name)


def test_new_smart_catalogue_offers_the_presets_and_opens_the_one_made(attached, qtbot):
    presets = [a for a in attached.folder_actions(["r"]) if a.group == "New smart catalogue"]
    assert [a.name for a in presets] == [p["name"] for p in cocat_rs.presets("me")]
    with qtbot.waitSignal(attached.open_requested, timeout=3000) as opened:
        _action(presets, "Mine").callback(["r"])
    [made] = opened.args
    assert made.name == "Mine" and attached.catalog_search(made).query == "author:=me"


def test_edit_search_opens_its_box(attached, smart, qtbot):
    with qtbot.waitSignal(attached.open_requested, timeout=3000) as opened:
        _action(attached.actions(smart), "Edit search…").callback(smart)
    assert opened.args == [smart]


def test_a_read_only_project_offers_no_new_smart_catalogue(attached, monkeypatch):
    monkeypatch.setattr(attached, "_can_write", lambda room_id: False)
    assert not [a for a in attached.folder_actions(["r"]) if a.group == "New smart catalogue"]


def test_catalogs_filter_speaks_cocat(attached, tagged, qtbot):
    loaded(attached, tagged, qtbot)
    assert [e.uuid for e in attached.filter_events(tagged, "tag:s")] == ["e0", "e1"]
    assert [e.uuid for e in attached.filter_events(tagged, "w")] == ["e2"]
    assert len(attached.filter_events(tagged, "")) == 3
    with pytest.raises(cocat_rs.QueryError):
        attached.filter_events(tagged, "auhtor:me")


# ---- in the catalog browser ----

def _browser_on(provider, catalog, qtbot):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    provider.open_requested.emit(catalog)
    assert browser._current_catalog is catalog
    return browser


def test_the_browser_previews_its_search_then_shows_what_it_saved(attached, smart, qtbot):
    from SciQLop.plugins.sciqlop_cocat.search_filter import CocatSearchFilter
    loaded(attached, smart, qtbot)
    browser = _browser_on(attached, smart, qtbot)
    box = browser._event_filter
    assert isinstance(box, CocatSearchFilter)
    _type(qtbot, box, "tag:w", signal="shown_events")
    assert [browser._event_model.event_at(r).uuid for r in range(browser._event_model.rowCount())] == ["e2"]
    box.save.click()
    qtbot.waitUntil(lambda: [browser._event_model.event_at(r).uuid
                             for r in range(browser._event_model.rowCount())] == ["e2"]
                    and not browser._previewing, timeout=5000)


# ---- what reads the whole project runs off the GUI thread ----

class _Recording:
    """The project, noting the thread of the calls that read all of it."""
    SLOW = {"query_kind", "parse_query", "vocabulary", "matches", "filter_words", "preview"}

    def __init__(self, room):
        self._room, self.on_gui_thread = room, []

    def __getattr__(self, name):
        import threading
        found = getattr(self._room, name)
        if name not in self.SLOW:
            return found

        def call(*args, **kwargs):
            if threading.current_thread() is threading.main_thread():
                self.on_gui_thread.append(name)
            return found(*args, **kwargs)
        return call


def test_the_box_reads_the_project_off_the_gui_thread(attached, tagged, qtbot, monkeypatch):
    smart = attached.create_smart_catalog("shocks", ["r"], "tag:s")
    recording = _Recording(attached._rooms["r"])
    monkeypatch.setattr(attached, "_room_of", lambda catalog: recording)
    plain = _box(attached, tagged, qtbot)
    qtbot.waitUntil(lambda: bool(plain.line._vocabulary.get("tags")), timeout=3000)
    _type(qtbot, plain, "tag:s")
    _wait_problem(qtbot, plain, "auhtor:me")
    box = _box(attached, smart, qtbot)
    _type(qtbot, box, "tag:w", signal="shown_events")
    assert recording.on_gui_thread == []
