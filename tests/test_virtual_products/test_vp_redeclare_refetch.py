"""Reproducer for: redeclaring a VP (%%vp hot reload, same signature) must
refetch graphs already plotted against it, not just swap the callback for
future plots."""
from tests.fixtures import *  # noqa: F401,F403


def test_vp_redeclare_same_signature_refetches_plotted_graph(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.magic import vp_magic

    ns = {"_CALLS": []}
    cell_a = (
        "def my_vp(start: float, stop: float) -> Scalar:\n"
        "    import numpy as np\n"
        "    _CALLS.append('a')\n"
        "    n = 8\n"
        "    return np.linspace(start, stop, n), np.zeros(n)\n"
    )
    # --debug creates a real plotted graph (debug panel) for my_vp.
    vp_magic("--debug --start 0 --stop 10", cell_a, local_ns=ns)
    # Wait for both the magic's smoke-test call AND the graph's own first
    # data fetch, so the redeclare below can't race an in-flight fetch.
    qtbot.waitUntil(lambda: len(ns["_CALLS"]) >= 2, timeout=3000)
    ns["_CALLS"].clear()

    # Same signature, only the body changed -> hot-reload path (no --debug,
    # so nothing re-plots or re-evaluates the function directly: the only
    # way 'b' can appear is if the existing graph gets refetched).
    cell_b = cell_a.replace("_CALLS.append('a')", "_CALLS.append('b')")
    vp_magic("--start 0 --stop 10", cell_b, local_ns=ns)

    qtbot.waitUntil(lambda: "b" in ns["_CALLS"], timeout=3000)


def test_refetch_walks_the_panels_on_the_gui_thread(qtbot, qapp, main_window, monkeypatch):
    """vp_magic runs on the kernel thread. Walking panels -> plots -> graphs
    from there raced panel teardown, one proxied call at a time."""
    import threading
    from PySide6.QtCore import QThread
    from SciQLop.components.plotting.ui import time_sync_panel

    on_gui_thread = []

    class _Window:
        def plot_panels(self):
            on_gui_thread.append(QThread.currentThread() is qapp.thread())
            return []

    monkeypatch.setattr("SciQLop.user_api.gui.get_main_window", lambda: _Window())
    worker = threading.Thread(target=time_sync_panel.refetch_graphs_for_vp, args=("any/vp",))
    worker.start()
    qtbot.waitUntil(lambda: not worker.is_alive(), timeout=3000)
    assert on_gui_thread == [True]
