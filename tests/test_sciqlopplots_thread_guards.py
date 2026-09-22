"""Behaviour SciQLop relies on from SciQLopPlots >= 0.37.0 (SciQLop#137 and #138), checked
against SciQLopPlots itself, without SciQLop's own workarounds in between."""
import threading
import time

import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QThread, Qt
from PySide6.QtWidgets import QApplication

from tests.fixtures import *  # noqa: F401,F403
from tests.test_panel_close_busy import _plot_a_blocked_callback


def test_destroying_a_graph_does_not_wait_for_its_running_callback(qtbot, qapp, main_window):
    """Bypasses remove_panel's deferral: the container is deleted while the callback runs."""
    panel, release, returned = _plot_a_blocked_callback(qtbot)
    dock_widget = main_window.dock_manager.findDockWidget(panel._get_impl_or_raise().name)
    container = dock_widget.takeWidget()
    dock_widget.closeDockWidget()

    container.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()

    assert not returned.is_set(), "destroying the graph joined the callback's thread"
    assert not shiboken6.isValid(container)

    # The point of the fix is that this thread outlives the test's own assertions; join it
    # here instead of leaving it to finish on its own, so a dangling worker thread from this
    # test is never still running when a later test's Qt/Shiboken teardown runs its GC sweep.
    release.set()
    qtbot.waitUntil(returned.is_set, timeout=5000)
    qtbot.wait(50)


def test_products_model_add_node_from_a_worker_thread_lands_on_the_gui_thread(qtbot, qapp):
    from SciQLop.core.enums import ParameterType
    from SciQLop.core.models import ProductsModelNode, ProductsModelNodeType, products

    seen = []
    record = lambda *_: seen.append(QThread.currentThread())
    products.rowsAboutToBeInserted.connect(record, Qt.DirectConnection)

    def add_from_the_kernel_thread():
        node = ProductsModelNode("worker_node", "worker", {}, ProductsModelNodeType.PARAMETER,
                                 ParameterType.Scalar, "", None)
        products.add_node(["thread_guard"], node)

    try:
        worker = threading.Thread(target=add_from_the_kernel_thread)
        worker.start()
        worker.join()
        qtbot.waitUntil(lambda: len(seen) > 0, timeout=5000)
    finally:
        products.rowsAboutToBeInserted.disconnect(record)

    assert all(thread == qapp.thread() for thread in seen)
