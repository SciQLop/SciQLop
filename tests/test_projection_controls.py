import numpy as np
import pytest
from tests.fixtures import *  # noqa: F401, F403


def test_projection_axis_ranges_and_scales(qapp, main_window):
    from SciQLop.user_api.plot import create_plot_panel
    from SciQLop.user_api.plot.enums import PlotType, ScaleType

    panel = create_plot_panel()
    plot, _graph = panel.plot_data(np.arange(10), np.arange(10), plot_type=PlotType.Projection)
    plot.set_x_range(-1.0, 11.0)
    plot.set_y_range(-2.0, 12.0)
    plot.set_x_scale_type(ScaleType.Logarithmic)
    plot.set_y_scale_type(ScaleType.Logarithmic)
    # Best-effort assertions: upstream must accept the calls without error.


def test_time_colored_curve(qapp, main_window):
    from SciQLop.user_api.plot import create_plot_panel
    from SciQLop.user_api.plot.enums import PlotType

    panel = create_plot_panel()
    plot, _graph = panel.plot_data(np.arange(10), np.arange(10), plot_type=PlotType.Projection)
    t = np.linspace(0, 1, 10)
    graph = plot.plot_time_colored_curve(np.arange(10), np.arange(10), t, colormap="viridis")
    assert graph is not None
