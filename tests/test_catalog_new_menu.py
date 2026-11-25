"""One "New" submenu in every right-click menu of the catalogue tree, listing only what can be made there, in one
order: Catalogue, Smart catalogue…, Folder, Project…. A provider declares what it can make (creations) and how
it spells "catalog" (CATALOG_WORD); the browser builds the menu. Read-only places get no "New"."""
import pytest

from .fixtures import *  # noqa: F401,F403
from .helpers import windows_shown_while
from .test_catalog_tree_sections import made  # noqa: F401

pytestmark = pytest.mark.usefixtures("only_this_test_s_catalog_providers")


def _placed(made, word="catalogue"):  # noqa: F811
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.provider import Creation, Placement, Section
    placements = {"me": Placement(Section.MINE, inline=True), "team": Placement(Section.SHARED),
                  "ro": Placement(Section.SHARED, can_create=False)}

    class Placed(DummyProvider):
        CATALOG_WORD = word
        made_projects = 0

        def placement(self, folder):
            return placements.get(folder) if folder is not None else None

        def folder_display_name(self, path):
            return {"me": "Mine", "team": "Team", "ro": "Theirs"}.get(path[0]) if len(path) == 1 else None

        def creations(self, path):
            if path is None:
                return frozenset({Creation.PROJECT})
            if path[0] == "ro":
                return frozenset()
            return frozenset({Creation.CATALOG, Creation.SMART_CATALOG, Creation.FOLDER})

        def new_project(self):
            Placed.made_projects += 1

    paths = [["me"], ["team"], ["team", "sub"], ["ro"]]
    p = Placed(num_catalogs=len(paths), events_per_catalog=1, paths=paths, name="Placed")
    for folder in ("me", "team", "ro"):
        p.folder_added.emit([folder])
    made.append(p)
    return p


def _browser(qtbot):
    """Made after the providers, as the sections' tests make their tree."""
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    view = CatalogBrowser()
    qtbot.addWidget(view)
    return view


def _node(view, *names):
    node = view._tree_model._root
    for name in names:
        found = [c for c in node.children if c.name == name]
        assert found, f"{name!r} not in {[c.name for c in node.children]}"
        node = found[0]
    return node


def _menu(view, node):
    model = view._tree_model
    return view._build_tree_context_menu(view._proxy_model.mapFromSource(model.createIndex(node.row(), 0, node)))


def _new(menu) -> list[str] | None:
    found = [a.menu() for a in menu.actions() if a.menu() is not None and a.text() == "New"] if menu else []
    assert len(found) <= 1, "one New submenu"
    return [a.text() for a in found[0].actions()] if found else None


def _loose(menu) -> list[str]:
    return [a.text() for a in menu.actions() if a.text().startswith("New ") or a.text() == "New project…"]


def test_each_place_offers_what_can_be_made_there_in_one_order(made, qtbot, qapp):  # noqa: F811
    _placed(made)
    browser = _browser(qtbot)
    menus = {}
    places = {"My catalogues": ("My catalogues",), "Shared": ("Shared",), "Team": ("Shared", "Team"),
              "Team/sub": ("Shared", "Team", "sub"), "Theirs": ("Shared", "Theirs")}
    windows = windows_shown_while(qapp, lambda: menus.update(
        {place: _menu(browser, _node(browser, *names)) for place, names in places.items()}))
    assert windows == []
    assert _new(menus["My catalogues"]) == ["Catalogue", "Smart catalogue…", "Folder", "Project…"]
    assert _new(menus["Team"]) == ["Catalogue", "Smart catalogue…", "Folder"]
    assert _new(menus["Team/sub"]) == ["Catalogue", "Smart catalogue…", "Folder"]
    assert _new(menus["Shared"]) == ["Project…"]
    assert _new(menus["Theirs"]) is None
    assert all(_loose(m) == [] for m in menus.values() if m is not None)


def test_the_one_click_rows_follow_the_provider_s_spelling(made, qtbot):  # noqa: F811
    _placed(made)
    browser = _browser(qtbot)
    team = _node(browser, "Shared", "Team")
    assert [c.name for c in team.children if c.is_placeholder] == ["New catalogue…", "New folder…"]


def test_a_provider_that_only_creates_catalogs_gets_catalog_and_folder(made, qtbot):  # noqa: F811
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    plain = DummyProvider(num_catalogs=1, events_per_catalog=0, paths=[["room"]], name="Plain")
    made.append(plain)
    plain.folder_added.emit(["room"])
    browser = _browser(qtbot)
    assert _new(_menu(browser, _node(browser, "Reference", "Plain", "room"))) == ["Catalog", "Folder"]


def test_catalogue_starts_naming_one_in_the_tree(made, qtbot, monkeypatch):  # noqa: F811
    _placed(made)
    browser = _browser(qtbot)
    edited = []
    monkeypatch.setattr(browser, "_trigger_placeholder_edit", edited.append)
    team = _node(browser, "Shared", "Team")
    menu = _menu(browser, team)
    _action(menu, "Catalogue").trigger()
    assert [n.name for n in edited] == ["New catalogue…"] and edited[0].parent is team


def test_smart_catalogue_makes_one_there_selects_it_and_starts_its_search(made, qtbot):  # noqa: F811
    p = _placed(made)
    browser = _browser(qtbot)
    _action(_menu(browser, _node(browser, "Shared", "Team")), "Smart catalogue…").trigger()
    [made_one] = [c for c in p.catalogs() if c.name == "Smart catalogue"]
    assert list(made_one.path) == ["team"] and browser._current_catalog is made_one
    _action(_menu(browser, _node(browser, "Shared", "Team")), "Smart catalogue…").trigger()
    assert "Smart catalogue (2)" in [c.name for c in p.catalogs()]


def test_project_asks_the_provider(made, qtbot):  # noqa: F811
    p = _placed(made)
    browser = _browser(qtbot)
    _action(_menu(browser, _node(browser, "Shared")), "Project…").trigger()
    assert type(p).made_projects == 1


def test_start_search_defaults_to_focus(qapp):
    from SciQLop.components.catalogs.ui.event_filter import PlainTextFilter
    box = PlainTextFilter()
    focused = []
    box.focus = lambda: focused.append(True)
    box.start_search()
    assert focused == [True]


def _action(menu, text):
    [new] = [a.menu() for a in menu.actions() if a.menu() is not None and a.text() == "New"]
    return next(a for a in new.actions() if a.text() == text)
