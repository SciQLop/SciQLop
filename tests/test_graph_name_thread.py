"""Every user_api Graph property reads Qt state on the GUI thread; `name`
(added this release) read objectName() on the caller's thread, which is the
kernel thread for notebook and agent code."""
import threading

from PySide6.QtCore import QThread

from tests.fixtures import *  # noqa: F401,F403


def test_graph_name_is_read_on_the_gui_thread(qtbot, qapp, main_window):
    from SciQLop.user_api.plot._graphs import _Named

    threads = []

    class _Impl:
        def objectName(self):
            threads.append(QThread.currentThread() is qapp.thread())
            return "B_x"

    class _Graph(_Named):
        _impl = _Impl()

    names = []
    worker = threading.Thread(target=lambda: names.append(_Graph().name))
    worker.start()
    qtbot.waitUntil(lambda: not worker.is_alive(), timeout=3000)
    assert names == ["B_x"]
    assert threads == [True]
