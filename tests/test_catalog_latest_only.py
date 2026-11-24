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
