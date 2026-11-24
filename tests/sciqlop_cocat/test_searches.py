"""Smart catalogues made and changed from SciQLop: a search (text, or a rule as JSON) on all events
or on one catalogue, freezing, and removing the search. The tree's menu offers them with the CoCat
web app's words."""
import cocat_rs
import pytest

from SciQLop.components.catalogs import Capability, CatalogEvent

from .conftest import HOUR, T0, loaded


@pytest.fixture
def tagged(attached):
    plain = attached.create_catalog("plain", ["r"])
    for i, tag in enumerate(["s", "s", "w"]):
        attached.add_event(plain, CatalogEvent(uuid=f"e{i}", start=T0 + i * HOUR, stop=T0 + (i + 1) * HOUR,
                                               meta={"tags": [tag]}))
    return plain


def _names(provider, catalog):
    return sorted(e.uuid for e in provider.events(catalog))


def test_a_smart_catalogue_made_from_a_search_holds_what_it_finds(attached, tagged, qtbot):
    smart = attached.create_smart_catalog("shocks", ["r"], "tag:s")
    assert smart in attached.catalogs() and smart.uuid in attached._smart
    assert sorted(e.uuid for e in loaded(attached, smart, qtbot)) == ["e0", "e1"]
    assert attached.catalog_icon(smart) is not None  # the funnel


def test_a_search_can_look_in_one_catalogue_only(attached, tagged, room, qtbot):
    other = attached.create_catalog("other", ["r"])
    attached.add_event(other, CatalogEvent(uuid="o1", start=T0, stop=T0 + HOUR, meta={"tags": ["s"]}))
    smart = attached.create_smart_catalog("in plain", ["r"], "tag:s", source=tagged)
    assert sorted(e.uuid for e in loaded(attached, smart, qtbot)) == ["e0", "e1"]
    search = attached.catalog_search(smart)
    assert (search.query, search.source) == ("tag:s", tagged)


def test_a_wrong_search_makes_nothing_and_says_where(attached, tagged):
    before = len(attached.catalogs())
    with pytest.raises(cocat_rs.QueryError) as wrong:
        attached.create_smart_catalog("bad", ["r"], "auhtor:bob")
    assert wrong.value.suggestion == "author" and len(attached.catalogs()) == before


def test_changing_the_search_changes_what_it_holds(attached, tagged, qtbot):
    smart = attached.create_smart_catalog("shocks", ["r"], "tag:s")
    loaded(attached, smart, qtbot)
    attached.set_catalog_search(smart, "tag:w")
    qtbot.waitUntil(lambda: _names(attached, smart) == ["e2"], timeout=5000)
    assert attached.catalog_search(smart).query == "tag:w"


def test_a_plain_catalogue_given_a_search_becomes_smart(attached, tagged, qtbot):
    target = attached.create_catalog("target", ["r"])
    with qtbot.waitSignal(attached.capabilities_changed, timeout=2000):
        attached.set_catalog_search(target, "tag:w")
    assert Capability.EDIT_EVENTS not in attached.capabilities(target)
    qtbot.waitUntil(lambda: _names(attached, target) == ["e2"], timeout=5000)


def test_a_rule_with_no_text_form_is_set_as_json_and_has_no_search_line(attached, tagged, qtbot):
    smart = attached.create_smart_catalog("shocks", ["r"], "tag:s")
    rule = {"merge": {"filter": {"all": True}, "where": {"contains": ["tags", "s"]}}, "gap": 0}
    attached.set_catalog_search(smart, rule=rule)
    search = attached.catalog_search(smart)
    assert (search.query, search.rule) == (None, rule)
    qtbot.waitUntil(lambda: len(attached.events(smart)) == 1, timeout=5000)  # e0 and e1 merged


def test_a_wrong_rule_is_refused_and_the_search_stays(attached, tagged):
    smart = attached.create_smart_catalog("shocks", ["r"], "tag:s")
    with pytest.raises(ValueError):
        attached.set_catalog_search(smart, rule={"bogus": 1})
    assert attached.catalog_search(smart).query == "tag:s"


def test_removing_the_search_leaves_a_plain_catalogue_of_its_listed_events(attached, tagged, room, qtbot):
    smart = attached.create_smart_catalog("shocks", ["r"], "tag:s")
    room.catalogue(smart.uuid).add_events(["e2"])  # listed by hand, besides what the search picks
    loaded(attached, smart, qtbot)
    attached.remove_catalog_search(smart)
    assert attached.catalog_search(smart) is None
    assert Capability.EDIT_EVENTS in attached.capabilities(smart)
    qtbot.waitUntil(lambda: _names(attached, smart) == ["e2"], timeout=5000)


def test_freezing_makes_a_plain_catalogue_of_what_it_holds_now(attached, tagged, qtbot):
    smart = attached.create_smart_catalog("shocks", ["r"], "tag:s")
    frozen = attached.freeze_catalog(smart, "shocks, frozen")
    assert frozen.path == smart.path and attached.catalog_search(frozen) is None
    assert _names(attached, frozen) == ["e0", "e1"]
    assert attached.catalog_search(smart).query == "tag:s"  # the smart one stays as it is


def _action_names(actions):
    return [a.name for a in actions]


def test_the_menus_use_the_web_app_s_words(attached, tagged):
    smart = attached.create_smart_catalog("shocks", ["r"], "tag:s")
    names = _action_names(attached.actions(smart))
    assert {"Freeze…", "Remove the search…", "Edit as JSON…"} <= set(names)
    assert not {"Edit as JSON…", "Freeze…"} & set(_action_names(attached.actions(tagged)))


def test_a_read_only_project_offers_no_search_actions(attached, tagged, monkeypatch):
    smart = attached.create_smart_catalog("shocks", ["r"], "tag:s")
    monkeypatch.setattr(attached, "_can_write", lambda room_id: False)
    assert not {"Edit as JSON…", "Remove the search…"} & set(_action_names(attached.actions(smart)))


def _run(provider, catalog_or_path, name):
    actions = provider.actions(catalog_or_path) if not isinstance(catalog_or_path, list) \
        else provider.folder_actions(catalog_or_path)
    action = next(a for a in actions if a.name == name)
    return action.callback(catalog_or_path)


def test_edit_as_json_opens_the_rule_editor(attached, tagged, qtbot):
    from SciQLop.plugins.sciqlop_cocat.rule_editor import RuleEditor
    smart = attached.create_smart_catalog("shocks", ["r"], "tag:s")
    dialog = _run(attached, smart, "Edit as JSON…")
    assert isinstance(dialog, RuleEditor) and dialog.isVisible() and not dialog.isModal()
    dialog.close()


def test_freeze_asks_a_name_then_freezes(attached, tagged, monkeypatch):
    from SciQLop.plugins.sciqlop_cocat import searches
    smart = attached.create_smart_catalog("shocks", ["r"], "tag:s")
    monkeypatch.setattr(searches, "ask_text", lambda parent, title, label, text: text)
    _run(attached, smart, "Freeze…")
    frozen = next(c for c in attached.catalogs() if c.name == "shocks (frozen)")
    assert attached.catalog_search(frozen) is None


def test_remove_the_search_asks_first(attached, tagged, monkeypatch):
    from SciQLop.plugins.sciqlop_cocat import searches
    smart = attached.create_smart_catalog("shocks", ["r"], "tag:s")
    asked = []
    monkeypatch.setattr(searches, "confirm", lambda parent, title, question, button: (asked.append(question), False)[1])
    _run(attached, smart, "Remove the search…")
    assert attached.catalog_search(smart) is not None
    assert "keeps the events it lists and stops adding events" in asked[0]
    monkeypatch.setattr(searches, "confirm", lambda *a: True)
    _run(attached, smart, "Remove the search…")
    assert attached.catalog_search(smart) is None
