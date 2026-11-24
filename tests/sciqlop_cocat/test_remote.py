import asyncio
import json

import pytest

from SciQLop.components.catalogs import Capability

from SciQLop.plugins.sciqlop_cocat.remote import RoomListener
from .conftest import HOUR, T0, only, own_catalogs


@pytest.fixture
def listener(attached):
    return RoomListener(attached, "r")


def _event(room, **kw):
    return room.create_event(start=T0, stop=T0 + HOUR, author="them", **kw)


def test_remote_catalogue_added_and_removed(attached, room, listener):
    cat = room.create_catalogue(name="theirs", author="them", attributes={"sciqlop_path": "f"})
    listener.catalogue_added(cat.uuid)
    assert (only(attached).name, only(attached).path) == ("theirs", ["r", "f"])
    listener.catalogue_added(cat.uuid)
    assert len(own_catalogs(attached)) == 1
    listener.catalogue_removed(cat.uuid)
    assert own_catalogs(attached) == []


def test_remote_rename_emits_catalog_renamed(attached, listener, qtbot):
    c = attached.create_catalog("old", ["r"])
    with qtbot.waitSignal(attached.catalog_renamed):
        listener.catalogue_renamed(c.uuid, "new")
    assert c.name == "new"


def test_remote_subpath_change_moves_catalog(attached, listener, qtbot):
    c = attached.create_catalog("n", ["r"])
    with qtbot.waitSignal(attached.catalog_moved):
        listener.catalogue_attributes(c.uuid, {"sciqlop_path": "a/b"}, [])
    assert c.path == ["r", "a", "b"]
    listener.catalogue_attributes(c.uuid, {}, ["sciqlop_path"])
    assert c.path == ["r"]


def test_remote_schema_set_and_removed(attached, listener, qtbot):
    from SciQLop.core.knobs import IntKnob, spec_to_dict
    c = attached.create_catalog("n", ["r"])
    spec = IntKnob(name="k", min=0, max=9, default=1)
    with qtbot.waitSignal(attached.attribute_spec_changed):
        listener.catalogue_attributes(c.uuid, {"sciqlop_schema__k": json.dumps(spec_to_dict(spec))}, [])
    assert spec_to_dict(attached.attribute_spec(c, "k")) == spec_to_dict(spec)
    listener.catalogue_attributes(c.uuid, {}, ["sciqlop_schema__k"])
    assert "k" not in attached._attribute_specs.get(c.uuid, {})


def test_remote_events_added_emits_events_changed_once(attached, room, listener, qtbot):
    c = attached.create_catalog("n", ["r"])
    events = [_event(room) for _ in range(50)]
    room.catalogue(c.uuid).add_events(events)
    changes = []
    attached.events_changed.connect(changes.append)
    listener.events_added(c.uuid, [e.uuid for e in events])
    assert len(attached.events(c)) == 50 and len(changes) == 1
    listener.events_removed(c.uuid, [e.uuid for e in events[:10]])
    assert len(attached.events(c)) == 40 and len(changes) == 2


def test_remote_events_added_keeps_fields_and_skips_gone_events(attached, room, listener):
    c = attached.create_catalog("n", ["r"])
    ev = room.create_event(start=T0, stop=T0 + HOUR, author="other", tags={"t"}, attributes={"k": 1})
    room.catalogue(c.uuid).add_events([ev])
    listener.events_added(c.uuid, ["gone", ev.uuid])
    [wrapper] = attached.events(c)
    assert (wrapper.uuid, wrapper.start, wrapper.stop, wrapper.meta["k"]) == (ev.uuid, T0, T0 + HOUR, 1)


def test_remote_event_range_updates_wrapper_and_is_not_echoed(attached, room, listener):
    c = attached.create_catalog("n", ["r"])
    ev = _event(room)
    listener.events_added(c.uuid, [ev.uuid])
    listener.event_range(ev.uuid, T0 + HOUR, T0 + 2 * HOUR)
    [wrapper] = attached.events(c)
    assert (wrapper.start, wrapper.stop) == (T0 + HOUR, T0 + 2 * HOUR)
    assert attached._pending_ranges == {}


def test_remote_event_attributes_set_and_removed(attached, room, listener, qtbot):
    c = attached.create_catalog("n", ["r"])
    ev = _event(room, attributes={"a": 1})
    listener.events_added(c.uuid, [ev.uuid])
    [wrapper] = attached.events(c)
    with qtbot.waitSignal(attached.event_meta_changed):
        listener.event_attributes(ev.uuid, {"b": 2}, ["a"])
    assert wrapper.meta == {"b": 2}


def test_remote_event_removed_leaves_every_catalogue(attached, room, listener):
    a = attached.create_catalog("a", ["r"])
    b = attached.create_catalog("b", ["r"])
    ev = _event(room)
    listener.events_added(a.uuid, [ev.uuid])
    listener.events_added(b.uuid, [ev.uuid])
    listener.event_removed(ev.uuid)
    assert attached.events(a) == [] and attached.events(b) == []
    assert ev.uuid not in attached._wrappers["r"]


def test_unknown_uuids_are_ignored(attached, listener):
    c = attached.create_catalog("n", ["r"])
    listener.catalogue_added("nope")
    listener.catalogue_removed("nope")
    listener.catalogue_renamed("nope", "x")
    listener.catalogue_attributes("nope", {"sciqlop_path": "a"}, [])
    listener.events_added("nope", ["nope"])
    listener.events_added(c.uuid, ["nope"])
    listener.events_removed("nope", ["nope"])
    listener.event_range("nope", T0, T0)
    listener.event_attributes("nope", {"a": 1}, [])
    listener.event_removed("nope")
    assert own_catalogs(attached) == [c] and attached.events(c) == []


def test_status_is_forwarded_to_the_provider(attached, listener, qtbot):
    with qtbot.waitSignal(attached.status_changed):
        listener.status("connecting")
    assert attached.room_status("r") == "connecting"


def test_listen_room_registers_a_listener_and_detach_closes_it(attached):
    async def listen():
        attached.listen_room("r")
    asyncio.run(listen())
    assert "r" in attached._listen_handles
    attached.detach_room("r")
    assert attached._listen_handles == {}


def test_remote_trash_and_restore_of_an_event(attached, room, listener):
    a, b = attached.create_catalog("a", ["r"]), attached.create_catalog("b", ["r"])
    ev = _event(room)
    for c in (a, b):
        room.catalogue(c.uuid).add_events([ev])
        listener.events_added(c.uuid, [ev.uuid])
    ev.delete()
    listener.event_fields(ev.uuid, {"status": "deleted"}, [])
    assert attached.events(a) == [] and attached.events(b) == []
    ev.restore()
    listener.event_fields(ev.uuid, {}, ["status"])
    assert [e.uuid for e in attached.events(a)] == [ev.uuid] == [e.uuid for e in attached.events(b)]


def test_remote_rule_change_refreshes_the_catalogue(attached, room, listener, qtbot):
    c = attached.create_catalog("n", ["r"])
    ev = _event(room, tags=["s"])
    room.catalogue(c.uuid).rule = {"filter": {"all": True}, "where": {"contains": ["tags", "s"]}}
    listener.catalogue_rule(c.uuid)  # read again in the background
    qtbot.waitUntil(lambda: [e.uuid for e in attached.events(c)] == [ev.uuid], timeout=5000)
    assert Capability.EDIT_EVENTS not in attached.capabilities(c)


def test_remote_tags_and_confidence_reach_the_event(attached, room, listener, qtbot):
    c = attached.create_catalog("n", ["r"])
    ev = _event(room)
    listener.events_added(c.uuid, [ev.uuid])
    [wrapper] = attached.events(c)
    room.event(ev.uuid).tags = {"shock"}
    room.event(ev.uuid).confidence = 0.4
    with qtbot.waitSignal(attached.event_meta_changed):
        listener.event_fields(ev.uuid, {"tags": ["shock"], "confidence": 0.4}, [])
    assert (wrapper.meta["tags"], wrapper.meta["rating"]) == (["shock"], 4)
