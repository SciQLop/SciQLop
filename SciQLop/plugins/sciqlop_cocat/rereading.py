"""Smart catalogues and links are read in one background worker, so neither opening nor editing a
big project freezes SciQLop. A smart catalogue is not read when its project opens, only when it is
first used (its events are asked for); its icon, tooltip and rights need only its rule.

The worker reads (cocat-rs 0.10.2 evaluates a rule without the GIL) and compares the read with the
last one shown, using whole-array comparisons: an unchanged catalogue costs no Python work per
event. A changed one sends only what changed: the ids gone, and rows for what is new or different.
The Qt thread, where _wrappers and every Qt object live, then applies the change SLICE events per
turn of the Qt loop, and says once at the end. One read is in flight at a time; what is asked
meanwhile waits for it."""
from __future__ import annotations

import bisect
from dataclasses import dataclass, field

import numpy as np
from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal

from SciQLop.components.catalogs import Catalog

from .convert import _derived_id, _utc, rows_of

SLICE = 2000  # events made, placed or dropped per turn of the Qt loop: about 15 ms


@dataclass(frozen=True)
class Snapshot:
    """A read as cocat-rs gave it, and each member's id (a derived interval's own), in that order."""
    arrays: dict
    ids: list

    @classmethod
    def of(cls, arrays: dict) -> "Snapshot":
        return cls(arrays, _ids(arrays))

    def same_as(self, other: "Snapshot") -> bool:
        a, b = self.arrays, other.arrays
        return (self.ids == other.ids and np.array_equal(a["start"], b["start"])
                and np.array_equal(a["stop"], b["stop"])
                and all(a.get(k) == b.get(k) for k in ("attributes", "tags", "confidence", "sources")))

    def differing(self, other: "Snapshot") -> list[int]:
        """Positions of the members that are new, or not as `other` had them."""
        theirs = {member: i for i, member in enumerate(other.ids)}
        a, b = self.arrays, other.arrays
        fields = [k for k in ("attributes", "tags", "confidence") if k in a]
        return [i for i, member in enumerate(self.ids)
                if (j := theirs.get(member)) is None or a["start"][i] != b["start"][j]
                or a["stop"][i] != b["stop"][j] or any(a[k][i] != b[k][j] for k in fields)]


def _ids(arrays: dict) -> list:
    uuids, sources = arrays["uuid"], arrays.get("sources")
    if None not in uuids:
        return list(uuids)
    starts = _utc(arrays["start"])
    return [uuid if uuid is not None else _derived_id(starts[i], sources[i] if sources else None)
            for i, uuid in enumerate(uuids)]


def _subset(arrays: dict, positions: list[int]) -> dict:
    """The arrays of the given members only, as cocat-rs would have read them. A value for the whole read
    (cocat-rs 0.12.3's "capped") is kept as it is."""
    picked = np.asarray(positions, dtype=int)

    def members(values):
        if isinstance(values, np.ndarray):
            return values[picked]
        return [values[i] for i in positions] if isinstance(values, list) else values

    return {key: members(values) for key, values in arrays.items()}


@dataclass
class Change:
    """What a read brings, made in the worker. ``rows`` is every member (sorted by start) when there
    was nothing to compare with; else ``gone`` and ``rows`` say what changed."""
    snapshot: Snapshot | None = None
    rows: list = field(default_factory=list)
    gone: list = field(default_factory=list)
    whole: bool = False
    error: Exception | None = None

    @property
    def empty(self) -> bool:
        return self.error is None and not self.whole and not self.rows and not self.gone


def read_change(cocat_cat, previous: Snapshot | None) -> Change:
    """Safe on any thread: it touches nothing of SciQLop's."""
    try:
        arrays = cocat_cat.event_arrays(attributes=True)
        snapshot = Snapshot.of(arrays)
        if previous is None:
            return Change(snapshot, sorted(rows_of(arrays), key=lambda row: row.start), whole=True)
        if snapshot.same_as(previous):
            return Change(snapshot)
        kept = set(snapshot.ids)
        changed = snapshot.differing(previous)
        return Change(snapshot, rows_of(_subset(arrays, changed)) if changed else [],
                      gone=[member for member in previous.ids if member not in kept])
    except Exception as error:  # a rule this cocat-rs cannot use: the catalogue says so
        return Change(error=error)


class _Done(QObject):
    read = Signal(object)  # [(catalog, Change)], queued to the Qt thread


class _Read(QRunnable):
    def __init__(self, jobs, done: _Done):
        super().__init__()
        self._jobs, self._done = jobs, done

    def run(self):
        self._done.read.emit([(catalog, read_change(cocat_cat, previous))
                              for catalog, cocat_cat, previous in self._jobs])


class Rereading:
    """Mixed into the provider: its catalogues, rooms and timers are used as they are."""

    def _start_rereading(self) -> None:
        self._reread_queue: dict[str, Catalog] = {}  # uuid -> catalogue waiting for the worker
        self._reading = None                          # the catalogues being read, None when idle
        self._to_apply: list = []                     # results back from the worker, applied in slices
        self._applying = None                         # the slices of the result being applied
        self._snapshots: dict[str, Snapshot] = {}     # uuid -> the read its events show
        self._members: dict[str, dict] = {}           # uuid -> {member id: event}, as shown
        self._unread: set[str] = set()                # smart catalogues nobody has used yet
        self._first_reads: set[str] = set()           # those being read for the first time
        # A child timer, not QTimer.singleShot(0, self, ...): it stops and goes with the provider, where
        # posted one-shot calls outlived a test's provider and crashed in QObject::event.
        self._slice_timer = QTimer(self)
        self._slice_timer.setSingleShot(True)
        self._slice_timer.setInterval(0)
        self._slice_timer.timeout.connect(self._apply_slice)
        self._read_pool = QThreadPool(self)
        self._read_pool.setMaxThreadCount(1)
        self._read_done = _Done(self)
        self._read_done.read.connect(self._apply_reads)

    # ---- reading on first use ----

    def events(self, catalog: Catalog, start=None, stop=None):
        if catalog.uuid in self._unread:
            self._unread.discard(catalog.uuid)
            self._first_reads.add(catalog.uuid)
            self.loading_started.emit(catalog)
            self._queue_rereads([catalog])
        return super().events(catalog, start, stop)

    def is_loading(self, catalog: Catalog) -> bool:
        return catalog.uuid in self._first_reads or super().is_loading(catalog)

    def reread(self, catalog: Catalog) -> None:
        """Read again in the background, unless nobody has used it yet and it is still smart."""
        if catalog.uuid in self._unread:
            cocat_cat = self._cocat_catalogue(catalog)
            if cocat_cat is not None and cocat_cat.rule is not None:
                return
            self._unread.discard(catalog.uuid)
        self._queue_rereads([catalog])

    def _read_once_used(self, catalog: Catalog) -> bool:
        return catalog.uuid not in self._unread

    # ---- asking for reads ----

    def mark_smart_dirty(self, room_id: str) -> None:
        """Any event edit can change a smart catalogue's members; re-read the ones in use shortly."""
        if any(c.uuid in self._smart and self._read_once_used(c) for c in self._catalogs_of(room_id)) \
                or self._links_from(room_id):
            self._smart_dirty.add(room_id)
            self._smart_timer.start()

    def refresh_smart_catalogs(self) -> None:
        self._smart_timer.stop()
        dirty, self._smart_dirty = self._smart_dirty, set()
        for room_id in dirty:
            self._queue_rereads([c for c in self._catalogs_of(room_id)
                                 if c.uuid in self._smart and self._read_once_used(c)])
            self._queue_rereads(self._links_from(room_id))

    def _reread_public_smart(self) -> None:
        """cocat-rs keeps each search's answer a minute: a re-read here asks the server again,
        usually to hear that nothing changed."""
        self._queue_rereads([self._catalogs[u] for u in self._public_smart
                             if u in self._catalogs and u not in self._unread])

    def _queue_rereads(self, catalogs) -> None:
        for catalog in catalogs:
            self._reread_queue[catalog.uuid] = catalog
        self._start_next_read()

    def _start_next_read(self) -> None:
        if self._reading is not None or not self._reread_queue:
            return
        batch, self._reread_queue = list(self._reread_queue.values()), {}
        jobs = [job for job in map(self._read_job, batch) if job is not None]
        if jobs:
            self._reading = [catalog for catalog, _, _ in jobs]
            self._read_pool.start(_Read(jobs, self._read_done))

    def _read_job(self, catalog: Catalog):
        """(catalog, its cocat-rs catalogue, the read shown), its rule noted here on the Qt thread."""
        cocat_cat = self._cocat_catalogue(catalog)
        if cocat_cat is None:
            self._end_first_read(catalog)
            return None
        try:
            self._note_rule(catalog, cocat_cat)
        except Exception as error:
            self._show_rows(catalog, None, None, error)
            self._end_first_read(catalog)
            return None
        return catalog, cocat_cat, self._snapshots.get(catalog.uuid)

    # ---- applying reads, a slice per turn ----

    def _apply_reads(self, results) -> None:
        self._to_apply.extend(results)
        self._apply_next()

    def _apply_next(self) -> None:
        """The next result, sliced; the next read starts once all are shown."""
        while self._to_apply and self._applying is None:
            catalog, change = self._to_apply.pop(0)
            if self._catalogs.get(catalog.uuid) is not catalog:  # deleted, or its project left, meanwhile
                continue
            if change.error is not None:
                self._show_rows(catalog, None, None, change.error)
                self._end_first_read(catalog)
                continue
            self._unreadable.pop(catalog.uuid, None)
            self._note_sign_in(catalog)
            if change.empty:
                self._snapshots[catalog.uuid] = change.snapshot
                self._end_first_read(catalog)
                continue
            self._applying = _Applying(self, catalog, change)
            return self._slice_timer.start()
        if self._applying is None and not self._to_apply:
            self._reading = None
            self._start_next_read()

    def _apply_slice(self) -> None:
        applying = self._applying
        if applying is None:
            return
        if self._catalogs.get(applying.catalog.uuid) is not applying.catalog:
            self._applying = None
        elif applying.step():
            self._applying = None
            applying.finish()
            self._end_first_read(applying.catalog)
        if self._applying is not None:
            return self._slice_timer.start()
        self._apply_next()

    def _end_first_read(self, catalog: Catalog) -> None:
        if catalog.uuid in self._first_reads:
            self._first_reads.discard(catalog.uuid)
            self.loading_finished.emit(catalog)

    def _forget_reads_of(self, catalog_uuid: str) -> None:
        for kept in (self._snapshots, self._members):
            kept.pop(catalog_uuid, None)
        self._unread.discard(catalog_uuid)
        self._first_reads.discard(catalog_uuid)

    def _stop_rereading(self) -> None:
        """At close: the read in flight ends first; its result is then dropped with the catalogues."""
        self._reread_queue = {}
        self._slice_timer.stop()
        self._read_pool.waitForDone()
        self._to_apply = []
        self._applying = None


class _Applying:
    """One read being shown, SLICE events per step. A whole read builds a new list beside the shown
    one and swaps it in at the end; a change edits the shown list in place."""

    def __init__(self, provider, catalog: Catalog, change: Change):
        self.provider, self.catalog, self.change = provider, catalog, change
        self.room_id = provider._events_room_id(catalog)
        self.members = {} if change.whole else provider._members.setdefault(catalog.uuid, {})
        self.shown = provider._members.get(catalog.uuid, {})
        self.events = [] if change.whole else provider._events.setdefault(catalog.uuid, [])
        self.work = iter([*[("gone", m) for m in change.gone], *[("row", r) for r in change.rows],
                          *([("drop", e) for e in provider._events.get(catalog.uuid, [])] if change.whole else [])])

    def step(self) -> bool:
        """True once all is done."""
        provider = self.provider
        if not self.change.whole:
            provider._ensure_sorted(self.catalog.uuid)  # a member's range may have moved meanwhile
        for _ in range(SLICE):
            item = next(self.work, None)
            if item is None:
                return True
            kind, what = item
            if kind == "gone":
                self._drop(self.members.pop(what, None))
            elif kind == "row":
                self._place(what)
            elif self.members.get(what.uuid) is not what:  # whole read: an event no longer shown
                provider._unfollow_range(self.catalog.uuid, what)
        return False

    def _place(self, row) -> None:
        provider = self.provider
        if not self.change.whole:
            self._drop(self.members.pop(row.uuid, None))
        event = provider._row_event(self.room_id, row, self.shown)
        self.members[row.uuid] = event
        if self.change.whole:
            self.events.append(event)  # rows come sorted by start
        else:
            bisect.insort(self.events, event, key=lambda e: e.start)
        provider._follow_range(self.catalog, event)

    def _drop(self, event) -> None:
        if event is None:
            return
        events = self.events
        at = bisect.bisect_left(events, event.start, key=lambda e: e.start)
        while at < len(events) and events[at] is not event:
            at += 1
        if at < len(events):
            del events[at]
        self.provider._unfollow_range(self.catalog.uuid, event)

    def finish(self) -> None:
        provider, uuid = self.provider, self.catalog.uuid
        if self.change.whole:
            provider._events[uuid] = self.events
            provider._needs_sort.discard(uuid)
            provider._members[uuid] = self.members
        provider._snapshots[uuid] = self.change.snapshot
        provider._emit_events_changed(self.catalog)
