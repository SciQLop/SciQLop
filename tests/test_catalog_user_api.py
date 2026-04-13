from .fixtures import *
import pytest
from datetime import datetime, timedelta, timezone
from SciQLop.components.catalogs.backend.provider import CatalogProvider, Catalog, CatalogEvent


def test_parse_path_single_slash_rejected():
    from SciQLop.user_api.catalogs._service import _parse_path
    with pytest.raises(ValueError, match="must be separated by '//'"):
        _parse_path("tscat/My Catalog")


def test_parse_path_mixed_separators_rejected():
    from SciQLop.user_api.catalogs._service import _parse_path
    with pytest.raises(ValueError, match="must be separated by '//'"):
        _parse_path("Shared//Bepi MSA/test")


def test_parse_path_double_slash():
    from SciQLop.user_api.catalogs._service import _parse_path
    provider, path, name = _parse_path("cocat//room1//My Catalog")
    assert provider == "cocat"
    assert path == ["room1"]
    assert name == "My Catalog"


def test_parse_path_double_slash_nested():
    from SciQLop.user_api.catalogs._service import _parse_path
    provider, path, name = _parse_path("cocat//room1//sub//My Catalog")
    assert provider == "cocat"
    assert path == ["room1", "sub"]
    assert name == "My Catalog"


def test_parse_path_name_with_slash_rejected():
    from SciQLop.user_api.catalogs._service import _parse_path
    with pytest.raises(ValueError, match="cannot contain '/'"):
        _parse_path("cocat//room1//Cat/with slash")


def test_parse_path_too_short():
    from SciQLop.user_api.catalogs._service import _parse_path
    with pytest.raises(ValueError):
        _parse_path("just-provider")


def test_parse_prefix_provider_only():
    from SciQLop.user_api.catalogs._service import _parse_prefix
    provider, path = _parse_prefix("cocat")
    assert provider == "cocat"
    assert path == []


def test_parse_prefix_with_path():
    from SciQLop.user_api.catalogs._service import _parse_prefix
    provider, path = _parse_prefix("cocat//room1")
    assert provider == "cocat"
    assert path == ["room1"]


def test_catalog_event_to_speasy(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import CatalogEvent
    from SciQLop.user_api.catalogs._service import _event_to_speasy

    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    stop = datetime(2020, 1, 2, tzinfo=timezone.utc)
    event = CatalogEvent(uuid="evt-1", start=start, stop=stop,
                         meta={"author": "Alice"})
    speasy_event = _event_to_speasy(event)
    assert speasy_event.start_time == start
    assert speasy_event.stop_time == stop
    assert speasy_event.meta["author"] == "Alice"
    assert speasy_event.meta["__sciqlop_uuid__"] == "evt-1"


def test_speasy_event_to_internal(qtbot, qapp):
    from speasy.products.catalog import Event as SpeasyEvent
    from SciQLop.user_api.catalogs._service import _event_to_internal

    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    stop = datetime(2020, 1, 2, tzinfo=timezone.utc)
    ev = SpeasyEvent(start, stop, meta={"author": "Alice", "__sciqlop_uuid__": "evt-1"})
    internal = _event_to_internal(ev)
    assert internal.uuid == "evt-1"
    assert internal.start == start
    assert internal.stop == stop
    assert internal.meta == {"author": "Alice"}
    assert "__sciqlop_uuid__" not in internal.meta


def test_speasy_event_to_internal_no_uuid(qtbot, qapp):
    from speasy.products.catalog import Event as SpeasyEvent
    from SciQLop.user_api.catalogs._service import _event_to_internal

    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    stop = datetime(2020, 1, 2, tzinfo=timezone.utc)
    ev = SpeasyEvent(start, stop, meta={"author": "Alice"})
    internal = _event_to_internal(ev)
    assert internal.uuid  # auto-generated, non-empty
    assert internal.meta == {"author": "Alice"}


def test_normalize_input_speasy_catalog(qtbot, qapp):
    from speasy.products.catalog import Catalog as SpeasyCatalog, Event as SpeasyEvent
    from SciQLop.user_api.catalogs._service import _normalize_input

    cat = SpeasyCatalog(name="test", events=[
        SpeasyEvent("2020-01-01", "2020-01-02", meta={"tag": "a"}),
    ])
    result = _normalize_input(cat)
    assert isinstance(result, SpeasyCatalog)
    assert result is cat


def test_normalize_input_tuples(qtbot, qapp):
    from SciQLop.user_api.catalogs._service import _normalize_input
    from speasy.products.catalog import Catalog as SpeasyCatalog

    data = [("2020-01-01", "2020-01-02"), ("2020-06-01", "2020-06-02")]
    result = _normalize_input(data)
    assert isinstance(result, SpeasyCatalog)
    assert len(result) == 2


def test_normalize_input_triples(qtbot, qapp):
    from SciQLop.user_api.catalogs._service import _normalize_input
    from speasy.products.catalog import Catalog as SpeasyCatalog

    data = [("2020-01-01", "2020-01-02", {"tag": "a"})]
    result = _normalize_input(data)
    assert isinstance(result, SpeasyCatalog)
    assert len(result) == 1
    assert result[0].meta["tag"] == "a"


class _IsolatedDummyProvider(CatalogProvider):
    """IsolatedDummy with a unique name to avoid collisions with other test modules."""

    def __init__(self, num_catalogs, events_per_catalog, paths=None, parent=None):
        super().__init__(name="IsolatedDummy", parent=parent)
        self._catalogs: list = []
        from datetime import timezone
        base = datetime(2020, 1, 1, tzinfo=timezone.utc)
        for c in range(num_catalogs):
            path = paths[c] if paths and c < len(paths) else []
            cat = Catalog(uuid=str(c), name=f"Catalog-{c}", provider=self, path=path)
            self._catalogs.append(cat)
            events = []
            for i in range(events_per_catalog):
                events.append(CatalogEvent(
                    uuid=f"{c}-{i}",
                    start=base + timedelta(days=i),
                    stop=base + timedelta(days=i, hours=1),
                    meta={"index": i, "catalog": c},
                ))
            self._set_events(cat, events)

    def catalogs(self):
        return list(self._catalogs)

    def capabilities(self, catalog=None):
        from SciQLop.components.catalogs.backend.provider import Capability
        return {
            Capability.EDIT_EVENTS, Capability.CREATE_EVENTS,
            Capability.DELETE_EVENTS, Capability.CREATE_CATALOGS,
            Capability.DELETE_CATALOGS, Capability.EXPORT_EVENTS,
            Capability.IMPORT_EVENTS, Capability.SAVE,
            Capability.SAVE_CATALOG, Capability.RENAME_CATALOG,
        }

    def create_catalog(self, name, path=None):
        cat = Catalog(uuid=str(len(self._catalogs)), name=name, provider=self, path=path or [])
        self._catalogs.append(cat)
        self._set_events(cat, [])
        self.catalog_added.emit(cat)
        return cat

    def remove_catalog(self, catalog):
        self._catalogs = [c for c in self._catalogs if c.uuid != catalog.uuid]
        super().remove_catalog(catalog)

    def import_events(self, catalog_name, events, path=None):
        cat = Catalog(uuid=str(len(self._catalogs)), name=catalog_name, provider=self, path=path or [])
        self._catalogs.append(cat)
        self._set_events(cat, events)
        self.catalog_added.emit(cat)
        return cat


@pytest.fixture
def dummy_provider(qtbot, qapp):
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    registry = CatalogRegistry.instance()
    provider = _IsolatedDummyProvider(
        num_catalogs=2, events_per_catalog=3,
        paths=[["room1"], ["room2"]],
    )
    yield provider
    registry.unregister(provider)


@pytest.fixture
def catalog_service(dummy_provider):
    from SciQLop.user_api.catalogs._service import CatalogService
    return CatalogService()


def test_list_all(catalog_service, dummy_provider):
    paths = catalog_service.list()
    assert len(paths) >= 2
    assert any("Catalog-0" in p for p in paths)
    assert any("Catalog-1" in p for p in paths)


def test_list_with_prefix(catalog_service, dummy_provider):
    paths = catalog_service.list("IsolatedDummy//room1")
    assert len(paths) == 1
    assert "Catalog-0" in paths[0]


def test_list_provider_only(catalog_service, dummy_provider):
    paths = catalog_service.list("IsolatedDummy")
    assert len(paths) == 2


def test_get_catalog(catalog_service, dummy_provider):
    from speasy.products.catalog import Catalog as SpeasyCatalog
    cat = catalog_service.get("IsolatedDummy//room1//Catalog-0")
    assert isinstance(cat, SpeasyCatalog)
    assert len(cat) == 3
    assert cat[0].meta["__sciqlop_uuid__"]


def test_get_not_found(catalog_service, dummy_provider):
    with pytest.raises(KeyError):
        catalog_service.get("IsolatedDummy//room1//NoSuchCatalog")


def test_get_bad_provider(catalog_service, dummy_provider):
    with pytest.raises(KeyError):
        catalog_service.get("NoSuchProvider//Catalog-0")


def test_save_existing_catalog(catalog_service, dummy_provider):
    cat = catalog_service.get("IsolatedDummy//room1//Catalog-0")
    assert len(cat) == 3

    from speasy.products.catalog import Catalog as SpeasyCatalog, Event as SpeasyEvent
    modified = SpeasyCatalog(name="Catalog-0", events=[
        cat[0],
        SpeasyEvent("2025-01-01", "2025-01-02", meta={"new": True}),
    ])
    catalog_service.save("IsolatedDummy//room1//Catalog-0", modified)

    reloaded = catalog_service.get("IsolatedDummy//room1//Catalog-0")
    assert len(reloaded) == 2
    assert reloaded[0].meta["__sciqlop_uuid__"] == cat[0].meta["__sciqlop_uuid__"]


def test_save_creates_if_missing(catalog_service, dummy_provider):
    catalog_service.save("IsolatedDummy//room1//Brand New", [
        ("2020-01-01", "2020-01-02"),
    ])
    cat = catalog_service.get("IsolatedDummy//room1//Brand New")
    assert len(cat) == 1


def test_save_bad_provider(catalog_service, dummy_provider):
    with pytest.raises(KeyError):
        catalog_service.save("NoSuchProvider//room//Cat", [("2020-01-01", "2020-01-02")])


def test_create_new_catalog(catalog_service, dummy_provider):
    catalog_service.create("IsolatedDummy//room3//New Cat", [
        ("2020-01-01", "2020-01-02"),
        ("2020-06-01", "2020-06-02", {"tag": "storm"}),
    ])
    cat = catalog_service.get("IsolatedDummy//room3//New Cat")
    assert len(cat) == 2
    assert cat[1].meta["tag"] == "storm"


def test_create_already_exists(catalog_service, dummy_provider):
    with pytest.raises(ValueError):
        catalog_service.create("IsolatedDummy//room1//Catalog-0", [])


def test_create_with_speasy_catalog(catalog_service, dummy_provider):
    from speasy.products.catalog import Catalog as SpeasyCatalog, Event as SpeasyEvent
    speasy_cat = SpeasyCatalog(name="FromSpeasy", events=[
        SpeasyEvent("2021-03-01", "2021-03-02"),
    ])
    catalog_service.create("IsolatedDummy//FromSpeasy", speasy_cat)
    result = catalog_service.get("IsolatedDummy//FromSpeasy")
    assert len(result) == 1


def test_remove_catalog(catalog_service, dummy_provider):
    catalog_service.remove("IsolatedDummy//room1//Catalog-0")
    with pytest.raises(KeyError):
        catalog_service.get("IsolatedDummy//room1//Catalog-0")
    assert len(catalog_service.list("IsolatedDummy")) == 1


def test_remove_not_found(catalog_service, dummy_provider):
    with pytest.raises(KeyError):
        catalog_service.remove("IsolatedDummy//room1//NoSuchCatalog")


class _CacheInvalidatingProvider(CatalogProvider):
    """Simulates tscat-like behavior:
    - add_event persists to a 'backend' and wipes the in-memory cache
    - remove_event trashes (not deletes) — re-adding with same UUID raises
    - This ensures _persist's diff logic works correctly."""

    def __init__(self, parent=None):
        super().__init__(name="CacheInvalidating", parent=parent)
        self._catalogs: list = []
        self._backend_events: dict[str, list[CatalogEvent]] = {}
        self._trashed_uuids: set[str] = set()

    def catalogs(self):
        return list(self._catalogs)

    def capabilities(self, catalog=None):
        from SciQLop.components.catalogs.backend.provider import Capability
        return {
            Capability.EDIT_EVENTS, Capability.CREATE_EVENTS,
            Capability.DELETE_EVENTS, Capability.CREATE_CATALOGS,
            Capability.DELETE_CATALOGS, Capability.SAVE,
        }

    def create_catalog(self, name, path=None):
        cat = Catalog(uuid=str(len(self._catalogs)), name=name, provider=self, path=path or [])
        self._catalogs.append(cat)
        self._backend_events[cat.uuid] = []
        self._set_events(cat, [])
        return cat

    def add_event(self, catalog, event):
        if event.uuid in self._trashed_uuids:
            raise RuntimeError(f"Cannot create entity with trashed UUID {event.uuid}")
        self._backend_events.setdefault(catalog.uuid, []).append(event)
        self._events.pop(catalog.uuid, None)  # simulate _on_action_done
        self._add_event(catalog, event)
        self.mark_dirty(catalog)

    def remove_event(self, catalog, event):
        backend = self._backend_events.get(catalog.uuid, [])
        self._backend_events[catalog.uuid] = [e for e in backend if e.uuid != event.uuid]
        self._trashed_uuids.add(event.uuid)
        super().remove_event(catalog, event)

    def remove_catalog(self, catalog):
        self._catalogs = [c for c in self._catalogs if c.uuid != catalog.uuid]
        self._backend_events.pop(catalog.uuid, None)
        super().remove_catalog(catalog)


@pytest.fixture
def cache_invalidating_provider(qtbot, qapp):
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    registry = CatalogRegistry.instance()
    provider = _CacheInvalidatingProvider()
    yield provider
    registry.unregister(provider)


@pytest.fixture
def cache_invalidating_service(cache_invalidating_provider):
    from SciQLop.user_api.catalogs._service import CatalogService
    return CatalogService()


def test_create_then_get_with_cache_invalidation(cache_invalidating_service):
    """Reproducer: create + get must return events even when the provider
    clears its in-memory cache during add_event (like tscat does)."""
    svc = cache_invalidating_service
    svc.create("CacheInvalidating//test_cat", [
        ("2020-01-01", "2020-01-02", {"tag": "a"}),
        ("2020-06-01", "2020-06-02", {"tag": "b"}),
        ("2020-12-01", "2020-12-02", {"tag": "c"}),
    ])
    cat = svc.get("CacheInvalidating//test_cat")
    assert len(cat) == 3
    assert cat[0].meta["tag"] == "a"
    assert cat[1].meta["tag"] == "b"
    assert cat[2].meta["tag"] == "c"


def test_save_then_get_with_cache_invalidation(cache_invalidating_service):
    """save (upsert) must also survive cache invalidation."""
    svc = cache_invalidating_service
    svc.save("CacheInvalidating//upsert_cat", [
        ("2020-01-01", "2020-01-02"),
        ("2020-06-01", "2020-06-02"),
    ])
    cat = svc.get("CacheInvalidating//upsert_cat")
    assert len(cat) == 2


def test_add_events_with_cache_invalidation(cache_invalidating_service):
    """add_events must survive cache invalidation."""
    svc = cache_invalidating_service
    svc.create("CacheInvalidating//append_cat", [("2020-01-01", "2020-01-02")])
    svc.add_events("CacheInvalidating//append_cat", [("2020-06-01", "2020-06-02")])
    cat = svc.get("CacheInvalidating//append_cat")
    assert len(cat) == 2


def test_remove_events_with_cache_invalidation(cache_invalidating_service):
    """remove_events must survive cache invalidation."""
    svc = cache_invalidating_service
    svc.create("CacheInvalidating//remove_cat", [
        ("2020-01-01", "2020-01-02"),
        ("2020-06-01", "2020-06-02"),
    ])
    cat = svc.get("CacheInvalidating//remove_cat")
    svc.remove_events("CacheInvalidating//remove_cat", [cat[0]])
    cat = svc.get("CacheInvalidating//remove_cat")
    assert len(cat) == 1


def test_import_catalogs_singleton():
    from SciQLop.user_api.catalogs import catalogs
    assert hasattr(catalogs, 'list')
    assert hasattr(catalogs, 'get')
    assert hasattr(catalogs, 'save')
    assert hasattr(catalogs, 'create')
    assert hasattr(catalogs, 'remove')
