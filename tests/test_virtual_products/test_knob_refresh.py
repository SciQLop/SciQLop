"""Reproducer for: changing a knob must re-fetch plot data."""
import pytest

from tests.fixtures import *  # noqa: F401,F403


@pytest.fixture(autouse=True)
def _clean_registry():
    from SciQLop.user_api.virtual_products.registry import _registry
    _registry._entries.clear()
    yield
    _registry._entries.clear()


def _find_graph_with_state(panel):
    for plot in panel.plots():
        for graph in plot.plottables():
            if getattr(graph, "_knob_state", None) is not None:
                return graph
    return None


def test_changing_knob_triggers_callback_refetch(qtbot, qapp, main_window):
    from SciQLop.user_api.virtual_products.magic import vp_magic

    cell = (
        "from typing import Annotated\n"
        "from SciQLop.user_api.knobs import Knob\n"
        "_CALLS = []\n"
        "def my_vp(start: float, stop: float,\n"
        "          fft: Annotated[int, Knob(min=64, max=4096)] = 256) -> Scalar:\n"
        "    import numpy as np\n"
        "    _CALLS.append(fft)\n"
        "    n = 8\n"
        "    return np.linspace(start, stop, n), np.zeros(n) + fft\n"
    )
    ns = {}
    vp_magic("--debug --start 0 --stop 10", cell, local_ns=ns)
    qtbot.wait(200)

    calls_before = list(ns["_CALLS"])
    assert calls_before, "callback should have been invoked once during debug setup"

    from SciQLop.user_api.virtual_products.registry import _registry
    entry = _registry.get("my_vp")
    graph = _find_graph_with_state(entry.panel)
    assert graph is not None, "expected a graph with knob state"

    state = graph._knob_state
    state.set_value("fft", 1024)

    qtbot.waitUntil(lambda: any(c == 1024 for c in ns["_CALLS"]), timeout=3000)
