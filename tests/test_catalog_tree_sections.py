"""The catalogue tree groups catalogues by what they are to the person, not by where they come
from: My catalogues, Shared, Reference. A provider places its catalogues; by default all of them
go to Reference, under one node named after the provider."""

import pytest
from PySide6.QtCore import QModelIndex, Qt

from .fixtures import *  # noqa: F401,F403


def _tree(qapp):
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    return CatalogTreeModel()


def rows(model, parent=QModelIndex()) -> list[str]:
    return [model.data(model.index(r, 0, parent)) for r in range(model.rowCount(parent))]


def child(model, *names) -> QModelIndex:
    index = QModelIndex()
    for name in names:
        [index] = [model.index(r, 0, index) for r in range(model.rowCount(index))
                   if model.data(model.index(r, 0, index)) == name]
    return index


@pytest.fixture
def made(qapp):
    from SciQLop.components.catalogs import CatalogRegistry
    providers = []
    yield providers
    for p in providers:
        CatalogRegistry.instance()._forget_for_tests(p)


def dummy(made, **kwargs):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    p = DummyProvider(**kwargs)
    made.append(p)
    return p


class Placed:
    """A provider that places each of its top folders, as cocat-rs does with its projects."""

    @staticmethod
    def make(made, placements: dict, paths: list[list[str]], name="Placed"):
        from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
        from SciQLop.components.catalogs.backend.provider import Placement

        class _Placed(DummyProvider):
            def placement(self, folder):
                return placements.get(folder) if folder is not None else None

            def folder_display_name(self, path):
                return {"me": "Mine", "team": "Team", "pub": "Public catalogues"}.get(path[0]) \
                    if len(path) == 1 else None

        p = _Placed(num_catalogs=len(paths), events_per_catalog=1, paths=paths, name=name)
        for folder in {path[0] for path in paths}:
            p.folder_added.emit([folder])
        made.append(p)
        return p, Placement


def test_the_sections_are_my_catalogues_shared_and_reference_in_that_order(made, qapp):
    from SciQLop.components.catalogs.backend.provider import Placement, Section
    placements = {"me": Placement(Section.MINE, inline=True), "team": Placement(Section.SHARED),
                  "pub": Placement(Section.REFERENCE, can_create=False)}
    Placed.make(made, placements, [["pub"], ["team"], ["me"]])
    model = _tree(qapp)
    assert rows(model)[:3] == ["My catalogues", "Shared", "Reference"]


def test_folders_a_provider_announced_before_the_tree_existed_show(made, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider

    class Announced(DummyProvider):
        def folders(self):
            return [["empty project"]]

    made.append(Announced(num_catalogs=0, events_per_catalog=0, name="Announced"))
    model = _tree(qapp)
    assert "empty project" in rows(model, child(model, "Reference", "Announced"))


def test_my_catalogues_is_always_shown_and_the_others_only_when_they_hold_something(made, qapp):
    model = _tree(qapp)
    assert rows(model)[0] == "My catalogues"
    assert "Shared" not in rows(model)


def test_a_provider_that_says_nothing_goes_to_reference_under_its_name(made, qapp):
    p = dummy(made, num_catalogs=2, events_per_catalog=1, name="Plugin lists")
    model = _tree(qapp)
    under = rows(model, child(model, "Reference", "Plugin lists"))
    assert [c.name for c in p.catalogs()] == [r for r in under if not r.endswith("…")]


def test_an_inline_project_shows_its_catalogues_directly_in_its_section(made, qapp):
    from SciQLop.components.catalogs.backend.provider import Placement, Section
    p, _ = Placed.make(made, {"me": Placement(Section.MINE, inline=True), "team": Placement(Section.SHARED)},
                       [["me"], ["me", "MMS"], ["team"]])
    model = _tree(qapp)
    mine = rows(model, child(model, "My catalogues"))
    assert set(mine[:2]) == {"MMS", p.catalogs()[0].name}
    assert mine[-2:] == ["New catalog…", "New folder…"]
    assert rows(model, child(model, "Shared")) == ["Team"]
    assert p.catalogs()[2].name in rows(model, child(model, "Shared", "Team"))


def test_creating_from_a_section_goes_to_its_inline_project(made, qapp):
    from SciQLop.components.catalogs.backend.provider import Placement, Section
    p, _ = Placed.make(made, {"me": Placement(Section.MINE, inline=True)}, [["me"]])
    model = _tree(qapp)
    mine = child(model, "My catalogues")
    [placeholder] = [model.index(r, 0, mine) for r in range(model.rowCount(mine))
                     if model.data(model.index(r, 0, mine)) == "New catalog…"]
    assert model.setData(placeholder, "shocks")
    assert [c.path for c in p.catalogs() if c.name == "shocks"] == [["me"]]
    assert "shocks" in rows(model, mine)


def test_read_only_places_get_no_creation_rows(made, qapp):
    from SciQLop.components.catalogs.backend.provider import Placement, Section
    Placed.make(made, {"pub": Placement(Section.REFERENCE, can_create=False)}, [["pub"]])
    model = _tree(qapp)
    assert not any(r.endswith("…") for r in rows(model, child(model, "Reference", "Public catalogues")))


def test_a_catalogue_added_later_lands_in_its_section(made, qapp):
    from SciQLop.components.catalogs.backend.provider import Placement, Section
    p, _ = Placed.make(made, {"me": Placement(Section.MINE, inline=True), "team": Placement(Section.SHARED)},
                       [["me"]])
    model = _tree(qapp)
    assert "Shared" not in rows(model)
    p.folder_added.emit(["team"])
    p.create_catalog("joint", ["team"])
    assert rows(model, child(model, "Shared", "Team"))[0] == "joint"


def test_a_project_that_goes_away_leaves_and_an_empty_section_hides(made, qapp):
    from SciQLop.components.catalogs.backend.provider import Placement, Section
    p, _ = Placed.make(made, {"me": Placement(Section.MINE, inline=True), "team": Placement(Section.SHARED)},
                       [["me"], ["team"]])
    model = _tree(qapp)
    team = [c for c in p.catalogs() if c.path == ["team"]][0]
    p.remove_catalog(team)
    p.folder_removed.emit(["team"])
    assert "Shared" not in rows(model)
    me = [c for c in p.catalogs() if c.path == ["me"]][0]
    p.remove_catalog(me)
    p.folder_removed.emit(["me"])
    assert rows(model)[0] == "My catalogues" and rows(model, child(model, "My catalogues")) == []


def test_each_node_knows_its_provider_and_path(made, qapp):
    from SciQLop.components.catalogs.backend.provider import Placement, Section
    p, _ = Placed.make(made, {"me": Placement(Section.MINE, inline=True)}, [["me", "MMS", "deep"]])
    model = _tree(qapp)
    folder = model.node_from_index(child(model, "My catalogues", "MMS"))
    deep = model.node_from_index(child(model, "My catalogues", "MMS", "deep"))
    assert (folder.provider, folder.path) == (p, ["me", "MMS"])
    assert deep.path == ["me", "MMS", "deep"]


def test_dropping_a_catalogue_on_a_section_puts_it_in_the_inline_project(made, qapp):
    from SciQLop.components.catalogs.backend.provider import Placement, Section
    from SciQLop.core.mime import encode_mime
    p, _ = Placed.make(made, {"me": Placement(Section.MINE, inline=True), "team": Placement(Section.SHARED)},
                       [["me"], ["team"]])
    other = dummy(made, num_catalogs=1, events_per_catalog=3, name="Elsewhere")
    model = _tree(qapp)
    data = encode_mime([other.catalogs()[0]])
    mine = child(model, "My catalogues")
    assert model.canDropMimeData(data, Qt.DropAction.CopyAction, -1, 0, mine)
    before = set(c.uuid for c in p.catalogs())
    model.dropMimeData(data, Qt.DropAction.CopyAction, -1, 0, mine)
    [copied] = [c for c in p.catalogs() if c.uuid not in before]
    assert copied.path == ["me"] and len(p.events(copied)) == 3


def test_reference_refuses_drops_on_its_header(made, qapp):
    from SciQLop.core.mime import encode_mime
    other = dummy(made, num_catalogs=1, events_per_catalog=1, name="Elsewhere")
    model = _tree(qapp)
    data = encode_mime([other.catalogs()[0]])
    assert not model.canDropMimeData(data, Qt.DropAction.CopyAction, -1, 0, child(model, "Reference"))


def test_a_provider_note_shows_under_its_section(made, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.provider import Section

    class Signed(DummyProvider):
        note = "Sign in to see shared projects"

        def section_note(self, section):
            return self.note if section == Section.SHARED else None

    p = Signed(num_catalogs=0, events_per_catalog=0, name="Signed")
    made.append(p)
    model = _tree(qapp)
    shared = child(model, "Shared")
    assert rows(model, shared) == ["Sign in to see shared projects"]
    assert not model.flags(model.index(0, 0, shared)) & Qt.ItemFlag.ItemIsSelectable
    p.note = None
    p.status_changed.emit()
    assert "Shared" not in rows(model)


def test_a_move_between_projects_of_one_provider_that_cannot_move_is_a_copy(made, qapp):
    from SciQLop.components.catalogs.backend.provider import Placement, Section
    from SciQLop.core.mime import encode_mime
    p, _ = Placed.make(made, {"me": Placement(Section.MINE, inline=True), "team": Placement(Section.SHARED)},
                       [["me"], ["team"]])
    p.can_move_catalog = lambda catalog, path: catalog.path[:1] == path[:1]
    source = [c for c in p.catalogs() if c.path == ["me"]][0]
    model = _tree(qapp)
    model.dropMimeData(encode_mime([source]), Qt.DropAction.MoveAction, -1, 0, child(model, "Shared", "Team"))
    assert source.path == ["me"]
    assert [c.path for c in p.catalogs() if c.name.startswith(source.name)] == [["me"], ["team"]]


def test_the_browser_opens_the_sections(made, qtbot, qapp):
    from SciQLop.components.catalogs.ui.catalog_browser import CatalogBrowser
    dummy(made, num_catalogs=1, events_per_catalog=1, name="Before")
    browser = CatalogBrowser()
    qtbot.addWidget(browser)
    dummy(made, num_catalogs=1, events_per_catalog=1, name="After")
    proxy, tree = browser._proxy_model, browser._catalog_tree
    assert all(tree.isExpanded(proxy.index(r, 0)) for r in range(proxy.rowCount()))


def test_a_section_still_draws_when_its_provider_left_the_registry_without_a_word(made, qapp):
    """Seen on screenshots: a provider forgotten by the registry (tests do it) left its group in the
    tree, and asking the section about it raised in flags() and data()."""
    from SciQLop.components.catalogs import CatalogRegistry
    from SciQLop.components.catalogs.backend.provider import Placement, Section
    p, _ = Placed.make(made, {"me": Placement(Section.MINE, inline=True)}, [["me"]])
    model = _tree(qapp)
    CatalogRegistry.instance()._forget_for_tests(p)
    mine = child(model, "My catalogues")
    model.flags(mine)
    model.data(mine, Qt.ItemDataRole.DecorationRole)
    model.data(mine, Qt.ItemDataRole.ToolTipRole)
