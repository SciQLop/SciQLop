"""Smart catalogues are read when first used, never when their project opens, and every read runs in
the background worker. What the GUI thread then does is bounded per turn of the Qt loop, and a
re-read touches only the members that changed: a project with a 100 000-event smart catalogue opens
and edits without freezing SciQLop."""
import threading

import pytest

from SciQLop.components.catalogs import CatalogEvent

from .conftest import HOUR, T0

RULE = {"filter": {"all": True}, "where": {"contains": ["tags", "s"]}}


class _Counted:
    """A cocat-rs catalogue that notes each bulk read and the thread it ran on."""

    def __init__(self, catalogue, reads):
        self._catalogue, self._reads = catalogue, reads

    def __getattr__(self, name):
        return getattr(self._catalogue, name)

    def event_arrays(self, **kw):
        self._reads.append((self._catalogue.uuid, threading.current_thread() is threading.main_thread()))
        return self._catalogue.event_arrays(**kw)


class _CountingRoom:
    def __init__(self, room, reads):
        self._room, self._reads = room, reads

    def catalogues(self):
        return [_Counted(c, self._reads) for c in self._room.catalogues()]

    def catalogue(self, uuid):
        return _Counted(self._room.catalogue(uuid), self._reads)

    def __getattr__(self, name):
        return getattr(self._room, name)


def _tagged(room, n, tag="s"):
    return [room.create_event(start=T0 + i * HOUR, stop=T0 + (i + 1) * HOUR, author="me", tags=[tag]) for i in range(n)]


@pytest.fixture
def opened(provider, room):
    """A project holding a smart catalogue of 5 tagged events, opened by the provider; its reads noted."""
    _tagged(room, 5)
    smart = room.create_catalogue(name="smart", author="me")
    smart.rule = RULE
    reads = []
    provider.attach_room("r", _CountingRoom(room, reads))
    catalog = next(c for c in provider.catalogs() if c.uuid == smart.uuid)
    return provider, catalog, reads


def _read_of(reads, catalog):
    return [on_gui for uuid, on_gui in reads if uuid == catalog.uuid]


def _wait_loaded(provider, catalog, qtbot):
    qtbot.waitUntil(lambda: not provider.is_loading(catalog), timeout=5000)


def test_opening_a_project_does_not_read_its_smart_catalogues(opened):
    provider, catalog, reads = opened
    assert _read_of(reads, catalog) == []
    assert catalog.uuid in provider._smart  # its icon, tooltip and rights are known all the same


def test_first_use_reads_it_in_the_background_and_says_when_it_is_done(opened, qtbot):
    provider, catalog, reads = opened
    with qtbot.waitSignal(provider.loading_finished, timeout=5000):
        assert provider.events(catalog) == []
        assert provider.is_loading(catalog)
    assert len(provider.events(catalog)) == 5
    assert _read_of(reads, catalog) == [False]  # once, off the GUI thread


def test_an_edit_does_not_read_a_smart_catalogue_nobody_used(opened, room, qtbot):
    provider, catalog, reads = opened
    plain = provider.create_catalog("plain", ["r"])
    provider.add_event(plain, CatalogEvent(uuid="e1", start=T0, stop=T0 + HOUR, meta={"tags": ["s"]}))
    qtbot.wait(400)  # past the re-read delay
    assert _read_of(reads, catalog) == []


def test_a_re_read_touches_only_the_members_that_changed(opened, room, qtbot, monkeypatch):
    provider, catalog, reads = opened
    provider.events(catalog)
    _wait_loaded(provider, catalog, qtbot)
    before = {e.uuid: e for e in provider.events(catalog)}
    followed = []
    real_follow = provider._follow_range
    monkeypatch.setattr(provider, "_follow_range", lambda c, e: (followed.append(e.uuid), real_follow(c, e)))

    plain = provider.create_catalog("plain", ["r"])
    provider.add_event(plain, CatalogEvent(uuid="new", start=T0 - HOUR, stop=T0, meta={"tags": ["s"]}))
    qtbot.waitUntil(lambda: len(provider.events(catalog)) == 6, timeout=5000)

    after = {e.uuid: e for e in provider.events(catalog)}
    assert all(after[uuid] is event for uuid, event in before.items())
    assert followed.count("new") == 2 and set(followed) == {"new"}  # the plain catalogue's, the smart one's
    assert [e.start for e in provider.events(catalog)] == sorted(e.start for e in after.values())


def test_a_removed_member_leaves_and_the_rest_stay(opened, room, qtbot):
    provider, catalog, reads = opened
    provider.events(catalog)
    _wait_loaded(provider, catalog, qtbot)
    gone, *kept = provider.events(catalog)
    plain = provider.create_catalog("plain", ["r"])
    provider.add_event(plain, CatalogEvent(uuid=gone.uuid, start=gone.start, stop=gone.stop))
    provider.set_event_meta(plain, provider.events(plain)[0], "tags", ["other"])
    qtbot.waitUntil(lambda: len(provider.events(catalog)) == 4, timeout=5000)
    assert provider.events(catalog) == kept


def test_a_big_read_is_shown_over_several_turns_of_the_qt_loop_and_said_once(provider, room, qtbot, monkeypatch):
    from SciQLop.plugins.sciqlop_cocat import rereading
    monkeypatch.setattr(rereading, "SLICE", 7)
    _tagged(room, 50)
    smart = room.create_catalogue(name="smart", author="me")
    smart.rule = RULE
    provider.attach_room("r", room)
    catalog = next(c for c in provider.catalogs() if c.uuid == smart.uuid)
    slices, said = [], []
    real_step = rereading._Applying.step
    monkeypatch.setattr(rereading._Applying, "step", lambda self: (slices.append(1), real_step(self))[1])
    provider.events_changed.connect(lambda c: said.append(c) if c is catalog else None)

    provider.events(catalog)
    _wait_loaded(provider, catalog, qtbot)

    assert len(provider.events(catalog)) == 50
    assert len(slices) >= 50 // 7 and len(said) == 1


def test_a_remote_rule_change_is_read_in_the_background(opened, room, qtbot):
    provider, catalog, reads = opened
    provider.events(catalog)
    _wait_loaded(provider, catalog, qtbot)
    reads.clear()
    room.catalogue(catalog.uuid).rule = {"filter": {"all": True}, "where": {"contains": ["tags", "none"]}}
    from SciQLop.plugins.sciqlop_cocat.remote import RoomListener
    RoomListener(provider, "r").catalogue_rule(catalog.uuid)  # as cocat-rs calls it
    qtbot.waitUntil(lambda: provider.events(catalog) == [], timeout=5000)
    assert _read_of(reads, catalog) and not any(_read_of(reads, catalog))
