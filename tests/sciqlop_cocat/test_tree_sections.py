"""Where cocat-rs projects go in SciQLop's catalogue tree: the person's own project directly in My
catalogues, projects shared with others in Shared, public catalogues in Reference. Their state shows
as an icon and in the tooltip, not in their name."""
import pytest
from PySide6.QtCore import QModelIndex

from SciQLop.components.catalogs import CatalogRegistry
from SciQLop.components.catalogs.backend.provider import Placement, Section
from SciQLop.plugins.sciqlop_cocat import provider as provider_module
from SciQLop.plugins.sciqlop_cocat.provider import CocatRsProvider
from SciQLop.plugins.sciqlop_cocat.public import PUBLIC
from .test_provider_rooms import ROOMS, FakeSession, opened, run  # noqa: F401

pytestmark = pytest.mark.usefixtures("only_this_test_s_catalog_providers")

TEAM_EDITOR = __import__("cocat_rs").ProjectInfo("c", "Lab", "editor")


@pytest.fixture
def make(qapp, tmp_path, monkeypatch):
    monkeypatch.setattr(provider_module.questions, "ask_move", lambda names, target: False)
    made = []

    def make(session):
        p = CocatRsProvider(author="me", session=session, cache_dir=tmp_path / "cache", local_dir=tmp_path / "local")
        made.append(p)
        return p

    yield make
    for p in made:
        run(p.close())
        CatalogRegistry.instance()._forget_for_tests(p)


def signed_out(make):
    p = make(FakeSession(signed_in=False))
    run(p.show_signed_out())
    [local] = p._room_infos
    return p, local


def signed_in(make, rooms=ROOMS):
    p = make(FakeSession(rooms=list(rooms)))
    assert run(p.connect())
    return p


def tree():
    from SciQLop.components.catalogs.ui.catalog_tree import CatalogTreeModel
    return CatalogTreeModel()


def rows(model, parent=QModelIndex()) -> list[str]:
    return [model.data(model.index(r, 0, parent)) for r in range(model.rowCount(parent))]


def section(model, name) -> QModelIndex:
    [index] = [model.index(r, 0) for r in range(model.rowCount()) if model.data(model.index(r, 0)) == name]
    return index


def test_the_provider_places_each_project_on_its_own(make):
    p, _ = signed_out(make)
    assert p.placement(None) is None


def test_signed_out_my_catalogues_shows_directly_in_its_section(make):
    p, local = signed_out(make)
    assert p.placement(local) == Placement(Section.MINE, inline=True)
    assert p.folder_display_name([local]) == "My catalogues"


def test_signed_in_the_own_project_is_my_catalogues_and_the_others_are_shared(make):
    p = signed_in(make, [*ROOMS, TEAM_EDITOR])
    assert p.placement("a") == Placement(Section.MINE, inline=True)
    assert p.placement("b") == Placement(Section.SHARED, can_create=False)  # a viewer
    assert p.placement("c") == Placement(Section.SHARED)
    assert p.placement(PUBLIC) == Placement(Section.REFERENCE, can_create=False)
    assert [p.folder_display_name([r]) for r in "abc"] == ["My catalogues", "Team", "Lab"]


def test_signed_in_a_project_kept_on_this_computer_is_a_folder_in_my_catalogues(make):
    p, local = signed_out(make)
    p.create_catalog("shocks")
    run(p.close())
    p = signed_in(make)
    assert p.placement(local) == Placement(Section.MINE)
    assert p.folder_display_name([local]) == "On this computer"


def test_the_tree_shows_the_sections(make, opened):
    p = signed_in(make, [*ROOMS, TEAM_EDITOR])
    p.create_catalog("shocks", ["a"])
    p.create_catalog("joint", ["c"])
    model = tree()
    assert rows(model)[:2] == ["My catalogues", "Shared"]
    mine = rows(model, section(model, "My catalogues"))
    assert mine[0] == "shocks" and "Team" not in mine
    assert rows(model, section(model, "Shared")) == ["Lab", "Team"]


def test_signed_out_shared_says_why_it_is_empty(make):
    p, _ = signed_out(make)
    assert p.section_note(Section.SHARED) == "Sign in to see shared projects"
    assert p.section_note(Section.MINE) is None
    assert signed_in(make).section_note(Section.SHARED) is None


def test_my_catalogues_open_in_another_window_says_so(make):
    first, local = signed_out(make)
    second, _ = signed_out(make)
    note = second.section_note(Section.MINE)
    assert "another SciQLop window" in note and "Open here" in note
    assert first.section_note(Section.MINE) is None


def test_a_catalogue_moves_inside_its_project_and_is_copied_to_another(make):
    p = signed_in(make, [*ROOMS, TEAM_EDITOR])
    shocks = p.create_catalog("shocks", ["a"])
    assert p.can_move_catalog(shocks, ["a", "MMS"])
    assert not p.can_move_catalog(shocks, ["c"])
    assert p.can_move_catalog(shocks, [PUBLIC])  # submitted, as before


def test_a_project_s_state_names_its_icon(make):
    p = signed_in(make, [*ROOMS, TEAM_EDITOR])
    assert p.project_state("b") == "read-only"
    assert p.project_state("c") in ("connecting", "offline", "synced")


def test_a_project_on_this_computer_says_so_and_where_it_is_open(make):
    local_p, local = signed_out(make)
    assert local_p.project_state(local) == "on this computer"
    other, _ = signed_out(make)
    assert other.project_state(local) == "elsewhere"


def test_the_own_project_s_tooltip_names_the_account(make):
    p = signed_in(make)
    assert "me@h" in p.node_tooltip(__import__("SciQLop.components.catalogs.backend.provider",
                                               fromlist=["NodeType"]).NodeType.FOLDER, path=["a"])
