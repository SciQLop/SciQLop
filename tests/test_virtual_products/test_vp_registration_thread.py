"""Reproducer for #138: registering a virtual product from the kernel thread
mutated ProductsModel off the GUI thread (cross-thread setParent, dangling nodes
in the filter model, segfault on the next search query)."""
import threading
import time

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import QApplication

from tests.fixtures import *  # noqa: F401,F403


class _BlockingInvoker(QObject):
    run_requested = Signal()

    def __init__(self):
        super().__init__()
        self._call = None
        self._result = None
        self.run_requested.connect(self._run, Qt.BlockingQueuedConnection)

    def _run(self):
        self._result = self._call()

    def __call__(self, func, *args, **kwargs):
        self._call = lambda: func(*args, **kwargs)
        self.run_requested.emit()
        return self._result


def _run_on_worker_thread(func, timeout=5.0):
    done = threading.Event()
    worker = threading.Thread(target=lambda: (func(), done.set()))
    worker.start()
    deadline = time.monotonic() + timeout
    while not done.is_set() and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    worker.join(timeout=1)
    assert done.is_set(), "call from worker thread did not complete"


def _emitting_threads_during(register):
    from SciQLop.core.models import products
    from SciQLop.user_api import threading as sqp_threading

    seen = []
    record = lambda *_: seen.append(QThread.currentThread())
    products.rowsAboutToBeInserted.connect(record, Qt.DirectConnection)
    invoker = _BlockingInvoker()
    invoker.moveToThread(QApplication.instance().thread())
    old_invoker = sqp_threading._invoker
    sqp_threading.init_invoker(invoker)
    try:
        _run_on_worker_thread(register)
    finally:
        sqp_threading.init_invoker(old_invoker)
        products.rowsAboutToBeInserted.disconnect(record)
    return seen


def test_virtual_product_registered_from_worker_thread_mutates_model_on_gui_thread(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    import numpy as np

    def vp(start: float, stop: float):
        return np.array([start, stop]), np.zeros(2)

    seen = _emitting_threads_during(
        lambda: create_virtual_product("thread_test/vp_from_worker", vp, VirtualProductType.Scalar, labels=["x"]))

    assert seen, "no model insertion observed"
    assert all(t == qapp.thread() for t in seen)


def test_layer_registered_from_worker_thread_mutates_model_on_gui_thread(qtbot, qapp, main_window):
    from SciQLop.user_api.layers._provider import LayerProvider

    seen = _emitting_threads_during(
        lambda: LayerProvider("thread_test/layer_from_worker", lambda start, stop: []))

    assert seen, "no model insertion observed"
    assert all(t == qapp.thread() for t in seen)
