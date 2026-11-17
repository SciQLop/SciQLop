"""Smart catalogues and links are re-read in one background worker, so an edit in a big project
does not freeze SciQLop: cocat-rs 0.10.2 evaluates a rule without the GIL, and each read takes its
own transaction. The worker only reads; the rows become events on the Qt thread, where _wrappers
and every Qt object live. One read is in flight at a time; what is asked meanwhile waits for it."""
from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QThreadPool, QTimer, Signal

from SciQLop.components.catalogs import Catalog

from .convert import row_key, rows_of


def read_rows(cocat_cat):
    """(rows, their keys, None), or (None, None, the error): safe on any thread, it touches nothing
    of SciQLop's."""
    try:
        rows = rows_of(cocat_cat.event_arrays(attributes=True))
    except Exception as error:  # a rule this cocat-rs cannot read: the catalogue says so
        return None, None, error
    return rows, tuple(map(row_key, rows)), None


class _Done(QObject):
    read = Signal(object)  # [(catalog, rows, error)], queued to the Qt thread


class _Read(QRunnable):
    def __init__(self, jobs, done: _Done):
        super().__init__()
        self._jobs, self._done = jobs, done

    def run(self):
        self._done.read.emit([(catalog, *read_rows(cocat_cat)) for catalog, cocat_cat in self._jobs])


class Rereading:
    """Mixed into the provider: its catalogues, rooms and timers are used as they are."""

    def _start_rereading(self) -> None:
        self._reread_queue: dict[str, Catalog] = {}  # uuid -> catalogue waiting for the worker
        self._reading = None                          # the catalogues being read, None when idle
        self._to_apply: list = []                     # results back from the worker, one per Qt turn
        self._read_pool = QThreadPool(self)
        self._read_pool.setMaxThreadCount(1)
        self._read_done = _Done(self)
        self._read_done.read.connect(self._apply_reads)

    def mark_smart_dirty(self, room_id: str) -> None:
        """Any event edit can change a smart catalogue's members; re-read them shortly."""
        if any(c.uuid in self._smart for c in self._catalogs_of(room_id)) or self._links_from(room_id):
            self._smart_dirty.add(room_id)
            self._smart_timer.start()

    def refresh_smart_catalogs(self) -> None:
        self._smart_timer.stop()
        dirty, self._smart_dirty = self._smart_dirty, set()
        for room_id in dirty:
            self._queue_rereads([c for c in self._catalogs_of(room_id) if c.uuid in self._smart])
            self._queue_rereads(self._links_from(room_id))

    def _reread_public_smart(self) -> None:
        """cocat-rs keeps each search's answer a minute: a re-read here asks the server again,
        usually to hear that nothing changed."""
        self._queue_rereads([self._catalogs[u] for u in self._public_smart if u in self._catalogs])

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
            self._reading = [catalog for catalog, _ in jobs]
            self._read_pool.start(_Read(jobs, self._read_done))

    def _read_job(self, catalog: Catalog):
        """(catalog, its cocat-rs catalogue), its rule noted here on the Qt thread."""
        cocat_cat = self._cocat_catalogue(catalog)
        if cocat_cat is None:
            return None
        try:
            self._note_rule(catalog, cocat_cat)
        except Exception as error:
            self._show_rows(catalog, None, None, error)
            return None
        return catalog, cocat_cat

    def _apply_reads(self, results) -> None:
        self._to_apply.extend(results)
        self._apply_next()

    def _apply_next(self) -> None:
        """One catalogue per turn of the Qt loop: a big one takes a while to show, and the GUI must
        answer in between. The next read starts once all are shown.

        simplify: a changed catalogue's events are all rebuilt in one turn: about 0.25 s for 33 000
        members. Reuse the unchanged events, or build in slices, if catalogues that big are common."""
        while self._to_apply:
            catalog, rows, keys, error = self._to_apply.pop(0)
            if self._catalogs.get(catalog.uuid) is catalog:  # not deleted, nor its project left, meanwhile
                self._show_rows(catalog, rows, keys, error)
                if self._to_apply:
                    return QTimer.singleShot(0, self, self._apply_next)
        self._reading = None
        self._start_next_read()

    def _stop_rereading(self) -> None:
        """At close: the read in flight ends first; its result is then dropped with the catalogues."""
        self._reread_queue = {}
        self._read_pool.waitForDone()
        self._to_apply = []
