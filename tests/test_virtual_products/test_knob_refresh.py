"""Reproducer for: changing a knob must re-fetch plot data."""
from tests.fixtures import *  # noqa: F401,F403
import pytest



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
    qtbot.waitUntil(lambda: len(ns["_CALLS"]) > 0, timeout=1000)

    from SciQLop.user_api.virtual_products.registry import _registry
    entry = _registry.get("my_vp")
    graph = _find_graph_with_state(entry.panel)
    assert graph is not None, "expected a graph with knob state"

    state = graph._knob_state
    state.set_value("fft", 1024)

    qtbot.waitUntil(lambda: any(c == 1024 for c in ns["_CALLS"]), timeout=3000)


@pytest.mark.parametrize("flags", ["", "--cachable "], ids=["plain", "cachable"])
def test_range_fetched_before_a_knob_change_is_not_served_stale(qtbot, qapp, main_window, flags):
    # --cachable makes the graph prefetch 2x the view (time_sync_panel._apply_prefetch_margin),
    # so SciQLopPlots then serves pans inside that window from its own cache.
    import numpy as np
    from SciQLopPlots import SciQLopPlotRange
    from SciQLop.user_api.virtual_products.magic import vp_magic
    from SciQLop.user_api.virtual_products.registry import _registry

    cell = (
        "from typing import Annotated\n"
        "from SciQLop.user_api.knobs import Knob\n"
        "_CALLS = []\n"
        "def stale_vp(start: float, stop: float,\n"
        "             level: Annotated[int, Knob(min=0, max=4096)] = 256) -> Scalar:\n"
        "    import numpy as np\n"
        "    _CALLS.append((start, level))\n"
        "    n = 8\n"
        "    return np.linspace(start, stop, n), np.zeros(n) + level\n"
    )
    ns = {}
    vp_magic(f"{flags}--debug --start 0 --stop 10", cell, local_ns=ns)
    graph = None

    def _fetched(lo, hi, level):
        return any(lo <= s < hi and lv == level for s, lv in ns["_CALLS"])

    def _graph():
        nonlocal graph
        entry = _registry.get("stale_vp")
        graph = _find_graph_with_state(entry.panel) if entry and entry.panel else None
        return graph is not None

    def _plotted_level():
        data = graph.data()
        values = None if data is None or len(data) < 2 else data[1]
        if values is None or len(values) == 0:
            return None
        return float(np.asarray(values).ravel()[0])

    qtbot.waitUntil(_graph, timeout=2000)
    assert (graph.prefetch_margin() > 0) == bool(flags)
    qtbot.waitUntil(lambda: _plotted_level() == 256, timeout=3000)
    axis = graph.x_axis()
    axis.set_range(SciQLopPlotRange(1000.0, 1010.0))
    qtbot.waitUntil(lambda: _fetched(900.0, 1010.0, 256), timeout=3000)
    qtbot.wait(200)

    graph._knob_state.set_value("level", 1024)
    qtbot.waitUntil(lambda: _fetched(900.0, 1010.0, 1024), timeout=3000)
    qtbot.waitUntil(lambda: _plotted_level() == 1024, timeout=3000)

    axis.set_range(SciQLopPlotRange(0.0, 10.0))
    qtbot.waitUntil(lambda: _fetched(-100.0, 10.0, 1024), timeout=3000)
    qtbot.waitUntil(lambda: _plotted_level() == 1024, timeout=3000)

    axis.set_range(SciQLopPlotRange(2.0, 12.0))
    qtbot.wait(300)
    assert _plotted_level() == 1024
