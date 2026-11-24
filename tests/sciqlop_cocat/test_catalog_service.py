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


def test_a_smart_catalogue_nobody_opened_says_it_is_loading_until_read(catalogs, path, provider, qtbot):
    """What get(), save() and add_events() wait on from a cell or an agent (off the GUI thread):
    without it they would read a smart catalogue before its first background read."""
    catalogs.create(path("plain"), [("2020-01-01", "2020-01-02", {"tags": ["shock"]})])
    [project] = provider._room_infos
    smart = provider._rooms[project].create_catalogue(name="shocks", author="me")
    smart.rule = {"filter": {"all": True}, "where": {"contains": ["tags", "shock"]}}
    provider._rewrap_room(project)
    assert catalogs._still_loading(path("shocks"))
    qtbot.waitUntil(lambda: not catalogs._still_loading(path("shocks")), timeout=5000)
    assert len(catalogs.get(path("shocks"))) == 1


def test_save_of_a_list_of_events_from_get_keeps_their_meta_and_identity(catalogs, path):
    catalogs.create(path("t"), [("2020-01-01", "2020-01-02", {"tags": ["shock"], "note": "n"})])
    [event] = catalogs.get(path("t"))
    uuid = event.meta["__sciqlop_uuid__"]
    event.meta["note"] = "edited"
    catalogs.save(path("t"), [event])
    [again] = catalogs.get(path("t"))
    assert again.meta["__sciqlop_uuid__"] == uuid
    assert (again.meta["note"], again.meta["tags"]) == ("edited", ["shock"])


def test_add_events_of_speasy_events_keeps_their_meta(catalogs, path):
    from speasy.products.catalog import Event
    catalogs.create(path("t"), [])
    catalogs.add_events(path("t"), [Event("2020-01-01", "2020-01-02", meta={"note": "n"})])
    [event] = catalogs.get(path("t"))
    assert event.meta["note"] == "n"


# ---- smart catalogues ----

def _read(catalogs, provider, path, qtbot):
    provider_, catalog = catalogs._resolve(path)
    from .conftest import loaded
    return loaded(provider_, catalog, qtbot)


def test_create_smart_makes_a_catalogue_of_what_its_search_finds(catalogs, path, provider, qtbot):
    catalogs.create(path("all"), [("2020-01-01", "2020-01-02", {"tags": ["shock"]}),
                                  ("2020-02-01", "2020-02-02", {"tags": ["wave"]})])
    catalogs.create_smart(path("shocks"), "tag:shock")
    assert catalogs.search_of(path("shocks")) == "tag:shock"
    assert len(_read(catalogs, provider, path("shocks"), qtbot)) == 1
    assert catalogs.search_of(path("all")) is None


def test_create_smart_can_look_in_one_catalogue(catalogs, path, provider, qtbot):
    catalogs.create(path("a"), [("2020-01-01", "2020-01-02", {"tags": ["shock"]})])
    catalogs.create(path("b"), [("2020-03-01", "2020-03-02", {"tags": ["shock"]})])
    catalogs.create_smart(path("shocks in a"), "tag:shock", source=path("a"))
    assert len(_read(catalogs, provider, path("shocks in a"), qtbot)) == 1


def test_create_smart_refuses_a_taken_name_and_a_wrong_search(catalogs, path):
    import cocat_rs
    catalogs.create(path("a"), [])
    with pytest.raises(ValueError):
        catalogs.create_smart(path("a"), "tag:shock")
    with pytest.raises(cocat_rs.QueryError) as wrong:
        catalogs.create_smart(path("new"), "auhtor:bob")
    assert wrong.value.suggestion == "author"
    assert path("new") not in catalogs.list()


def test_set_search_rule_of_remove_search_and_freeze(catalogs, path, provider, qtbot):
    catalogs.create(path("all"), [("2020-01-01", "2020-01-02", {"tags": ["shock"]}),
                                  ("2020-02-01", "2020-02-02", {"tags": ["wave"]})])
    catalogs.create(path("t"), [])
    catalogs.set_search(path("t"), "tag:wave")
    assert catalogs.search_of(path("t")) == "tag:wave"
    assert catalogs.rule_of(path("t"))["where"] == {"contains": ["tags", "wave"]}
    catalogs.set_rule(path("t"), {"filter": {"all": True}, "where": {"contains": ["tags", "shock"]}})
    assert catalogs.search_of(path("t")) == "tag:shock"
    assert len(_read(catalogs, provider, path("t"), qtbot)) == 1
    frozen = catalogs.freeze(path("t"), "t frozen")
    assert frozen == path("t frozen") and catalogs.search_of(frozen) is None and len(catalogs.get(frozen)) == 1
    catalogs.remove_search(path("t"))
    assert catalogs.search_of(path("t")) is None and catalogs.rule_of(path("t")) is None
