""""New catalog…" wherever "New smart catalogue" is: My catalogues, a project, a folder in a project; the
catalogue goes there. A read-only project offers neither. The tree made the creation rows when it
first placed a project, from the project list, before the project was joined and writable."""
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


def _menu_texts(view, node):
    model = view._tree_model
    menu = view._build_tree_context_menu(view._proxy_model.mapFromSource(model.createIndex(node.row(), 0, node)))
    return [a.text() for a in menu.actions()] if menu is not None else []


def test_new_catalog_is_offered_wherever_a_new_smart_catalogue_is(browser, qapp):
    view, p = browser
    nodes = _nodes(view, p)
    assert nodes["My catalogues"].section == Section.MINE
    menus = {}
    assert windows_shown_while(qapp, lambda: menus.update({k: _menu_texts(view, n) for k, n in nodes.items()})) == []
    for place in ("My catalogues", "Team"):
        assert "New catalog…" in menus[place] and "New smart catalogue" in menus[place], place
    assert "New catalog…" in menus["Team/sub"]  # a folder never offered "New smart catalogue"
    assert "New catalog…" not in menus["Theirs"] and "New smart catalogue" not in menus["Theirs"]


def test_a_new_catalogue_goes_where_it_was_asked(browser):
    from PySide6.QtCore import Qt
    from SciQLop.components.catalogs.ui.catalog_tree import _PlaceholderType
    view, p = browser
    model = view._tree_model
    for place, name, path in (("My catalogues", "mine", ["a"]), ("Team", "ours", ["t"]),
                              ("Team/sub", "deeper", ["t", "sub"])):
        row = next(c for c in _nodes(view, p)[place].children if c.placeholder_type == _PlaceholderType.CATALOG)
        assert model.setData(model.createIndex(row.row(), 0, row), name, Qt.ItemDataRole.EditRole)
        [made] = [c for c in p.catalogs() if c.name == name]
        assert list(made.path) == path, place
