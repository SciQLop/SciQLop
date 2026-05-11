from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from tscat_gui.tscat_driver.actions import Action


ORPHAN_CATALOG_UUID = "00000000-0000-0000-0000-orphan-tscat"
ORPHAN_CATALOG_NAME = "🗑 Orphan events"


def _orphan_uuids(all_events_by_uuid: dict, all_catalogues) -> set:
    """Compute the set of orphan event UUIDs from in-memory tscat data."""
    import tscat
    attached: set[str] = set()
    for cat in all_catalogues:
        cat_events, _ = tscat.get_events(cat)
        for ev in cat_events:
            attached.add(ev.uuid)
    return set(all_events_by_uuid.keys()) - attached


@dataclass
class GetOrphanEventsAction(Action):
    """Driver-thread action that finds tscat events with no catalogue membership.

    `action()` runs on the tscat-gui driver QThread, so direct
    `tscat.get_events()` / `tscat.get_catalogues()` calls here are safe.
    Calling those from the main thread is NOT safe — they share the
    SQLAlchemy session with the driver and racing them silently corrupts
    state (see `pitfall-catalogs-hot-path-tscat-query.md`).
    """

    events: List = field(default_factory=list)

    def action(self) -> None:
        import tscat
        from tscat.base import backend as _tscat_backend
        # tscat's sessionmaker uses autoflush=False, so events newly linked
        # to a catalogue via catalogue.events.extend(...) (issued by
        # AddEventsToCatalogueAction) are only in Python memory until
        # tscat.save() commits. Flush first so our SELECTs see those
        # pending links — otherwise just-imported events appear as orphans
        # until the user saves.
        _tscat_backend().session.flush()
        all_events = {e.uuid: e for e in tscat.get_events()}
        orphan_uuids = _orphan_uuids(all_events, tscat.get_catalogues())
        self.events = [all_events[u] for u in orphan_uuids]


@dataclass
class BulkDeleteOrphanEventsAction(Action):
    """Permanently delete orphan tscat events on the driver thread.

    If ``uuids`` is None, every current orphan is deleted; otherwise only the
    intersection of ``uuids`` with the current orphan set is touched (events
    that have meanwhile been adopted by some catalogue are skipped).

    Uses a single SQLAlchemy bulk-delete query (chunked to stay under
    SQLite's IN-clause parameter limit) instead of iterating
    ``entity.remove(permanently=True)``. The per-entity path calls
    ``session.flush()`` for every event (see
    ``tscat.orm_sqlalchemy.Backend.remove``) which scales to one SQLite
    round-trip per orphan; on a database with 50k+ orphans that took
    minutes. The bulk path runs in seconds.
    """

    uuids: Optional[List[str]] = None
    deleted_count: int = 0

    # SQLite's default expression-tree depth tolerates ~999 IN-clause params
    # on older builds and 32 766 on 3.32+. 5 000 is comfortably under both.
    _DELETE_CHUNK_SIZE = 5000

    def action(self) -> None:
        import tscat
        from tscat.base import backend as _tscat_backend
        from tscat.orm_sqlalchemy import orm as _orm

        session = _tscat_backend().session
        # Mirror TscatCatalogProvider._ensure_clean_session: a previous
        # failed flush could have left the transaction in a bad state, and
        # our commit() below would otherwise persist whatever stale work
        # was staged before this action ran.
        if not session.is_active:
            session.rollback()

        all_events = {e.uuid: e for e in tscat.get_events()}
        orphan_set = _orphan_uuids(all_events, tscat.get_catalogues())
        target = orphan_set if self.uuids is None else (orphan_set & set(self.uuids))
        if not target:
            return

        target_list = list(target)
        chunk = self._DELETE_CHUNK_SIZE
        for start in range(0, len(target_list), chunk):
            session.query(_orm.Event).filter(
                _orm.Event.uuid.in_(target_list[start:start + chunk])
            ).delete(synchronize_session=False)
        session.commit()
        # Drop now-stale ORM identities so subsequent `tscat.get_events()`
        # calls return only the survivors and any wrapper held by user code
        # auto-reloads from DB on next attribute access.
        session.expire_all()
        self.deleted_count = len(target_list)
