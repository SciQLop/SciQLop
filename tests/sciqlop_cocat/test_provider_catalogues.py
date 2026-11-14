import json

import pytest

from .conftest import HOUR, T0, only


def _schema(spec):
    from SciQLop.core.knobs import spec_to_dict
    return json.dumps(spec_to_dict(spec))


def test_attach_room_loads_catalogues_with_folder_path(provider, room):
    ev = room.create_event(start=T0, stop=T0 + HOUR, author="t", attributes={"note": "x"})
    room.create_catalogue(name="c", author="t", attributes={"sciqlop_path": "a/b"}, events=[ev])
    provider.attach_room("r", room)
    c = only(provider)
    assert (c.name, c.path) == ("c", ["r", "a", "b"])
    [event] = provider.events(c)
    assert (event.uuid, event.start, event.stop, event.meta) == (ev.uuid, T0, T0 + HOUR, {"note": "x"})


def test_attach_room_announces_the_room_folder(provider, room, qtbot):
    with qtbot.waitSignal(provider.folder_added) as signal:
        provider.attach_room("r", room)
    assert signal.args == [["r"]]


def test_attach_room_loads_persisted_schema(provider, room):
    from SciQLop.core.knobs import IntKnob, spec_to_dict
    spec = IntKnob(name="rating", min=1, max=5, default=2)
    room.create_catalogue(name="c", author="t", attributes={"sciqlop_schema__rating": _schema(spec)})
    provider.attach_room("r", room)
    assert spec_to_dict(provider.attribute_spec(only(provider), "rating")) == spec_to_dict(spec)


def test_event_in_two_catalogues_is_one_object(provider, room):
    ev = room.create_event(start=T0, stop=T0 + HOUR, author="t")
    room.create_catalogue(name="a", author="t", events=[ev])
    room.create_catalogue(name="b", author="t", events=[ev])
    provider.attach_room("r", room)
    a, b = provider.catalogs()
    assert provider.events(a)[0] is provider.events(b)[0]


def test_create_catalog_writes_room_and_subpath(attached, room, qtbot):
    with qtbot.waitSignal(attached.catalog_added):
        c = attached.create_catalog("n", ["r", "f"])
    assert room.catalogue(c.uuid).attributes["sciqlop_path"] == "f"
    assert room.catalogue(c.uuid).author == "me"
    assert c.path == ["r", "f"]


def test_create_catalog_without_path_uses_an_attached_room(attached):
    assert attached.create_catalog("n").path == ["r"]


def test_create_catalog_needs_a_room(provider):
    with pytest.raises(RuntimeError):
        provider.create_catalog("n")


def test_rename_and_remove_catalog_reach_room(attached, room, qtbot):
    c = attached.create_catalog("old", ["r"])
    attached.rename_catalog(c, "new")
    assert room.catalogue(c.uuid).name == "new" and c.name == "new"
    with qtbot.waitSignal(attached.catalog_removed):
        attached.remove_catalog(c)
    assert room.catalogues() == [] and attached.catalogs() == []


def test_move_catalog_updates_subpath_and_rejects_other_room(attached, room):
    c = attached.create_catalog("n", ["r", "f"])
    attached.move_catalog(c, ["r", "g", "h"])
    assert room.catalogue(c.uuid).attributes["sciqlop_path"] == "g/h"
    attached.move_catalog(c, ["r"])
    assert "sciqlop_path" not in room.catalogue(c.uuid).attributes
    assert c.path == ["r"]
    with pytest.raises(ValueError):
        attached.move_catalog(c, ["other"])


def test_set_attribute_spec_persists_as_catalogue_attribute(attached, room):
    from SciQLop.core.knobs import IntKnob
    c = attached.create_catalog("n", ["r"])
    spec = IntKnob(name="k", min=0, max=9, default=1)
    attached.set_attribute_spec(c, "k", spec)
    assert json.loads(room.catalogue(c.uuid).attributes["sciqlop_schema__k"]) == json.loads(_schema(spec))
    attached.remove_attribute_spec(c, "k")
    assert "sciqlop_schema__k" not in room.catalogue(c.uuid).attributes


def test_detach_room_clears_tree_and_capabilities(attached, room):
    attached.create_catalog("n", ["r"])
    assert attached.capabilities()
    assert attached.detach_room("r") is room
    assert attached.catalogs() == [] and attached.capabilities() == set()
