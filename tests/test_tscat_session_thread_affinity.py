"""Reproducers for the tscat "session is in 'prepared' state" corruption.

The tscat-gui driver serializes all DB work on its worker QThread, against
tscat's single global SQLAlchemy session. TscatCatalogProvider used to
commit (``tscat.save()``) and rollback (``_ensure_clean_session``) that
session directly on the main thread; a main-thread commit racing driver
actions leaves the session transaction stuck in SQLAlchemy's PREPARED
state, after which every catalog action fails with InvalidRequestError.
These tests pin every session touch to the driver thread.
"""

import threading
import time

import pytest


PROVIDER = "My Catalogs"


def _spin(qapp, predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents()
        if predicate():
            return True
        time.sleep(0.02)
    return predicate()


def _session():
    from tscat.base import backend
    return backend().session


@pytest.fixture(scope="module")
def tscat_provider(qapp):
    from tscat_gui.tscat_driver.model import tscat_model
    tscat_model.tscat_root()
    _spin(qapp, lambda: False, timeout=0.5)
    from SciQLop.components.catalogs.backend.registry import CatalogRegistry
    registry = CatalogRegistry.instance()
    existing = next((p for p in registry.providers() if p.name == PROVIDER), None)
    if existing is not None:
        yield existing
        return
    from SciQLop.plugins.tscat_catalogs.tscat_provider import TscatCatalogProvider
    provider = TscatCatalogProvider()
    yield provider
    registry.unregister(provider)


def test_save_commits_on_driver_thread(tscat_provider, qapp, monkeypatch):
    session = _session()
    commit_threads: list[int] = []
    real_commit = session.commit

    def recording_commit():
        commit_threads.append(threading.get_ident())
        real_commit()

    monkeypatch.setattr(session, "commit", recording_commit)
    tscat_provider.save()
    assert _spin(qapp, lambda: commit_threads), "save() never reached session.commit()"
    assert threading.get_ident() not in commit_threads, (
        "tscat session.commit() ran on the main thread; it must run on the "
        "tscat-gui driver thread or it races in-flight driver actions and "
        "leaves the session stuck in the 'prepared' state"
    )


def test_tests_use_their_own_tscat_database():
    """appdirs ignores XDG_DATA_HOME on macOS, so tests wrote the developer's
    real tscat database and shared it across processes."""
    assert "sciqlop_test_" in str(_session().get_bind().url)


def _committed_event_uuids(qapp, catalogue_uuid: str) -> list[str]:
    """Drop everything uncommitted, then list the catalogue's events, on the
    driver thread like every other session touch."""
    from dataclasses import dataclass, field
    from tscat_gui.tscat_driver.actions import Action
    from tscat_gui.tscat_driver.model import tscat_model

    @dataclass
    class _ReadCommitted(Action):
        uuids: list = field(default_factory=list)

        def action(self) -> None:
            import tscat
            tscat.discard()
            catalogue = next(c for c in tscat.get_catalogues() if c.uuid == catalogue_uuid)
            self.uuids = [e.uuid for e in tscat.get_events(catalogue)[0]]
            # Reading opened a transaction; an open one keeps a lock on the
            # sqlite file, and another process's BEGIN EXCLUSIVE then fails
            # with "database is locked".
            tscat.discard()

    probe = _ReadCommitted(user_callback=None)
    tscat_model.do(probe)
    assert _spin(qapp, lambda: probe.completed, timeout=10), "probe action never ran"
    return probe.uuids


def test_save_right_after_adding_an_event_commits_its_catalogue_link(tscat_provider, qapp, monkeypatch):
    """add_event links the new event to its catalogue from the create action's
    callback, so that link is queued only after the create has run. A save
    requested right after add_event was queued before the link: the commit
    held an orphan event, and the catalogue came back empty after a restart."""
    import uuid
    from datetime import datetime, timezone
    from SciQLop.components.catalogs.backend.provider import CatalogEvent

    session = _session()
    commits = []
    real_commit = session.commit
    monkeypatch.setattr(session, "commit", lambda: (commits.append(1), real_commit()))

    catalog = tscat_provider.create_catalog(f"save-race-{uuid.uuid4().hex[:8]}")
    event = CatalogEvent(uuid=str(uuid.uuid4()),
                         start=datetime(2025, 10, 10, 8, tzinfo=timezone.utc),
                         stop=datetime(2025, 10, 10, 9, tzinfo=timezone.utc))
    tscat_provider.add_event(catalog, event)
    tscat_provider.save()

    assert _spin(qapp, lambda: commits and tscat_provider._pending_actions == 0, timeout=10)
    assert _committed_event_uuids(qapp, catalog.uuid) == [event.uuid]
    assert not session.in_transaction(), "the probe left a transaction open, locking the sqlite file"


def test_failed_flush_recovery_rolls_back_on_driver_thread(tscat_provider, qapp, monkeypatch):
    from sqlalchemy.orm import Session

    session = _session()
    rollback_threads: list[int] = []
    real_rollback = session.rollback

    def recording_rollback():
        rollback_threads.append(threading.get_ident())
        real_rollback()

    monkeypatch.setattr(session, "rollback", recording_rollback)
    # Simulate the dead transaction a failed flush leaves behind, so the
    # provider's recovery path actually issues a rollback.
    monkeypatch.setattr(Session, "is_active", False)
    tscat_provider.save()
    assert _spin(qapp, lambda: rollback_threads), "recovery rollback never ran"
    assert threading.get_ident() not in rollback_threads, (
        "tscat session.rollback() ran on the main thread; recovery must be "
        "routed through the driver thread like every other session touch"
    )
