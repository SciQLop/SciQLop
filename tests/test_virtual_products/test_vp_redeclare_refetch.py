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
