import uuid as _uuid

import cocat_rs
import pytest

from SciQLop.components.catalogs import Capability, CatalogEvent

from .conftest import HOUR, T0, loaded, own_catalogs


def _new_event(**meta):
    return CatalogEvent(uuid=str(_uuid.uuid4()), start=T0, stop=T0 + HOUR, meta=meta)


def _catalog_with_event(provider, **meta):
    c = provider.create_catalog("c", ["r"])
    ev = _new_event(**meta)
    provider.add_event(c, ev)
    return c, provider.events(c)[0]


def test_add_event_keeps_typed_fields_and_attributes(attached, room):
    c, wrapper = _catalog_with_event(attached, tags=["a"], rating=3, note="n")
    stored = room.event(wrapper.uuid)
    assert (stored.tags, stored.confidence, stored.attributes) == ({"a"}, 0.3, {"note": "n"})
    assert stored.author == "me"
    assert room.catalogue(c.uuid).event_arrays()["uuid"] == [wrapper.uuid]
    assert (wrapper.start, wrapper.stop) == (T0, T0 + HOUR)


def test_adding_an_event_already_in_the_room_links_it(attached, room):
    a, wrapper = _catalog_with_event(attached)
    b = attached.create_catalog("b", ["r"])
    attached.add_event(b, CatalogEvent(uuid=wrapper.uuid, start=T0, stop=T0 + HOUR))
    assert room.catalogue(b.uuid).event_arrays()["uuid"] == [wrapper.uuid]
    assert attached.events(b)[0] is wrapper


def test_remove_event_deletes_from_room(attached, room):
    c, wrapper = _catalog_with_event(attached)
    attached.remove_event(c, wrapper)
    assert attached.events(c) == []
    assert room.catalogue(c.uuid).event_arrays()["uuid"] == []
    assert room.event(wrapper.uuid).status == "deleted"
    assert [e.uuid for e in room.trash()] == [wrapper.uuid]


def test_remove_event_keeps_it_when_another_catalogue_holds_it(attached, room):
    a, wrapper = _catalog_with_event(attached)
    b = attached.create_catalog("b", ["r"])
    attached.add_event(b, CatalogEvent(uuid=wrapper.uuid, start=T0, stop=T0 + HOUR))
    attached.remove_event(a, wrapper)
    assert room.event(wrapper.uuid).uuid == wrapper.uuid
    assert room.catalogue(b.uuid).event_arrays()["uuid"] == [wrapper.uuid]


def test_remove_event_keeps_it_when_a_catalogue_not_yet_loaded_holds_it(attached, room):
    a, wrapper = _catalog_with_event(attached)
    unseen = room.create_catalogue(name="remote, not announced yet", author="other")
    unseen.add_events([wrapper.uuid])
    attached.remove_event(a, wrapper)
    assert room.event(wrapper.uuid).catalogues == [unseen.uuid]


def test_set_event_meta_updates_wrapper_and_room(attached, room, qtbot):
    c, wrapper = _catalog_with_event(attached)
    with qtbot.waitSignal(attached.event_meta_changed):
        attached.set_event_meta(c, wrapper, "k", 1)
    assert wrapper.meta["k"] == 1 and room.event(wrapper.uuid).attributes["k"] == 1
    attached.remove_event_meta(c, wrapper, "k")
    assert "k" not in wrapper.meta and "k" not in room.event(wrapper.uuid).attributes


def _reread(room, catalog):
    from SciQLop.plugins.sciqlop_cocat.convert import rows_of
    [row] = rows_of(room.catalogue(catalog.uuid).event_arrays(attributes=True))
    return row.meta


def test_editing_tags_and_rating_writes_the_typed_fields(attached, room):
    c, wrapper = _catalog_with_event(attached, tags=["a"], rating=3)
    attached.set_event_meta(c, wrapper, "tags", ["b", "c"])
    attached.set_event_meta(c, wrapper, "rating", 7)
    stored = room.event(wrapper.uuid)
    assert (stored.tags, stored.confidence, stored.attributes) == ({"b", "c"}, 0.7, {})
    assert _reread(room, c) == {"tags": ["b", "c"], "rating": 7}
    assert (wrapper.meta["tags"], wrapper.meta["rating"]) == (["b", "c"], 7)


def test_removing_tags_and_rating_clears_the_typed_fields(attached, room):
    c, wrapper = _catalog_with_event(attached, tags=["a"], rating=3, note="n")
    attached.remove_event_meta(c, wrapper, "tags")
    attached.remove_event_meta(c, wrapper, "rating")
    stored = room.event(wrapper.uuid)
    assert (stored.tags, stored.confidence) == (set(), None)
    assert _reread(room, c) == {"note": "n"}
    assert "tags" not in wrapper.meta and "rating" not in wrapper.meta


def test_editing_drops_the_plain_tags_and_rating_older_sciqlop_wrote(attached, room):
    c, wrapper = _catalog_with_event(attached)
    room.event(wrapper.uuid).set_attributes(tags=["old"], rating=5)
    attached.set_event_meta(c, wrapper, "tags", ["new"])
    attached.set_event_meta(c, wrapper, "rating", 8)
    assert room.event(wrapper.uuid).attributes == {}
    attached.remove_event_meta(c, wrapper, "rating")
    assert _reread(room, c) == {"tags": ["new"]}


def test_editing_the_rating_of_several_events_writes_each_confidence(attached, room):
    c, first = _catalog_with_event(attached, rating=3)
    attached.add_event(c, _new_event(rating=4))
    attached.set_events_meta(c, attached.events(c), "rating", 9)
    assert {room.event(e.uuid).confidence for e in attached.events(c)} == {0.9}


def test_set_events_meta_writes_every_event(attached, room):
    c = attached.create_catalog("c", ["r"])
    for _ in range(3):
        attached.add_event(c, _new_event())
    attached.set_events_meta(c, attached.events(c), "k", 2)
    assert all(room.event(e.uuid).attributes["k"] == 2 for e in attached.events(c))


def test_range_edits_are_debounced_into_one_write(attached, room, qtbot):
    c, wrapper = _catalog_with_event(attached)
    for hours in (2, 3, 4):
        wrapper.stop = T0 + hours * HOUR
    assert room.event(wrapper.uuid).stop == T0 + HOUR
    qtbot.waitUntil(lambda: room.event(wrapper.uuid).stop == T0 + 4 * HOUR, timeout=2000)


def test_flush_ranges_writes_every_pending_event(attached, room):
    c = attached.create_catalog("c", ["r"])
    attached.add_event(c, _new_event())
    attached.add_event(c, _new_event())
    for e in attached.events(c):
        e.start = T0 - HOUR
    attached.flush_ranges()
    assert all(room.event(e.uuid).start == T0 - HOUR for e in attached.events(c))


def test_range_change_inside_remote_changes_is_not_queued(attached):
    c, wrapper = _catalog_with_event(attached)
    with attached.remote_changes():
        wrapper.apply_remote_range(T0, T0 + 5 * HOUR)
    assert wrapper.stop == T0 + 5 * HOUR
    assert attached._pending_ranges == {}


def test_detach_flushes_pending_ranges(attached, room):
    c, wrapper = _catalog_with_event(attached)
    wrapper.stop = T0 + 7 * HOUR
    attached.detach_room("r")
    assert room.event(wrapper.uuid).stop == T0 + 7 * HOUR


def test_edits_on_an_event_deleted_remotely_do_not_raise(attached, room):
    c, wrapper = _catalog_with_event(attached)
    room.event(wrapper.uuid).delete()  # a remote delete whose listener call has not run yet
    attached.set_event_meta(c, wrapper, "k", 1)
    assert "k" not in wrapper.meta
    attached.remove_event_meta(c, wrapper, "k")
    attached.remove_event(c, wrapper)
    assert attached.events(c) == []


def _smart(provider, room, name="smart", tag="s"):
    cocat_cat = room.create_catalogue(name=name, author="other")
    cocat_cat.rule = {"merge": {"filter": {"all": True}, "where": {"contains": ["tags", tag]}}, "gap": 0}
    return provider._wrap_catalogue("r", cocat_cat)


def test_smart_catalogue_shows_derived_intervals_read_only(attached, room, qtbot):
    c = attached.create_catalog("plain", ["r"])
    attached.add_event(c, _new_event(tags=["s"]))
    attached.add_event(c, CatalogEvent(uuid=str(_uuid.uuid4()), start=T0 + HOUR / 2, stop=T0 + 2 * HOUR,
                                       meta={"tags": ["s"]}))
    smart = _smart(attached, room)
    [merged] = loaded(attached, smart, qtbot)
    assert (merged.start, merged.stop) == (T0, T0 + 2 * HOUR)
    assert attached.capabilities(smart) & {Capability.EDIT_EVENTS, Capability.CREATE_EVENTS,
                                           Capability.DELETE_EVENTS} == set()
    assert Capability.EDIT_EVENTS in attached.capabilities(c)
    attached.set_event_meta(smart, merged, "k", 1)
    merged.stop = T0 + 5 * HOUR
    attached.flush_ranges()
    assert "k" not in merged.meta


def test_smart_catalogue_follows_local_edits(attached, room, qtbot):
    smart = _smart(attached, room)
    assert attached.events(smart) == []
    c = attached.create_catalog("plain", ["r"])
    attached.add_event(c, _new_event(tags=["s"]))
    qtbot.waitUntil(lambda: len(attached.events(smart)) == 1)


def test_a_smart_catalogue_reuses_the_intervals_it_already_shows(attached, room, qtbot):
    """A smart catalogue over public ones holds thousands of rows: one new QObject each per read is too many."""
    c = attached.create_catalog("plain", ["r"])
    attached.add_event(c, _new_event(tags=["s"]))
    smart = _smart(attached, room)
    [first] = loaded(attached, smart, qtbot)
    attached.add_event(c, CatalogEvent(uuid=str(_uuid.uuid4()), start=T0 + 10 * HOUR, stop=T0 + 11 * HOUR,
                                       meta={"tags": ["s"]}))
    qtbot.waitUntil(lambda: len(attached.events(smart)) == 2)
    assert attached.events(smart)[0] is first


# ---- a catalogue this cocat-rs cannot read ----

NEWER_RULE = "rule.filter: not a set: expected one of all, catalogue, filter"


class _Unreadable:
    """A catalogue whose rule a newer cocat-rs wrote: reading it raises, as an older cocat-rs does."""

    def __init__(self, cocat_cat):
        self._cat = cocat_cat

    def __getattr__(self, name):
        if name in ("rule", "event_arrays"):
            raise ValueError(NEWER_RULE)
        return getattr(self._cat, name)


class _RoomWithOneUnreadable:
    def __init__(self, room, bad_uuid):
        self._room, self._bad = room, bad_uuid

    def _wrap(self, cocat_cat):
        return _Unreadable(cocat_cat) if cocat_cat.uuid == self._bad else cocat_cat

    def catalogues(self):
        return [self._wrap(c) for c in self._room.catalogues()]

    def catalogue(self, uuid):
        return self._wrap(self._room.catalogue(uuid))

    def __getattr__(self, name):
        return getattr(self._room, name)


@pytest.fixture
def one_unreadable(provider, room):
    good = room.create_catalogue(name="good", author="me")
    good.add_events([room.create_event(start=T0, stop=T0 + HOUR, author="me").uuid])
    bad = room.create_catalogue(name="bad", author="other")
    provider.attach_room("r", _RoomWithOneUnreadable(room, bad.uuid))
    return provider, {c.name: c for c in own_catalogs(provider)}


def test_a_catalogue_that_cannot_be_read_leaves_the_rest_of_the_project_open(one_unreadable):
    provider, catalogs = one_unreadable
    assert set(catalogs) == {"good", "bad"}
    assert len(provider.events(catalogs["good"])) == 1 and provider.events(catalogs["bad"]) == []


def test_it_says_why_and_offers_no_edit(one_unreadable):
    from SciQLop.components.catalogs.backend.provider import NodeType
    provider, catalogs = one_unreadable
    tip = provider.node_tooltip(NodeType.CATALOG, catalog=catalogs["bad"])
    assert "Invalid rule" in tip and "not a set" in tip and "update" not in tip
    assert provider.capabilities(catalogs["bad"]) & {Capability.EDIT_EVENTS, Capability.CREATE_EVENTS} == set()


def test_the_status_bar_hears_of_it_once(provider, room):
    told = []
    provider.error_occurred.connect(told.append)
    bad = room.create_catalogue(name="bad", author="other")
    provider.attach_room("r", _RoomWithOneUnreadable(room, bad.uuid))
    [catalog] = own_catalogs(provider)
    provider.reload_catalog(catalog)
    provider.reload_catalog(catalog)
    assert len(told) == 1 and "bad" in told[0] and "rule" in told[0] and "not a set" in told[0]


def test_re_reading_it_does_not_raise(one_unreadable):
    provider, catalogs = one_unreadable
    provider.reload_catalog(catalogs["bad"])
    assert provider.events(catalogs["bad"]) == []


# ---- moved from the tscat provider's tests: the generic drop and meta paths, on a real project ----

def test_a_dropped_event_linked_into_another_catalogue_is_in_both(attached, room):
    source, wrapper = _catalog_with_event(attached)
    target = attached.create_catalog("target", ["r"])

    attached.handle_event_drop(target_catalog=target, events=[wrapper], action="link", source_catalog=source)

    assert [e.uuid for e in attached.events(source)] == [wrapper.uuid]
    assert [e.uuid for e in attached.events(target)] == [wrapper.uuid]
    assert len(room.catalogue(target.uuid).events) == 1


def test_a_dropped_event_moved_changes_catalogue_and_keeps_the_event(attached, room):
    source, wrapper = _catalog_with_event(attached)
    target = attached.create_catalog("target", ["r"])

    attached.handle_event_drop(target_catalog=target, events=[wrapper], action="move", source_catalog=source)

    assert attached.events(source) == [] and [e.uuid for e in attached.events(target)] == [wrapper.uuid]
    assert room.event(wrapper.uuid).status != "deleted"


def test_setting_an_absent_key_to_none_is_a_change(attached, qtbot):
    c, wrapper = _catalog_with_event(attached)
    with qtbot.waitSignal(attached.event_meta_changed):
        attached.set_event_meta(c, wrapper, "note", None)
    assert "note" in wrapper.meta and wrapper.meta["note"] is None


def test_a_re_read_brings_new_tags_and_rating_and_says_so(attached, room, qtbot):
    smart = attached.create_catalog("tagged", ["r"])
    plain, wrapper = _catalog_with_event(attached, tags=["s"], rating=2)
    room.catalogue(smart.uuid).rule = {"filter": {"all": True}, "where": {"contains": ["tags", "s"]}}
    attached.reload_catalog(smart)
    [member] = attached.events(smart)
    room.event(member.uuid).confidence = 0.9
    with qtbot.waitSignal(attached.events_changed):
        attached.reload_catalog(smart)
    assert attached.events(smart)[0].meta["rating"] == 9


def test_a_smart_catalogue_has_a_funnel_icon_a_plain_one_the_default(attached, room):
    from SciQLop.components.catalogs.backend.color_palette import catalog_swatch_icon
    plain = attached.create_catalog("plain", ["r"])
    smart = attached.create_catalog("smart", ["r"])
    room.catalogue(smart.uuid).rule = {"filter": {"all": True}, "where": {"contains": ["tags", "s"]}}
    attached.reload_catalog(smart)
    assert attached.catalog_icon(plain) is None
    funnel = catalog_swatch_icon(smart.uuid, shape="funnel").pixmap(16, 16).toImage()
    assert attached.catalog_icon(smart).pixmap(16, 16).toImage() == funnel


def test_a_range_edited_inside_out_is_refused_alone_and_said(attached, room):
    """cocat-rs 0.11 refuses a stop before the start: one such edit failed the whole batch of range
    writes, and the other events' edits were lost with it."""
    c, good = _catalog_with_event(attached)
    attached.add_event(c, _new_event())
    bad = next(e for e in attached.events(c) if e is not good)
    told = []
    attached.error_occurred.connect(told.append)
    good.stop = T0 + 3 * HOUR
    bad.start = T0 + 5 * HOUR  # after its stop
    attached.flush_ranges()
    assert room.event(good.uuid).stop == T0 + 3 * HOUR
    assert (room.event(bad.uuid).start, room.event(bad.uuid).stop) == (T0, T0 + HOUR)
    assert (bad.start, bad.stop) == (T0, T0 + HOUR)  # shown as stored again
    assert len(told) == 1 and "before" in told[0]
