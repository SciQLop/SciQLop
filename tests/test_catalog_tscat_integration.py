"""Integration tests for CatalogService with the real tscat provider.

These tests exercise create/get/add_events/remove_events/save through
the user-facing CatalogService, backed by the live TscatCatalogProvider.
"""

import time

import pytest


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
    from tscat_gui.tscat_driver.model import tscat_model
    tscat_model.tscat_root()
    from SciQLop.plugins.tscat_catalogs.tscat_provider import TscatCatalogProvider
    provider = TscatCatalogProvider()
    yield provider


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
