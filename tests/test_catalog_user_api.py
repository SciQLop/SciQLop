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


class _TrackingEvent(CatalogEvent):
    """Event whose range setters persist to a backend dict, like TscatEvent
    persists via SetAttributeAction."""

    @CatalogEvent.start.setter
    def start(self, value):
        CatalogEvent.start.fset(self, value)
        backend = getattr(self, "_backend", None)
        if backend is not None:
            backend[self.uuid]["start"] = self._start

    @CatalogEvent.stop.setter
    def stop(self, value):
        CatalogEvent.stop.fset(self, value)
        backend = getattr(self, "_backend", None)
        if backend is not None:
            backend[self.uuid]["stop"] = self._stop


class _PersistenceTrackingProvider(CatalogProvider):
    """Mirrors tscat's persistence model: event meta persists through
    set_event_meta/remove_event_meta (uuid-keyed), event ranges persist only
    through the cached event object's setters."""

    def __init__(self, parent=None):
        super().__init__(name="PersistTrack", parent=parent)
        self._catalogs: list = []
        self._backend: dict[str, dict] = {}

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
        cat = Catalog(uuid=f"ptp-{len(self._catalogs)}", name=name, provider=self, path=path or [])
        self._catalogs.append(cat)
        self._set_events(cat, [])
        return cat

    def add_event(self, catalog, event):
        self._backend[event.uuid] = {
            "start": event.start, "stop": event.stop, "meta": dict(event.meta),
        }
        tracked = _TrackingEvent(uuid=event.uuid, start=event.start,
                                 stop=event.stop, meta=event.meta)
        tracked._backend = self._backend
        self._add_event(catalog, tracked)
        self.mark_dirty(catalog)

    def remove_event(self, catalog, event):
        self._backend.pop(event.uuid, None)
        super().remove_event(catalog, event)

    def set_event_meta(self, catalog, event, key, value):
        if event.meta.get(key) == value:
            return
        self._backend[event.uuid]["meta"][key] = value
        event.set_meta(key, value)
        self.event_meta_changed.emit(catalog, event, key)
        self.mark_dirty(catalog)

    def remove_event_meta(self, catalog, event, key):
        if key not in event.meta:
            return
        self._backend[event.uuid]["meta"].pop(key, None)
        event.remove_meta(key)
        self.event_meta_changed.emit(catalog, event, key)
        self.mark_dirty(catalog)


@pytest.fixture
def tracking_provider(qtbot, qapp):
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    provider = _PersistenceTrackingProvider()
    yield provider
    CatalogRegistry.instance().unregister(provider)


@pytest.fixture
def tracking_service(tracking_provider):
    from SciQLop.user_api.catalogs._service import CatalogService
    return CatalogService()


def _utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_save_persists_modified_event_times(tracking_service, tracking_provider):
    """Round-trip get() -> edit times -> save() must reach the backend.

    Reproducer for the 2026-06-09 review finding: _persist diffs by uuid only,
    so an event present in both old and new (same uuid, changed times) was
    neither updated through the provider nor through the cached event object.
    """
    from speasy.products.catalog import Catalog as SpeasyCatalog, Event as SpeasyEvent
    svc = tracking_service
    svc.create("PersistTrack//cat", [("2020-01-01", "2020-01-02", {"tag": "a"})])
    cat = svc.get("PersistTrack//cat")
    uuid = cat[0].meta["__sciqlop_uuid__"]

    edited = SpeasyCatalog(name="cat", events=[
        SpeasyEvent(_utc(2021, 5, 5), _utc(2021, 5, 6), meta=dict(cat[0].meta)),
    ])
    svc.save("PersistTrack//cat", edited)

    assert tracking_provider._backend[uuid]["start"] == _utc(2021, 5, 5)
    assert tracking_provider._backend[uuid]["stop"] == _utc(2021, 5, 6)


def test_save_persists_modified_event_meta(tracking_service, tracking_provider):
    """Modified/removed meta keys on a surviving uuid must go through
    set_event_meta/remove_event_meta so backends persist them."""
    from speasy.products.catalog import Catalog as SpeasyCatalog, Event as SpeasyEvent
    svc = tracking_service
    svc.create("PersistTrack//cat", [
        ("2020-01-01", "2020-01-02", {"tag": "a", "doomed": 1}),
    ])
    cat = svc.get("PersistTrack//cat")
    uuid = cat[0].meta["__sciqlop_uuid__"]

    new_meta = {"tag": "b", "fresh": True, "__sciqlop_uuid__": uuid}
    edited = SpeasyCatalog(name="cat", events=[
        SpeasyEvent(cat[0].start_time, cat[0].stop_time, meta=new_meta),
    ])
    svc.save("PersistTrack//cat", edited)

    backend_meta = tracking_provider._backend[uuid]["meta"]
    assert backend_meta["tag"] == "b"
    assert backend_meta["fresh"] is True
    assert "doomed" not in backend_meta


def test_save_preserves_cached_event_identity(tracking_service, tracking_provider):
    """Surviving events must keep their cached object identity so
    persistence-wired wrappers (TscatEvent-style) stay in the cache."""
    from speasy.products.catalog import Catalog as SpeasyCatalog, Event as SpeasyEvent
    svc = tracking_service
    svc.create("PersistTrack//cat", [("2020-01-01", "2020-01-02", {"tag": "a"})])
    cat_obj = tracking_provider.catalogs()[0]
    before = tracking_provider.events(cat_obj)[0]

    cat = svc.get("PersistTrack//cat")
    edited = SpeasyCatalog(name="cat", events=[
        SpeasyEvent(_utc(2022, 1, 1), _utc(2022, 1, 2), meta=dict(cat[0].meta)),
    ])
    svc.save("PersistTrack//cat", edited)

    after = tracking_provider.events(cat_obj)[0]
    assert after is before
    assert isinstance(after, _TrackingEvent)
    assert after.start == _utc(2022, 1, 1)


def test_save_emits_events_changed_once(tracking_service, tracking_provider, qapp):
    """Bulk saves must coalesce events_changed into one emission — per-event
    emissions made overlay/table refreshes O(N²) (2026-06-09 review, P1)."""
    svc = tracking_service
    svc.create("PersistTrack//bulk", [("2020-01-01", "2020-01-02")])

    counts = []
    tracking_provider.events_changed.connect(lambda c: counts.append(c))
    svc.save("PersistTrack//bulk", [
        ("2021-01-01", "2021-01-02"),
        ("2021-02-01", "2021-02-02"),
        ("2021-03-01", "2021-03-02"),
    ])
    assert len(counts) == 1


def test_service_methods_marshal_to_main_thread(tracking_service, tracking_provider, qapp):
    """Reproducer (2026-06-09 review): CatalogService methods emit provider
    signals and mutate provider dicts, but carried no @on_main_thread — calls
    from the Jupyter kernel thread ran Qt code off the main thread."""
    import threading as _threading
    from SciQLop.user_api import threading as sqp_threading

    routed = []

    def recording_invoker(func, *args, **kwargs):
        routed.append(getattr(func, "__name__", str(func)))
        return func(*args, **kwargs)

    old_invoker = sqp_threading._invoker
    sqp_threading.init_invoker(recording_invoker)
    try:
        errors = []

        def worker():
            try:
                tracking_service.create("PersistTrack//threaded", [("2020-01-01", "2020-01-02")])
                tracking_service.list("PersistTrack")
                tracking_service.get("PersistTrack//threaded")
                tracking_service.remove("PersistTrack//threaded")
            except Exception as e:  # surfaced below; thread must not swallow
                errors.append(e)

        t = _threading.Thread(target=worker)
        t.start()
        t.join(timeout=10)
        assert not errors, errors
        assert len(routed) >= 4, \
            f"service calls from a worker thread must marshal through the invoker, got {routed}"
    finally:
        sqp_threading.init_invoker(old_invoker)


def test_import_catalogs_singleton():
    from SciQLop.user_api.catalogs import catalogs
    assert hasattr(catalogs, 'list')
    assert hasattr(catalogs, 'get')
    assert hasattr(catalogs, 'save')
    assert hasattr(catalogs, 'create')
    assert hasattr(catalogs, 'remove')


# ---------------------------------------------------------------------------
# Round-2 fuzzing validation (docs/api-fuzzing-report-round2-2026-06-12.md)
# ---------------------------------------------------------------------------

class TestEventOrderingValidation:
    """R2-1 — the user-api path stored events that tscat itself rejects
    (start > stop), silently desyncing the two stores. Mirror tscat's rule
    (`start > stop` raises, start == stop is allowed) at the API boundary,
    before anything is created or dispatched."""

    def test_save_rejects_inverted_event(self, catalog_service, dummy_provider):
        with pytest.raises(ValueError, match="before stop"):
            catalog_service.save("IsolatedDummy//inverted",
                                 [("2020-01-02", "2020-01-01")])

    def test_save_rejects_inverted_event_before_creating_catalog(
            self, catalog_service, dummy_provider):
        with pytest.raises(ValueError):
            catalog_service.save("IsolatedDummy//inverted",
                                 [("2020-01-02", "2020-01-01")])
        assert "IsolatedDummy//inverted" not in catalog_service.list()

    def test_create_rejects_inverted_event(self, catalog_service, dummy_provider):
        with pytest.raises(ValueError, match="before stop"):
            catalog_service.create("IsolatedDummy//inverted2",
                                   [("2020-01-02", "2020-01-01")])

    def test_add_events_rejects_inverted_event(self, catalog_service, dummy_provider):
        with pytest.raises(ValueError, match="before stop"):
            catalog_service.add_events("IsolatedDummy//room1//Catalog-0",
                                       [("2020-01-02", "2020-01-01")])

    def test_save_rejects_inverted_event_in_speasy_catalog(
            self, catalog_service, dummy_provider):
        from speasy.products.catalog import Catalog as SpeasyCatalog, Event as SpeasyEvent

        cat = SpeasyCatalog(name="x", events=[SpeasyEvent("2020-01-02", "2020-01-01")])
        with pytest.raises(ValueError, match="before stop"):
            catalog_service.save("IsolatedDummy//inverted3", cat)

    def test_zero_duration_event_is_allowed(self, catalog_service, dummy_provider):
        catalog_service.save("IsolatedDummy//instant",
                             [("2020-01-01", "2020-01-01")])
        events = catalog_service.get("IsolatedDummy//instant")
        assert len(events) == 1


class TestCatalogInputTypeErrors:
    """R2-8 / R2-13 — raw AttributeError / cryptic dict-update errors on
    wrong input types."""

    def test_get_none_path_raises_type_error(self, catalog_service, dummy_provider):
        with pytest.raises(TypeError, match="path must be a str"):
            catalog_service.get(None)

    def test_save_none_path_raises_type_error(self, catalog_service, dummy_provider):
        with pytest.raises(TypeError, match="path must be a str"):
            catalog_service.save(None, [("2020-01-01", "2020-01-02")])

    def test_non_dict_meta_raises_type_error(self, catalog_service, dummy_provider):
        with pytest.raises(TypeError, match="meta must be a dict"):
            catalog_service.save("IsolatedDummy//meta",
                                 [("2020-01-01", "2020-01-02", "not_a_dict")])


def test_a_path_without_a_folder_means_the_provider_s_default_folder(qapp):
    """A provider that keeps every catalogue in a folder (cocat-rs: a project) names the one a
    notebook path without a folder means."""
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    from SciQLop.user_api.catalogs._service import CatalogService

    class InFolders(DummyProvider):
        def __init__(self):
            super().__init__(num_catalogs=0, events_per_catalog=0, name="In folders")

        def default_folder(self):
            return ["home"]

    provider = InFolders()
    try:
        service = CatalogService()
        service.create("In folders//x", [("2020-01-01", "2020-01-02")])
        assert [c.path for c in provider.catalogs() if c.name == "x"] == [["home"]]
        assert len(service.get("In folders//x")) == 1
        assert len(service.get("In folders//home//x")) == 1
    finally:
        CatalogRegistry.instance()._forget_for_tests(provider)
