"""A request queued for the tscat database thread must not keep the QObject that sent it alive.

That thread can be the last to drop a request. If the request's callback held the sender, the sender was
destroyed there, Qt could not stop its timers from that thread, and a timer later fired on freed memory.
"""
import gc
import weakref
from datetime import datetime, timezone

import pytest


@pytest.fixture
def queued_requests(qapp, monkeypatch):
    from tscat_gui.tscat_driver.model import tscat_model
    requests = []
    monkeypatch.setattr(tscat_model, "do", requests.append)
    return requests


def _unregistered_provider():
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    from SciQLop.plugins.tscat_catalogs.tscat_provider import TscatCatalogProvider
    provider = TscatCatalogProvider()
    CatalogRegistry.instance().unregister(provider)
    return provider


def _is_gone_once_dropped(ref):
    gc.collect()
    return ref() is None


def test_the_orphan_query_does_not_keep_the_provider_alive(queued_requests):
    provider = _unregistered_provider()
    provider._do_dispatch_orphan_refresh()
    ref = weakref.ref(provider)

    del provider

    assert queued_requests and _is_gone_once_dropped(ref)


def test_adding_an_event_does_not_keep_the_provider_alive(queued_requests):
    from SciQLop.components.catalogs import Catalog, CatalogEvent
    provider = _unregistered_provider()
    event = CatalogEvent(uuid="e", start=datetime(2020, 1, 1, tzinfo=timezone.utc),
                         stop=datetime(2020, 1, 2, tzinfo=timezone.utc))
    provider.add_event(Catalog(uuid="c", name="c"), event)
    ref = weakref.ref(provider)

    del provider

    assert queued_requests and _is_gone_once_dropped(ref)


def test_deleting_orphans_does_not_keep_the_dialog_alive(queued_requests):
    from PySide6.QtWidgets import QApplication
    from SciQLop.plugins.tscat_catalogs.orphan_cleanup_dialog import OrphanCleanupDialog
    provider = _unregistered_provider()
    dialog = OrphanCleanupDialog(provider=provider)
    dialog.delete_uuids(None)
    QApplication.restoreOverrideCursor()
    ref = weakref.ref(dialog)

    del dialog

    assert queued_requests and _is_gone_once_dropped(ref)


def test_a_request_answered_after_its_sender_is_gone_is_ignored(queued_requests):
    provider = _unregistered_provider()
    provider._do_dispatch_orphan_refresh()
    query = queued_requests[-1]
    del provider
    gc.collect()

    query.user_callback(query)
