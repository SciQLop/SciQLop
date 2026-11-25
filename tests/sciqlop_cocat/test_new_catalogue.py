"""The tree's New menu on cocat-rs: Catalogue, Smart catalogue…, Folder in My catalogues, a project and a folder in
it; Project… on the sections; nothing on a read-only project. The catalogue goes where it was asked. The tree
made the creation rows when it first placed a project, from the project list, before it was joined and writable."""
import cocat_rs
import pytest

from SciQLop.components.catalogs.backend.provider import Section

from ..helpers import windows_shown_while
from .test_provider_rooms import FakeSession, make_provider, opened, run  # noqa: F401

ROOMS = [cocat_rs.ProjectInfo("a", "My catalogues", "owner", personal=True),
         cocat_rs.ProjectInfo("t", "Team", "editor"), cocat_rs.ProjectInfo("b", "Theirs", "viewer")]


@pytest.fixture
def browser(make_provider, qtbot):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    p = make_provider(FakeSession(rooms=ROOMS))
    view = CatalogBrowser()
    qtbot.addWidget(view)
    run(p.connect())
    p.create_catalog("x", ["t", "sub"])
    return view, p


def _nodes(view, p):
    model = view._tree_model
    team = model._containers[(p, "t")]
    return {"My catalogues": model._containers[(p, "a")], "Team": team,
            "Team/sub": next(c for c in team.children if c.name == "sub"), "Theirs": model._containers[(p, "b")]}


def _new(view, node):
    model = view._tree_model
    menu = view._build_tree_context_menu(view._proxy_model.mapFromSource(model.createIndex(node.row(), 0, node)))
    found = [a.menu() for a in menu.actions() if a.menu() is not None and a.text() == "New"] if menu else []
    return [a.text() for a in found[0].actions()] if found else None


def test_the_new_menu_offers_what_each_place_takes(browser, qapp):
    view, p = browser
    nodes = _nodes(view, p)
    assert nodes["My catalogues"].section == Section.MINE
    menus = {}
    assert windows_shown_while(qapp, lambda: menus.update({k: _new(view, n) for k, n in nodes.items()})) == []
    assert menus["My catalogues"] == ["Catalogue", "Smart catalogue…", "Folder", "Project…"]
    assert menus["Team"] == menus["Team/sub"] == ["Catalogue", "Smart catalogue…", "Folder"]
    assert menus["Theirs"] is None
    shared = view._tree_model._containers[(p, "t")].parent
    assert _new(view, shared) == ["Project…"]


def test_a_new_catalogue_goes_where_it_was_asked(browser):
    from PySide6.QtCore import Qt
    from SciQLop.components.catalogs.ui.catalog_tree import _PlaceholderType
    view, p = browser
    model = view._tree_model
    for place, name, path in (("My catalogues", "mine", ["a"]), ("Team", "ours", ["t"]),
                              ("Team/sub", "deeper", ["t", "sub"])):
        row = next(c for c in _nodes(view, p)[place].children if c.placeholder_type == _PlaceholderType.CATALOG)
        assert row.name == "New catalogue…"
        assert model.setData(model.createIndex(row.row(), 0, row), name, Qt.ItemDataRole.EditRole)
        [made] = [c for c in p.catalogs() if c.name == name]
        assert list(made.path) == path, place


def test_new_smart_catalogue_is_made_there_and_its_box_searches_all_events(browser, qtbot):
    view, p = browser
    team = _nodes(view, p)["Team"]
    model = view._tree_model
    menu = view._build_tree_context_menu(view._proxy_model.mapFromSource(model.createIndex(team.row(), 0, team)))
    [new] = [a.menu() for a in menu.actions() if a.menu() is not None and a.text() == "New"]
    next(a for a in new.actions() if a.text() == "Smart catalogue…").trigger()
    [made] = [c for c in p.catalogs() if c.name == "Smart catalogue"]
    assert list(made.path) == ["t"] and view._current_catalog is made
    qtbot.waitUntil(lambda: getattr(view._event_filter, "scope", lambda: None)() == "all", timeout=3000)
    assert p.catalog_search(made) is None  # nothing saved until Save: an empty search would pick every event
