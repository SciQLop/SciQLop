from .fixtures import *
import pytest
from datetime import datetime, timezone


def test_parse_path_single_slash():
    from SciQLop.user_api.catalogs._service import _parse_path
    provider, path, name = _parse_path("tscat/My Catalog")
    assert provider == "tscat"
    assert path == []
    assert name == "My Catalog"


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


def test_parse_path_name_with_slash():
    from SciQLop.user_api.catalogs._service import _parse_path
    provider, path, name = _parse_path("cocat//room1//Cat/with slash")
    assert provider == "cocat"
    assert path == ["room1"]
    assert name == "Cat/with slash"


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


@pytest.fixture
def dummy_provider(qtbot, qapp):
    from SciQLop.components.catalogs.backend.dummy_provider import DummyProvider
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    registry = CatalogRegistry.instance()
    old_providers = list(registry._providers)
    provider = DummyProvider(
        num_catalogs=2, events_per_catalog=3,
        paths=[["room1"], ["room2"]],
    )
    registry.register(provider)
    yield provider
    registry._providers = old_providers


@pytest.fixture
def catalog_service(dummy_provider):
    from SciQLop.user_api.catalogs._service import CatalogService
    return CatalogService()


def test_list_all(catalog_service, dummy_provider):
    paths = catalog_service.list()
    assert len(paths) == 2
    assert all("//" in p for p in paths)
    assert any("Catalog-0" in p for p in paths)
    assert any("Catalog-1" in p for p in paths)


def test_list_with_prefix(catalog_service, dummy_provider):
    paths = catalog_service.list("DummyProvider//room1")
    assert len(paths) == 1
    assert "Catalog-0" in paths[0]


def test_list_provider_only(catalog_service, dummy_provider):
    paths = catalog_service.list("DummyProvider")
    assert len(paths) == 2


def test_get_catalog(catalog_service, dummy_provider):
    from speasy.products.catalog import Catalog as SpeasyCatalog
    cat = catalog_service.get("DummyProvider//room1//Catalog-0")
    assert isinstance(cat, SpeasyCatalog)
    assert len(cat) == 3
    assert cat[0].meta["__sciqlop_uuid__"]


def test_get_not_found(catalog_service, dummy_provider):
    with pytest.raises(KeyError):
        catalog_service.get("DummyProvider//room1//NoSuchCatalog")


def test_get_bad_provider(catalog_service, dummy_provider):
    with pytest.raises(KeyError):
        catalog_service.get("NoSuchProvider//Catalog-0")
