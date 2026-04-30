"""Cocat MOVE_CATALOG: same-room moves persist via set_attributes/
remove_attributes, cross-room moves are rejected, and remote attribute
changes update the local catalog path."""
from .fixtures import *
import uuid as _uuid


class _FakeCocatCatalogue:
    """Mimics cocat.Catalogue's interface for set/remove_attributes,
    on_set_attributes, on_remove_attributes."""

    def __init__(self, name: str, attributes: dict | None = None):
        self.uuid = _uuid.uuid4()
        self.name = name
        self.attributes = dict(attributes or {})
        self._set_callbacks: list = []
        self._remove_callbacks: list = []
        self._delete_callbacks: list = []
        self._rename_callbacks: list = []
        self._add_event_callbacks: list = []
        self._remove_event_callbacks: list = []
        self.events = []

    def set_attributes(self, **kwargs):
        self.attributes.update(kwargs)
        for cb in list(self._set_callbacks):
            cb(kwargs)

    def remove_attributes(self, keys):
        keys = [keys] if isinstance(keys, str) else list(keys)
        for k in keys:
            self.attributes.pop(k, None)
        for cb in list(self._remove_callbacks):
            cb(keys)

    def on_set_attributes(self, cb): self._set_callbacks.append(cb)
    def on_remove_attributes(self, cb): self._remove_callbacks.append(cb)
    def on_delete(self, cb): self._delete_callbacks.append(cb)
    def on_change_name(self, cb): self._rename_callbacks.append(cb)
    def on_add_events(self, cb): self._add_event_callbacks.append(cb)
    def on_remove_events(self, cb): self._remove_event_callbacks.append(cb)


class _FakeRoom:
    """Mimics what CocatCatalogProvider needs from a Room."""
    def __init__(self, room_id: str):
        self.room_id = room_id
        self._catalogues: dict[str, _FakeCocatCatalogue] = {}
        self.catalogues: list[str] = []  # required by _load_room_catalogs
        self.db = None  # not used in these tests

    def add_fake(self, cat: _FakeCocatCatalogue):
        self._catalogues[str(cat.uuid)] = cat

    def get_catalogue(self, uuid_or_name):
        key = str(uuid_or_name)
        return self._catalogues.get(key)


def _make_provider_with_room(room_id: str = "room_a"):
    from SciQLop.plugins.collaborative_catalogs.cocat_provider import CocatCatalogProvider
    p = CocatCatalogProvider.__new__(CocatCatalogProvider)
    # Minimal init bypassing the WebSocket login flow
    p._url = ""
    p._catalog_map = {}
    p._available_rooms = []
    p._default_room_id = room_id
    p._connected = True
    p._client_for_listing = None
    room = _FakeRoom(room_id)
    p._rooms = {room_id: room}
    # CatalogProvider.__init__ wires QObject + registry; do it the safe way
    from SciQLop.components.catalogs.backend.provider import CatalogProvider
    CatalogProvider.__init__(p, name="Shared")
    return p, room


def _wrap(provider, room: _FakeRoom, name: str, attributes=None):
    from SciQLop.components.catalogs.backend.provider import Catalog
    fake = _FakeCocatCatalogue(name=name, attributes=attributes)
    room.add_fake(fake)
    cat = Catalog(uuid=str(fake.uuid), name=name, provider=provider,
                  path=[room.room_id])
    provider._catalog_map[cat.uuid] = cat
    provider._set_events(cat, [])
    provider._subscribe_catalogue(fake, cat)
    return cat, fake


def test_move_within_same_room_writes_subpath_attribute(qtbot, qapp):
    provider, room = _make_provider_with_room("room_a")
    cat, fake = _wrap(provider, room, "MyCatalog")

    provider.move_catalog(cat, ["room_a", "folder_x", "folder_y"])

    assert cat.path == ["room_a", "folder_x", "folder_y"]
    assert fake.attributes.get("sciqlop_path") == "folder_x/folder_y"


def test_move_to_room_root_removes_subpath_attribute(qtbot, qapp):
    provider, room = _make_provider_with_room("room_a")
    cat, fake = _wrap(provider, room, "MyCatalog",
                      attributes={"sciqlop_path": "old/path"})
    cat.path = ["room_a", "old", "path"]

    provider.move_catalog(cat, ["room_a"])

    assert cat.path == ["room_a"]
    assert "sciqlop_path" not in fake.attributes


def test_move_across_rooms_is_rejected(qtbot, qapp):
    import pytest
    provider, room = _make_provider_with_room("room_a")
    cat, fake = _wrap(provider, room, "MyCatalog")

    with pytest.raises(ValueError, match="across cocat rooms"):
        provider.move_catalog(cat, ["room_b", "folder"])

    # Original state untouched
    assert cat.path == ["room_a"]
    assert fake.attributes == {}


def test_move_to_unjoined_room_is_rejected(qtbot, qapp):
    import pytest
    provider, room = _make_provider_with_room("room_a")
    cat, fake = _wrap(provider, room, "MyCatalog")
    # Pretend the catalog claims to live in an unjoined room
    cat.path = ["room_unjoined"]

    with pytest.raises(KeyError):
        provider.move_catalog(cat, ["room_unjoined", "x"])


def test_remote_subpath_attribute_set_emits_catalog_moved(qtbot, qapp):
    provider, room = _make_provider_with_room("room_a")
    cat, fake = _wrap(provider, room, "MyCatalog")

    moves: list = []
    provider.catalog_moved.connect(lambda c: moves.append(list(c.path)))

    fake.set_attributes(sciqlop_path="new/folder")

    assert cat.path == ["room_a", "new", "folder"]
    assert moves == [["room_a", "new", "folder"]]


def test_remote_subpath_attribute_removed_resets_to_room_root(qtbot, qapp):
    provider, room = _make_provider_with_room("room_a")
    cat, fake = _wrap(provider, room, "MyCatalog",
                      attributes={"sciqlop_path": "deep/path"})
    cat.path = ["room_a", "deep", "path"]

    moves: list = []
    provider.catalog_moved.connect(lambda c: moves.append(list(c.path)))

    fake.remove_attributes(["sciqlop_path"])

    assert cat.path == ["room_a"]
    assert moves == [["room_a"]]


def test_remote_unrelated_attribute_change_does_not_emit(qtbot, qapp):
    provider, room = _make_provider_with_room("room_a")
    cat, fake = _wrap(provider, room, "MyCatalog")

    moves: list = []
    provider.catalog_moved.connect(lambda c: moves.append(list(c.path)))

    fake.set_attributes(some_other_key="value")

    assert moves == []
    assert cat.path == ["room_a"]


def test_capabilities_include_move_when_room_joined(qtbot, qapp):
    from SciQLop.components.catalogs.backend.provider import Capability
    provider, room = _make_provider_with_room("room_a")
    assert Capability.MOVE_CATALOG in provider.capabilities()
