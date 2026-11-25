"""Background work where only the last request's answer is shown."""
import threading
import time

from .fixtures import *  # noqa: F401,F403


def test_only_the_last_answer_comes_back_and_off_the_gui_thread(qtbot):
    from SciQLop.components.catalogs.ui.latest_only import LatestOnly
    worker = LatestOnly()
    answers, threads = [], []

    def slow(value):
        def work():
            threads.append(threading.current_thread() is threading.main_thread())
            time.sleep(0.05)
            return value
        return work

    worker.done.connect(answers.append)
    for value in (1, 2, 3):
        worker.submit(slow(value))
    qtbot.waitUntil(lambda: answers == [3], timeout=3000)
    qtbot.wait(150)
    assert answers == [3] and threads and not any(threads)
    worker.stop()


def test_a_failure_is_said_as_text(qtbot):
    from SciQLop.components.catalogs.ui.latest_only import LatestOnly
    worker = LatestOnly()
    failures = []
    worker.failed.connect(failures.append)
    worker.submit(lambda: 1 / 0)
    qtbot.waitUntil(lambda: bool(failures), timeout=3000)
    assert "division" in failures[0]
    worker.stop()


def test_stop_drops_what_is_still_to_come(qtbot):
    from SciQLop.components.catalogs.ui.latest_only import LatestOnly
    worker = LatestOnly()
    answers = []
    worker.done.connect(answers.append)
    worker.submit(lambda: (time.sleep(0.1), "late")[1])
    worker.stop()
    qtbot.wait(150)
    assert answers == []


def _started_slow_job(worker, seconds, value="late"):
    started = threading.Event()
    worker.submit(lambda: (started.set(), time.sleep(seconds), value)[2])
    assert started.wait(2)


def test_stop_does_not_wait_for_the_job_in_flight(qtbot):
    from SciQLop.components.catalogs.ui.latest_only import LatestOnly
    worker = LatestOnly()
    _started_slow_job(worker, 0.4)
    began = time.perf_counter()
    worker.stop()
    assert time.perf_counter() - began < 0.05


def test_a_worker_deleted_while_its_job_runs_hears_nothing(qtbot):
    import shiboken6
    from PySide6.QtCore import QObject
    from SciQLop.components.catalogs.ui.latest_only import LatestOnly
    owner = QObject()
    worker = LatestOnly(owner)
    answers = []
    worker.done.connect(answers.append)
    _started_slow_job(worker, 0.2)
    worker.stop()
    shiboken6.delete(owner)
    qtbot.wait(400)
    assert answers == []
