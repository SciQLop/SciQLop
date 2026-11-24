"""The notebook API (``SciQLop.user_api.catalogs.catalogs``) on the cocat-rs provider, which SciQLop
ships on by default. Moved from the tests that ran it on the old tscat provider."""
import pytest

from SciQLop.components.catalogs import CatalogRegistry
from SciQLop.plugins.sciqlop_cocat.provider import CocatRsProvider
from SciQLop.user_api.catalogs._service import CatalogService
from .test_provider_rooms import FakeSession, run

PROVIDER = "Catalogs under test"  # the shared test main window has a "Catalogs (cocat-rs)" too


def under_test(session, tmp_path) -> CocatRsProvider:
    p = CocatRsProvider(author="me", session=session, cache_dir=tmp_path / "cache", local_dir=tmp_path / "local")
    p._name = PROVIDER
    return p


@pytest.fixture
def provider(qapp, tmp_path):
    p = under_test(FakeSession(signed_in=False), tmp_path)
    run(p.show_signed_out())
    yield p
    run(p.close())
    CatalogRegistry.instance()._forget_for_tests(p)


@pytest.fixture
def catalogs(provider):
    return CatalogService()


@pytest.fixture
def path(provider):
    """A catalogue's notebook path: provider, project (by its id), name."""
    [project] = provider._room_infos
    return lambda name: f"{PROVIDER}//{project}//{name}"


TWO = [("2020-01-01", "2020-01-02"), ("2020-06-01", "2020-06-15")]


def test_create_then_get_returns_events(catalogs, path):
    catalogs.create(path("t"), TWO)
    assert len(catalogs.get(path("t"))) == 2


def test_add_events_appends(catalogs, path, qapp):
    catalogs.create(path("t"), TWO[:1])
    qapp.processEvents()  # as from one notebook cell to the next
    catalogs.add_events(path("t"), TWO[1:])
    assert len(catalogs.get(path("t"))) == 2


def test_remove_events(catalogs, path):
    catalogs.create(path("t"), TWO)
    catalogs.remove_events(path("t"), [catalogs.get(path("t"))[0]])
    assert len(catalogs.get(path("t"))) == 1


def test_save_creates_a_catalogue(catalogs, path):
    catalogs.save(path("t"), [("2020-03-01", "2020-03-10")])
    assert len(catalogs.get(path("t"))) == 1


def test_save_replaces_the_events(catalogs, path):
    catalogs.create(path("t"), TWO[:1])
    catalogs.save(path("t"), [("2021-01-01", "2021-01-02"), ("2021-06-01", "2021-06-15"),
                              ("2021-12-01", "2021-12-31")])
    assert len(catalogs.get(path("t"))) == 3


def test_list_and_remove(catalogs, path, provider):
    catalogs.create(path("t"), TWO[:1])
    assert path("t") in catalogs.list(PROVIDER)
    removed = []
    provider.catalog_removed.connect(lambda catalog: removed.append(catalog.name))

    catalogs.remove(path("t"))

    assert removed == ["t"] and path("t") not in catalogs.list(PROVIDER)


def test_create_twice_raises(catalogs, path):
    catalogs.create(path("t"), TWO[:1])
    with pytest.raises(ValueError, match="already exists"):
        catalogs.create(path("t"), TWO[1:])


def test_uuids_round_trip(catalogs, path):
    catalogs.create(path("t"), TWO[:1])
    first = catalogs.get(path("t"))[0].meta["__sciqlop_uuid__"]
    assert catalogs.get(path("t"))[0].meta["__sciqlop_uuid__"] == first


def test_persist_needs_no_save(catalogs, path, provider):
    """cocat-rs writes each change as it happens."""
    catalogs.create(path("t"), TWO)
    catalogs.persist(path("t"))
    [catalog] = provider.catalogs()
    assert not provider.is_dirty(catalog)


# ---- a path without a project: the default one ----

def test_a_path_without_a_project_means_the_default_one(catalogs, path, provider):
    catalogs.create(f"{PROVIDER}//shocks", TWO)

    assert len(catalogs.get(f"{PROVIDER}//shocks")) == 2
    assert catalogs.list(PROVIDER) == [path("shocks")]  # listed with its project
    catalogs.add_events(f"{PROVIDER}//shocks", [("2021-01-01", "2021-01-02")])
    assert len(catalogs.get(path("shocks"))) == 3


def test_save_and_remove_without_a_project(catalogs, path):
    catalogs.save(f"{PROVIDER}//shocks", TWO)
    assert len(catalogs.get(path("shocks"))) == 2
    catalogs.remove(f"{PROVIDER}//shocks")
    assert catalogs.list(PROVIDER) == []


def test_without_a_project_it_is_the_default_one_signed_in(qapp, tmp_path):
    from .test_provider_rooms import ROOMS
    p = under_test(FakeSession(rooms=ROOMS), tmp_path)
    try:
        run(p.connect())
        CatalogService().create(f"{PROVIDER}//shocks", TWO)
        [catalog] = p.catalogs()
        assert catalog.path == ["a"]  # the account's own project, not the read-only "Team"
    finally:
        run(p.close())
        CatalogRegistry.instance()._forget_for_tests(p)


def test_tags_and_rating_come_back_from_get(catalogs, path):
    catalogs.create(path("t"), [("2020-01-01", "2020-01-02", {"tags": ["shock"], "rating": 7, "note": "n"}),
                                ("2020-02-01", "2020-02-02")])
    first, second = catalogs.get(path("t"))
    assert (first.meta["tags"], first.meta["rating"], first.meta["note"]) == (["shock"], 7, "n")
    assert "rating" not in second.meta and "tags" not in second.meta


def test_tags_and_rating_come_back_after_a_restart(catalogs, path, provider, tmp_path):
    catalogs.create(path("t"), [("2020-01-01", "2020-01-02", {"tags": ["shock"], "rating": 7})])
    run(provider.close())
    CatalogRegistry.instance()._forget_for_tests(provider)  # a restart: only the new one is listed
    again = under_test(FakeSession(signed_in=False), tmp_path)
    try:
        run(again.show_signed_out())
        [event] = catalogs.get(path("t"))
        assert (event.meta["tags"], event.meta["rating"]) == (["shock"], 7)
    finally:
        run(again.close())
        CatalogRegistry.instance()._forget_for_tests(again)


def test_tags_and_rating_edited_through_save_survive_a_restart(catalogs, path, provider, tmp_path):
    catalogs.create(path("t"), [("2020-01-01", "2020-01-02", {"tags": ["shock"], "rating": 7})])
    catalogue = catalogs.get(path("t"))
    [event] = catalogue
    event.meta["tags"], event.meta["rating"] = ["shock", "foreshock"], 2
    catalogs.save(path("t"), catalogue)
    run(provider.close())
    CatalogRegistry.instance()._forget_for_tests(provider)
    again = under_test(FakeSession(signed_in=False), tmp_path)
    try:
        run(again.show_signed_out())
        [event] = catalogs.get(path("t"))
        assert (event.meta["tags"], event.meta["rating"]) == (["foreshock", "shock"], 2)
    finally:
        run(again.close())
        CatalogRegistry.instance()._forget_for_tests(again)
