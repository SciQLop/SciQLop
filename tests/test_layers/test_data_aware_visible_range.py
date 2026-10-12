"""A data-aware layer sees the samples on screen, not the graph's whole buffer.

The buffer also holds prefetched data around the view, so a "max on screen"
marker used to land outside the plot.
"""
import numpy as np
from SciQLopPlots import SciQLopPlotRange
from ..fixtures import *  # noqa: F401,F403
from .test_scope import panel_with_plot  # noqa: F401
from SciQLop.user_api.data_types import Scalar


def _layer_seeing(plot, panel, start, stop):
    from SciQLop.components.plotting.ui.time_sync_panel import wire_layer_renderer
    seen = []

    def spy(data: Scalar):
        seen.append((data.time.min(), data.time.max(), len(data.values)))
        return []

    plot.x_axis().set_range(SciQLopPlotRange(start, stop))
    wire_layer_renderer(plot, spy, panel=panel, scope="plot")
    return seen


def test_the_layer_gets_only_the_visible_samples(panel_with_plot, qtbot):
    panel, plot = panel_with_plot
    t = np.arange(0.0, 100.0)
    plot.line(t, np.sin(t))
    seen = _layer_seeing(plot, panel, 10.0, 20.0)
    qtbot.waitUntil(lambda: len(seen) > 0, timeout=1000)
    lo, hi, n = seen[-1]
    assert 10.0 <= lo and hi <= 20.0 and n == hi - lo + 1


def test_panning_over_loaded_data_reruns_the_layer(panel_with_plot, qtbot):
    panel, plot = panel_with_plot
    t = np.arange(0.0, 100.0)
    plot.line(t, np.sin(t))
    seen = _layer_seeing(plot, panel, 10.0, 20.0)
    qtbot.waitUntil(lambda: len(seen) > 0, timeout=1000)
    plot.x_axis().set_range(SciQLopPlotRange(50.0, 60.0))
    qtbot.waitUntil(lambda: seen[-1][0] >= 50.0 and seen[-1][1] <= 60.0, timeout=1000)
