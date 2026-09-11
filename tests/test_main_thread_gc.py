"""Python's cyclic GC runs on whichever thread trips the allocation threshold.
On a worker thread it finalizes Python-owned QObjects that live on the GUI
thread; Qt then destroys them from the wrong thread ("QBasicTimer::stop:
Failed. Possibly trying to stop from a different thread") and a later timer
tick dereferences freed memory (macOS crash report 2026-09-11, thread
_TscatDriverWorker inside gc_collect_main while the GUI thread died in
QTimerInfoList::activateTimers). The collector below pins all collections to
the GUI thread."""
import gc
import threading

from SciQLop.core.main_thread_gc import MainThreadGarbageCollector


class _Cycle:
    finalized_on: list = []

    def __init__(self):
        self.me = self

    def __del__(self):
        _Cycle.finalized_on.append(threading.current_thread())


def _drop_cycles_on_a_worker_thread(n=5000):
    def work():
        for _ in range(n):
            _Cycle()
    t = threading.Thread(target=work)
    t.start()
    t.join()


def test_without_the_collector_a_worker_thread_finalizes_gui_garbage():
    gc.collect()
    _Cycle.finalized_on = []
    _drop_cycles_on_a_worker_thread()
    assert any(t is not threading.main_thread() for t in _Cycle.finalized_on)


def test_collector_finalizes_worker_thread_garbage_on_the_gui_thread(qtbot):
    gc.collect()                # leftovers from other tests, before we start logging
    _Cycle.finalized_on = []
    collector = MainThreadGarbageCollector(interval_ms=20)
    collector.start()
    try:
        assert not gc.isenabled()
        _drop_cycles_on_a_worker_thread()
        assert _Cycle.finalized_on == []
        qtbot.waitUntil(lambda: len(_Cycle.finalized_on) >= 5000, timeout=5000)
        assert set(_Cycle.finalized_on) == {threading.main_thread()}
    finally:
        collector.stop()
    assert gc.isenabled()
