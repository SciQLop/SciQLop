"""Integration tests for CatalogService with the real tscat provider.

These tests exercise create/get/add_events/remove_events/save through
the user-facing CatalogService, backed by the live TscatCatalogProvider.
"""

import time
import uuid as _uuid
from datetime import datetime, timezone

import pytest

from SciQLop.components.catalogs.backend.provider import CatalogEvent


PROVIDER = "My Catalogs"


def _path(name: str) -> str:
    return f"{PROVIDER}//{name}"


def _process_events(qapp, rounds=15):
    """Process events to let tscat's async QThread actions complete."""
    for _ in range(rounds):
        qapp.processEvents()
        time.sleep(0.05)
    qapp.processEvents()


@pytest.fixture(scope="module")
def tscat_provider(qapp):
    # tscat backend is pre-initialized in conftest.py to dodge a thread race
    # between the driver QThread and any test thread.
    from tscat_gui.tscat_driver.model import tscat_model
    tscat_model.tscat_root()
    _process_events(qapp)
    from SciQLop.plugins.tscat_catalogs.tscat_provider import TscatCatalogProvider
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    provider = TscatCatalogProvider()
    yield provider
    CatalogRegistry.instance().unregister(provider)


@pytest.fixture
def catalogs(tscat_provider):
    from SciQLop.user_api.catalogs._service import CatalogService
    return CatalogService()


class TestCatalogTscatIntegration:
    def test_create_then_get_returns_events(self, catalogs):
        catalogs.create(_path("t_create"), [
            ("2020-01-01", "2020-01-02"),
            ("2020-06-01", "2020-06-15"),
        ])
        result = catalogs.get(_path("t_create"))
        assert len(result) == 2

    def test_get_after_event_loop_processing(self, catalogs, qapp):
        """Events survive async action_done callbacks."""
        catalogs.create(_path("t_async_get"), [("2020-01-01", "2020-01-02")])
        _process_events(qapp)
        result = catalogs.get(_path("t_async_get"))
        assert len(result) == 1

    def test_add_events_appends(self, catalogs):
        catalogs.create(_path("t_add"), [("2020-01-01", "2020-01-02")])
        catalogs.add_events(_path("t_add"), [("2020-06-01", "2020-06-15")])
        result = catalogs.get(_path("t_add"))
        assert len(result) == 2

    def test_add_events_after_event_loop(self, catalogs, qapp):
        """Simulates notebook: create in cell 1, add_events in cell 2."""
        catalogs.create(_path("t_add_async"), [("2020-01-01", "2020-01-02")])
        _process_events(qapp)
        catalogs.add_events(_path("t_add_async"), [("2020-06-01", "2020-06-15")])
        result = catalogs.get(_path("t_add_async"))
        assert len(result) == 2

    def test_remove_events(self, catalogs):
        catalogs.create(_path("t_rm"), [
            ("2020-01-01", "2020-01-02"),
            ("2020-06-01", "2020-06-15"),
        ])
        cat = catalogs.get(_path("t_rm"))
        catalogs.remove_events(_path("t_rm"), [cat[0]])
        result = catalogs.get(_path("t_rm"))
        assert len(result) == 1

    def test_remove_events_after_event_loop(self, catalogs, qapp):
        catalogs.create(_path("t_rm_async"), [
            ("2020-01-01", "2020-01-02"),
            ("2020-06-01", "2020-06-15"),
        ])
        _process_events(qapp)
        cat = catalogs.get(_path("t_rm_async"))
        catalogs.remove_events(_path("t_rm_async"), [cat[0]])
        result = catalogs.get(_path("t_rm_async"))
        assert len(result) == 1

    def test_save_creates_catalog(self, catalogs):
        catalogs.save(_path("t_save"), [("2020-03-01", "2020-03-10")])
        result = catalogs.get(_path("t_save"))
        assert len(result) == 1

    def test_save_overwrites(self, catalogs):
        catalogs.create(_path("t_overwrite"), [("2020-01-01", "2020-01-02")])
        catalogs.save(_path("t_overwrite"), [
            ("2021-01-01", "2021-01-02"),
            ("2021-06-01", "2021-06-15"),
            ("2021-12-01", "2021-12-31"),
        ])
        result = catalogs.get(_path("t_overwrite"))
        assert len(result) == 3

    def test_save_after_event_loop(self, catalogs, qapp):
        catalogs.create(_path("t_save_async"), [("2020-01-01", "2020-01-02")])
        _process_events(qapp)
        catalogs.save(_path("t_save_async"), [
            ("2021-01-01", "2021-01-02"),
            ("2021-06-01", "2021-06-15"),
        ])
        result = catalogs.get(_path("t_save_async"))
        assert len(result) == 2

    def test_list_includes_created(self, catalogs):
        catalogs.create(_path("t_list"), [("2020-01-01", "2020-01-02")])
        assert _path("t_list") in catalogs.list(PROVIDER)

    def test_remove_catalog(self, catalogs):
        catalogs.create(_path("t_del"), [("2020-01-01", "2020-01-02")])
        catalogs.remove(_path("t_del"))
        assert _path("t_del") not in catalogs.list(PROVIDER)

    def test_remove_catalog_after_event_loop(self, catalogs, qapp, tscat_provider):
        """Remove after cache rebuild — catalog_removed must still reach the UI."""
        catalogs.create(_path("t_del_async"), [("2020-01-01", "2020-01-02")])
        _process_events(qapp)

        removed = []
        tscat_provider.catalog_removed.connect(lambda cat: removed.append(cat.uuid))
        catalogs.remove(_path("t_del_async"))

        assert len(removed) == 1
        assert _path("t_del_async") not in catalogs.list(PROVIDER)

    def test_create_duplicate_raises(self, catalogs):
        catalogs.create(_path("t_dup"), [("2020-01-01", "2020-01-02")])
        with pytest.raises(ValueError, match="already exists"):
            catalogs.create(_path("t_dup"), [("2020-06-01", "2020-06-15")])

    def test_roundtrip_uuids(self, catalogs):
        catalogs.create(_path("t_uuid"), [("2020-01-01", "2020-01-02")])
        uuid1 = catalogs.get(_path("t_uuid"))[0].meta["__sciqlop_uuid__"]
        uuid2 = catalogs.get(_path("t_uuid"))[0].meta["__sciqlop_uuid__"]
        assert uuid1 == uuid2


class TestTrackedActionExceptionSafety:
    def test_pending_actions_decremented_on_failure(self, tscat_provider):
        """_tracked_action must decrement _pending_actions if the body raises."""
        before = tscat_provider._pending_actions
        with pytest.raises(RuntimeError):
            with tscat_provider._tracked_action():
                raise RuntimeError("simulated failure")
        assert tscat_provider._pending_actions == before


def test_add_event_persists_meta_to_tscat_backend(qapp, tscat_provider):
    """Regression: when an event is added with arbitrary metadata (the case
    of a drag-and-drop import from speasy), every meta key must reach the
    tscat backend, not just live in the in-memory mirror. Before the fix
    the imported columns disappeared on the next SciQLop restart because
    tscat.add_event ignored event.meta. We verify by inspecting the tscat
    entity directly via _extract_meta — that's the same path the provider
    uses on cold reload."""
    from SciQLop.plugins.tscat_catalogs.tscat_provider import _extract_meta
    from tscat_gui.tscat_driver.model import tscat_model
    from tscat_gui.model_base.constants import EntityRole

    cat = tscat_provider.create_catalog("t_meta_persist")
    _process_events(qapp)
    ev = CatalogEvent(
        uuid=str(_uuid.uuid4()),
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
        meta={
            "tags": ["imported", "speasy"],
            "rating": 3,
            "custom_column": "custom_value",
            "another": 42,
        },
    )
    tscat_provider.add_event(cat, ev)
    _process_events(qapp, rounds=30)

    # Reading via provider.events triggers the GetCatalogueAction load that
    # populates the catalog model from the orm. We then introspect the
    # underlying tscat entity to confirm meta survived the persist path.
    tscat_provider._events.pop(cat.uuid, None)
    tscat_provider.events(cat)
    _process_events(qapp, rounds=30)
    catalog_model = tscat_model.catalog(cat.uuid)
    assert catalog_model.rowCount() == 1
    entity = catalog_model.index(0, 0).data(EntityRole)
    persisted = _extract_meta(entity)

    assert persisted.get("custom_column") == "custom_value"
    assert persisted.get("another") == 42
    assert persisted.get("rating") == 3
    assert "imported" in persisted.get("tags", [])


def test_set_event_meta_updates_local_mirror(qapp, tscat_provider):
    """provider.set_event_meta must update event.meta synchronously and persist via tscat."""
    cat = tscat_provider.create_catalog("t_meta_edit")
    _process_events(qapp)
    ev = CatalogEvent(
        uuid=str(_uuid.uuid4()),
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
        meta={},
    )
    tscat_provider.add_event(cat, ev)
    _process_events(qapp)

    received = []
    tscat_provider.event_meta_changed.connect(lambda c, e, k: received.append(k))

    tscat_provider.set_event_meta(cat, ev, "rating", 4)
    _process_events(qapp)

    assert ev.meta["rating"] == 4
    assert received == ["rating"]
    assert tscat_provider.is_dirty(cat)


def test_set_events_meta_bulk_uses_single_tscat_action(qapp, tscat_provider, monkeypatch):
    """The bulk override should issue ONE SetAttributeAction with N uuids."""
    from tscat_gui.tscat_driver import actions as tscat_actions

    cat = tscat_provider.create_catalog("t_meta_bulk")
    _process_events(qapp)
    events = []
    for _ in range(3):
        e = CatalogEvent(
            uuid=str(_uuid.uuid4()),
            start=datetime(2020, 1, 1, tzinfo=timezone.utc),
            stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
            meta={},
        )
        tscat_provider.add_event(cat, e)
        events.append(e)
    _process_events(qapp)

    captured: list = []
    real_init = tscat_actions.SetAttributeAction.__init__

    def spy_init(self, *args, **kwargs):
        captured.append(kwargs)
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(tscat_actions.SetAttributeAction, "__init__", spy_init)

    tscat_provider.set_events_meta(cat, events, "tags", ["x"])
    _process_events(qapp)

    set_attr_calls = [c for c in captured if c.get("name") == "tags"]
    assert len(set_attr_calls) == 1
    assert len(set_attr_calls[0]["uuids"]) == 3
    for e in events:
        assert e.meta["tags"] == ["x"]


def test_set_event_meta_distinguishes_absent_from_none(qapp, tscat_provider):
    """Setting a key to None when the key is absent must emit (sentinel-based)."""
    cat = tscat_provider.create_catalog("t_meta_none")
    _process_events(qapp)
    ev = CatalogEvent(
        uuid=str(_uuid.uuid4()),
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
        meta={},
    )
    tscat_provider.add_event(cat, ev)
    _process_events(qapp)

    received = []
    tscat_provider.event_meta_changed.connect(lambda c, e, k: received.append(k))

    tscat_provider.set_event_meta(cat, ev, "note", None)

    assert "note" in ev.meta
    assert ev.meta["note"] is None
    assert received == ["note"]
