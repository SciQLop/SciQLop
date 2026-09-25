"""A coloured VP plotted for real: the colour reaches the plot's colour scale."""
import numpy as np
import pytest

from tests.fixtures import *  # noqa: F401,F403
from SciQLop.user_api.data_types import Colored

T0 = 1_700_000_000.0


def _traj(start: float, stop: float):
    t = np.linspace(start, stop, 64)
    a = np.linspace(0, 2 * np.pi, 64)
    return Colored((t, np.column_stack([np.cos(a), np.sin(a), a])), color=np.linspace(5.0, 25.0, 64))


def _declare(path):
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType
    return create_virtual_product(path, _traj, VirtualProductType.Vector, labels=["X", "Y", "Z"],
                                  colored=True, color_label="|B| (nT)", color_gradient="thermal")


def _z_range(plot):
    r = plot.z_axis().range()
    return r.start(), r.stop()


def _panel():
    from SciQLop.user_api.plot import create_plot_panel
    panel = create_plot_panel()
    panel.time_range = (T0, T0 + 100.0)
    return panel


def test_time_series_line_is_coloured(qtbot, main_window):
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product
    _declare("colored_test/ts")
    plot, graph = plot_product(_panel()._impl, ["colored_test", "ts"])
    qtbot.waitUntil(lambda: _z_range(plot) == pytest.approx((5.0, 25.0)), timeout=5000)
    assert plot.z_axis().label() == "|B| (nT)"


def test_projection_curve_is_coloured(qtbot, main_window):
    from SciQLopPlots import PlotType
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product
    _declare("colored_test/proj")
    plot, graph = plot_product(_panel()._impl, ["colored_test", "proj"], plot_type=PlotType.Projections)
    qtbot.waitUntil(lambda: _z_range(plot) == pytest.approx((5.0, 25.0)), timeout=5000)
    assert plot.z_axis().label() == "|B| (nT)"
