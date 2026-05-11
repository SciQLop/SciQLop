"""Tests for the tscat orphan-events virtual catalog and cleanup dialog.

All tscat reads and writes go through the driver (``tscat_model.do(...)``);
direct ``tscat.*`` calls from the main thread are unsafe because they race
the driver's SQLAlchemy session.
"""
import time
import uuid as _uuid
from datetime import datetime, timezone

# Mirror of SciQLop.plugins.tscat_catalogs.orphans.ORPHAN_CATALOG_UUID —
# inlined because importing the SciQLop tscat plugin package at test
# collection time pulls Qt globals before QApplication exists.
ORPHAN_CATALOG_UUID = "00000000-0000-0000-0000-orphan-tscat"


def _process(qapp, rounds=20):
    for _ in range(rounds):
        qapp.processEvents()
        time.sleep(0.05)


def _dispatch_and_wait(qapp, action, rounds=30):
    """Dispatch a tscat-gui action and process events until it completes."""
    from tscat_gui.tscat_driver.model import tscat_model
    tscat_model.do(action)
    for _ in range(rounds):
        qapp.processEvents()
        if action.completed:
            return
        time.sleep(0.05)


def _create_orphan_event(qapp, author: str):
    """Create an orphan event via the driver, return the resulting _Event."""
    import tscat
    from tscat_gui.tscat_driver.actions import CreateEntityAction
    args = dict(
        start=datetime(2020, 1, 1, tzinfo=timezone.utc),
        stop=datetime(2020, 1, 1, 1, tzinfo=timezone.utc),
        author=author,
        uuid=str(_uuid.uuid4()),
    )
    action = CreateEntityAction(user_callback=None, cls=tscat._Event, args=args)
    _dispatch_and_wait(qapp, action)
    return action.entity


def _create_catalogue(qapp, name: str):
    import tscat
    from tscat_gui.tscat_driver.actions import CreateEntityAction
    args = dict(name=name, author="t", uuid=str(_uuid.uuid4()))
    action = CreateEntityAction(user_callback=None, cls=tscat._Catalogue, args=args)
    _dispatch_and_wait(qapp, action)
    return action.entity


def _attach_event(qapp, catalogue, event):
    from tscat_gui.tscat_driver.actions import AddEventsToCatalogueAction
    action = AddEventsToCatalogueAction(
        user_callback=None,
        uuids=[event.uuid],
        catalogue_uuid=catalogue.uuid,
    )
    _dispatch_and_wait(qapp, action)


def _query_orphans(qapp):
    from SciQLop.plugins.tscat_catalogs.orphans import GetOrphanEventsAction
    action = GetOrphanEventsAction(user_callback=None)
    _dispatch_and_wait(qapp, action)
    return action.events


def test_action_finds_event_with_no_catalogue(qapp):
    baseline = {e.uuid for e in _query_orphans(qapp)}

    orphan = _create_orphan_event(qapp, "orphan-action-1")
    cat = _create_catalogue(qapp, "host-1")
    attached = _create_orphan_event(qapp, "attached-action-1")
    _attach_event(qapp, cat, attached)

    found = {e.uuid for e in _query_orphans(qapp)} - baseline
    assert orphan.uuid in found
    assert attached.uuid not in found


def test_action_excludes_events_assigned_to_any_catalogue(qapp):
    baseline = {e.uuid for e in _query_orphans(qapp)}

    cat = _create_catalogue(qapp, "all-attached")
    ev = _create_orphan_event(qapp, "all-mine")
    _attach_event(qapp, cat, ev)

    found = {e.uuid for e in _query_orphans(qapp)} - baseline
    assert ev.uuid not in found


def test_provider_publishes_virtual_orphan_catalog_when_orphans_exist(qapp):
    from SciQLop.plugins.tscat_catalogs.tscat_provider import TscatCatalogProvider

    _create_orphan_event(qapp, "provider-orph-1")

    provider = TscatCatalogProvider()
    _process(qapp)
    catalog_uuids = {c.uuid for c in provider.catalogs()}
    assert ORPHAN_CATALOG_UUID in catalog_uuids


def test_orphan_catalog_capabilities_are_delete_only(qapp):
    from SciQLop.plugins.tscat_catalogs.tscat_provider import TscatCatalogProvider
    from SciQLop.components.catalogs.backend.provider import Capability

    _create_orphan_event(qapp, "provider-orph-caps")

    provider = TscatCatalogProvider()
    _process(qapp)
    orph_cat = next(c for c in provider.catalogs() if c.uuid == ORPHAN_CATALOG_UUID)

    caps = provider.capabilities(orph_cat)
    assert Capability.DELETE_EVENTS in caps
    assert Capability.RENAME_CATALOG not in caps
    assert Capability.EDIT_EVENTS not in caps
    assert Capability.CREATE_EVENTS not in caps


def test_provider_events_for_orphan_catalog_returns_cached_orphans(qapp):
    from SciQLop.plugins.tscat_catalogs.tscat_provider import TscatCatalogProvider

    e = _create_orphan_event(qapp, "provider-orph-events")

    provider = TscatCatalogProvider()
    _process(qapp)
    orph_cat = next(c for c in provider.catalogs() if c.uuid == ORPHAN_CATALOG_UUID)
    listed = provider.events(orph_cat)
    listed_uuids = {ev.uuid for ev in listed}
    assert e.uuid in listed_uuids


def test_orphan_node_appears_when_first_orphan_is_created(qapp):
    """Provider listens for tscat-driver actions and refreshes the virtual node live."""
    from SciQLop.plugins.tscat_catalogs.tscat_provider import TscatCatalogProvider

    # Drain pre-existing orphans by attaching them to a sink catalogue
    sink = _create_catalogue(qapp, "orphan-sink-appear")
    pre_orphans = _query_orphans(qapp)
    for ev in pre_orphans:
        _attach_event(qapp, sink, ev)

    provider = TscatCatalogProvider()
    _process(qapp)
    assert not any(c.uuid == ORPHAN_CATALOG_UUID for c in provider.catalogs())

    added: list[str] = []
    provider.catalog_added.connect(lambda c: added.append(c.uuid))

    _create_orphan_event(qapp, "trigger-orph-appear")
    _process(qapp)

    assert ORPHAN_CATALOG_UUID in added
    assert any(c.uuid == ORPHAN_CATALOG_UUID for c in provider.catalogs())


def test_orphan_node_disappears_when_last_orphan_is_attached(qapp):
    from SciQLop.plugins.tscat_catalogs.tscat_provider import TscatCatalogProvider

    cat = _create_catalogue(qapp, "adopt")
    e = _create_orphan_event(qapp, "orph-adopt")

    provider = TscatCatalogProvider()
    _process(qapp)
    assert any(c.uuid == ORPHAN_CATALOG_UUID for c in provider.catalogs())

    # Attach all current orphans to the catalogue
    pending = _query_orphans(qapp)
    for ev in pending:
        _attach_event(qapp, cat, ev)
    _process(qapp)

    assert not any(c.uuid == ORPHAN_CATALOG_UUID for c in provider.catalogs())


def test_bulk_delete_action_removes_targeted_orphans(qapp):
    from SciQLop.plugins.tscat_catalogs.orphans import BulkDeleteOrphanEventsAction

    e1 = _create_orphan_event(qapp, "bulk-del-1")
    e2 = _create_orphan_event(qapp, "bulk-del-2")
    before = {ev.uuid for ev in _query_orphans(qapp)}
    assert {e1.uuid, e2.uuid} <= before

    action = BulkDeleteOrphanEventsAction(user_callback=None, uuids=[e1.uuid])
    _dispatch_and_wait(qapp, action)
    assert action.deleted_count == 1

    after = {ev.uuid for ev in _query_orphans(qapp)}
    assert e1.uuid not in after
    assert e2.uuid in after


def test_bulk_delete_action_with_uuids_none_clears_all_orphans(qapp):
    from SciQLop.plugins.tscat_catalogs.orphans import BulkDeleteOrphanEventsAction

    _create_orphan_event(qapp, "bulk-all-1")
    _create_orphan_event(qapp, "bulk-all-2")
    pre = _query_orphans(qapp)
    assert len(pre) >= 2

    action = BulkDeleteOrphanEventsAction(user_callback=None, uuids=None)
    _dispatch_and_wait(qapp, action)

    post = _query_orphans(qapp)
    assert len(post) == 0
    assert action.deleted_count >= len(pre)


def test_cleanup_dialog_lists_orphans_and_deletes_selected(qapp):
    from SciQLop.plugins.tscat_catalogs.orphan_cleanup_dialog import OrphanCleanupDialog
    from SciQLop.plugins.tscat_catalogs.tscat_provider import TscatCatalogProvider

    e1 = _create_orphan_event(qapp, "cleanup1")
    e2 = _create_orphan_event(qapp, "cleanup2")

    provider = TscatCatalogProvider()
    _process(qapp)

    dialog = OrphanCleanupDialog(provider=provider)
    listed = {row[0] for row in dialog.orphan_rows()}
    assert e1.uuid in listed
    assert e2.uuid in listed

    dialog.delete_uuids([e1.uuid])
    _process(qapp)

    remaining = {ev.uuid for ev in _query_orphans(qapp)}
    assert e1.uuid not in remaining
    assert e2.uuid in remaining
