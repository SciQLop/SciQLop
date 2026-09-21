import os
import sys
import threading
import time

import pytest

from SciQLop.components.profiling.thread_cpu_top import hot_threads, own_python_native_tids

pytestmark = pytest.mark.skipif(not sys.platform.startswith("linux"),
                                reason="thread_cpu_top reads /proc, which only Linux has")


def _spin(stop: threading.Event) -> None:
    while not stop.is_set():
        pass


def test_spinning_thread_ranks_above_idle_thread():
    stop_spin = threading.Event()
    stop_idle = threading.Event()
    spinner = threading.Thread(target=_spin, args=(stop_spin,), name="spinner", daemon=True)
    idler = threading.Thread(target=stop_idle.wait, name="idler", daemon=True)
    spinner.start()
    idler.start()
    try:
        threads = hot_threads(os.getpid(), window_s=0.3)
        by_tid = {t.tid: t for t in threads}
        assert spinner.native_id in by_tid
        assert idler.native_id in by_tid
        assert by_tid[spinner.native_id].cpu_seconds > by_tid[idler.native_id].cpu_seconds
        ranked_tids = [t.tid for t in threads]
        assert ranked_tids.index(spinner.native_id) < ranked_tids.index(idler.native_id)
    finally:
        stop_spin.set()
        stop_idle.set()
        spinner.join()
        idler.join()


def test_threads_are_sorted_descending_by_cpu_seconds():
    threads = hot_threads(os.getpid(), window_s=0.1)
    cpu_seconds = [t.cpu_seconds for t in threads]
    assert cpu_seconds == sorted(cpu_seconds, reverse=True)


def test_own_python_threads_are_flagged_is_python():
    marker = threading.Event()
    t = threading.Thread(target=marker.wait, name="marked-thread", daemon=True)
    t.start()
    try:
        native_tids = own_python_native_tids()
        assert t.native_id in native_tids
        threads = hot_threads(os.getpid(), window_s=0.1)
        by_tid = {th.tid: th for th in threads}
        assert by_tid[t.native_id].is_python is True
        assert by_tid[t.native_id].name
    finally:
        marker.set()
        t.join()
