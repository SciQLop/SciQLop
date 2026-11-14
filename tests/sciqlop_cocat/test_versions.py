import cocat_rs
import pytest

from SciQLop.components.catalogs import CatalogRegistry
from SciQLop.plugins.sciqlop_cocat.convert import SUBPATH_ATTR, encode_subpath
from SciQLop.plugins.sciqlop_cocat.versions import VersionsProvider


@pytest.fixture
def past(tmp_path):
    project = cocat_rs.Project.open(tmp_path / "past", "p")
    shocks = project.create_catalogue(name="shocks", author="a",
                                      attributes={SUBPATH_ATTR: encode_subpath(["Mercury"])})
    shocks.add_events([project.create_event(start="2020-01-01T00:00:00Z", stop="2020-01-01T01:00:00Z",
                                            author="a")])
    yield project, shocks


@pytest.fixture
def versions(qapp):
    provider = VersionsProvider()
    yield provider
    CatalogRegistry.instance()._forget_for_tests(provider)


def test_a_version_shows_as_a_read_only_folder(versions, past):
    project, shocks = past
    folders = []
    versions.folder_added.connect(folders.append)
    versions.show("p@3", "Team as of 2026-11-09 15:10", project)
    [catalog] = versions.catalogs()
    assert folders == [["p@3"]] and versions.folder_display_name(["p@3"]) == "Team as of 2026-11-09 15:10"
    assert catalog.name == "shocks" and catalog.path == ["p@3", "Mercury"]
    assert catalog.uuid != shocks.uuid  # the live catalogue keeps its own uuid in SciQLop
    [event] = versions.events(catalog)
    assert event.uuid.startswith("p@3/")
    assert versions.capabilities() == set() and versions.capabilities(catalog) == set()


def test_showing_a_version_twice_keeps_one(versions, past):
    project, _ = past
    versions.show("p@3", "Team", project)
    versions.show("p@3", "Team", project)
    assert len(versions.catalogs()) == 1


def test_closing_a_version_removes_it(versions, past):
    project, _ = past
    removed = []
    versions.folder_removed.connect(removed.append)
    versions.show("p@3", "Team", project)
    [close] = versions.folder_actions(["p@3"])
    close.callback(["p@3"])
    assert versions.catalogs() == [] and removed == [["p@3"]]
    assert versions.folder_actions(["p@3"]) == []
