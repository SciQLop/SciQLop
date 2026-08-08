import numpy as np
import pytest
from SciQLop.user_api.plot import create_plot_panel
from SciQLop.user_api.plot.enums import GraphType, BinStrategy, GraphLineStyle, AxisType


def test_graph_type_has_waterfall():
    assert GraphType.Waterfall.value == 4


def test_bin_strategy_values():
    assert BinStrategy.Linear.value == "linear"
    assert BinStrategy.Log.value == "log"
    assert BinStrategy.SymLog.value == "symlog"


def test_graph_line_style_values():
    assert GraphLineStyle.Solid.value == 0
    assert GraphLineStyle.Dash.value == 1


def test_axis_type_values():
    assert AxisType.Linear.value == 0
    assert AxisType.Logarithmic.value == 1


def test_plot_data_accepts_line_style(qapp):
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    SciQLopMainWindow()
    panel = create_plot_panel()
    _, graph = panel.plot_data(np.arange(10), np.arange(10), line_style=GraphLineStyle.Dash)
    # Upstream may not expose a getter; the call must not raise.


def test_set_axis_type(qapp):
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    SciQLopMainWindow()
    panel = create_plot_panel()
    plot, _ = panel.plot_data(np.arange(10), np.arange(10))
    plot.set_axis_type("y", AxisType.Logarithmic)


def test_set_axis_type_resets_time_axis(qapp):
    from SciQLop.core.ui.mainwindow import SciQLopMainWindow
    SciQLopMainWindow()
    panel = create_plot_panel()
    plot, _ = panel.plot_data(np.arange(10), np.arange(10))
    plot.set_axis_type("x", AxisType.DateTime)
    assert plot._resolve_axis("x").is_time_axis() is True
    plot.set_axis_type("x", AxisType.Linear)
    assert plot._resolve_axis("x").is_time_axis() is False
    plot.set_axis_type("x", AxisType.DateTime)
    plot.set_axis_type("x", AxisType.Logarithmic)
    assert plot._resolve_axis("x").is_time_axis() is False
