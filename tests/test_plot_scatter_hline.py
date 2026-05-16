"""Tests for scatter(), add_hline(), remove_graph(), and HorizontalLine."""
from .fixtures import *
import pytest
import numpy as np


@pytest.fixture
def time_series_plot(plot_panel):
    from SciQLop.user_api.plot import PlotType
    x = np.linspace(0, 100, 50)
    y = np.sin(x)
    plot, _graph = plot_panel.plot_data(x, y, plot_type=PlotType.TimeSeries)
    return plot


@pytest.fixture
def xy_plot(plot_panel):
    from SciQLop.user_api.plot import PlotType
    from SciQLop.user_api.plot.enums import GraphType
    x = np.linspace(0, 100, 50)
    y = np.sin(x)
    plot, _graph = plot_panel.plot_data(x, y, plot_type=PlotType.XY,
                                        graph_type=GraphType.Curve)
    return plot


class TestScatter:
    def test_scatter_returns_graph(self, time_series_plot):
        from SciQLop.user_api.plot._graphs import Graph
        x = np.array([1.0, 2.0, 3.0])
        y = np.array([10.0, 20.0, 30.0])
        g = time_series_plot.scatter(x, y)
        assert isinstance(g, Graph)

    def test_scatter_on_xy_plot(self, xy_plot):
        from SciQLop.user_api.plot._graphs import Graph
        x = np.array([1.0, 2.0])
        y = np.array([5.0, 6.0])
        g = xy_plot.scatter(x, y)
        assert isinstance(g, Graph)

    def test_scatter_set_data(self, time_series_plot):
        x = np.array([1.0, 2.0, 3.0])
        y = np.array([10.0, 20.0, 30.0])
        g = time_series_plot.scatter(x, y)
        g.set_data(np.array([4.0, 5.0]), np.array([40.0, 50.0]))

    def test_scatter_converts_non_float64(self, time_series_plot):
        from SciQLop.user_api.plot._graphs import Graph
        x = [1, 2, 3]
        y = [10, 20, 30]
        g = time_series_plot.scatter(x, y)
        assert isinstance(g, Graph)


class TestAddHLine:
    def test_returns_horizontal_line(self, time_series_plot):
        from SciQLop.user_api.plot._graphic_primitives import HorizontalLine
        hl = time_series_plot.add_hline(5.0)
        assert isinstance(hl, HorizontalLine)

    def test_value_round_trip(self, time_series_plot):
        hl = time_series_plot.add_hline(5.0)
        assert hl.value == pytest.approx(5.0)
        hl.value = 10.0
        assert hl.value == pytest.approx(10.0)

    def test_color_kwarg(self, time_series_plot):
        from PySide6.QtGui import QColor
        hl = time_series_plot.add_hline(3.0, color="#ff0000")
        assert hl.color == QColor("#ff0000")

    def test_color_round_trip(self, time_series_plot):
        from PySide6.QtGui import QColor
        hl = time_series_plot.add_hline(3.0)
        hl.color = "#00ff00"
        assert hl.color == QColor("#00ff00")

    def test_line_width_round_trip(self, time_series_plot):
        hl = time_series_plot.add_hline(3.0)
        hl.line_width = 3.0
        assert hl.line_width == pytest.approx(3.0)

    def test_remove(self, time_series_plot):
        hl = time_series_plot.add_hline(5.0)
        hl.remove()
        assert hl._impl is None

    def test_on_xy_plot(self, xy_plot):
        from SciQLop.user_api.plot._graphic_primitives import HorizontalLine
        hl = xy_plot.add_hline(7.0)
        assert isinstance(hl, HorizontalLine)
        assert hl.value == pytest.approx(7.0)


class TestRemoveGraph:
    def test_remove_scatter(self, time_series_plot):
        x = np.array([1.0, 2.0, 3.0])
        y = np.array([10.0, 20.0, 30.0])
        g = time_series_plot.scatter(x, y)
        time_series_plot.remove_graph(g)

    def test_remove_line_graph(self, plot_panel):
        from SciQLop.user_api.plot import PlotType
        x = np.linspace(0, 100, 50)
        y = np.sin(x)
        plot, graph = plot_panel.plot_data(x, y, plot_type=PlotType.TimeSeries)
        plot.remove_graph(graph)


class TestRescaleAxes:
    def test_rescale_axes_on_xy_plot(self, xy_plot):
        xy_plot.rescale_axes()

    def test_rescale_axes_on_time_series_plot(self, time_series_plot):
        time_series_plot.rescale_axes()


class TestApplyHints:
    def test_apply_hints_sets_labels(self, time_series_plot):
        from SciQLop.core.plot_hints import PlotHints, AxisHints
        hints = PlotHints(y=AxisHints(label="B", unit="nT"))
        time_series_plot.apply_hints(hints)
        assert time_series_plot._impl.y_axis().label() == "B [nT]"

    def test_apply_hints_sets_log_scale(self, time_series_plot):
        from SciQLop.core.plot_hints import PlotHints, AxisHints
        hints = PlotHints(y=AxisHints(scale="log"))
        time_series_plot.apply_hints(hints)
        assert time_series_plot._impl.y_axis().log() is True

    def test_set_axis_label_no_unit(self, time_series_plot):
        time_series_plot.set_axis_label("y", "velocity")
        assert time_series_plot._impl.y_axis().label() == "velocity"

    def test_set_axis_label_with_unit(self, time_series_plot):
        time_series_plot.set_axis_label("y", "velocity", unit="km/s")
        assert time_series_plot._impl.y_axis().label() == "velocity [km/s]"

    def test_set_axis_label_unknown_axis_raises(self, time_series_plot):
        with pytest.raises(ValueError, match="axis 'bogus'"):
            time_series_plot.set_axis_label("bogus", "x")

    def test_set_axis_scale_log(self, time_series_plot):
        from SciQLop.user_api.plot import ScaleType
        time_series_plot.set_axis_scale("y", ScaleType.Logarithmic)
        assert time_series_plot._impl.y_axis().log() is True

    def test_set_axis_scale_linear(self, time_series_plot):
        from SciQLop.user_api.plot import ScaleType
        time_series_plot.set_axis_scale("y", ScaleType.Logarithmic)
        time_series_plot.set_axis_scale("y", ScaleType.Linear)
        assert time_series_plot._impl.y_axis().log() is False

    def test_apply_hints_on_xy_plot(self, xy_plot):
        from SciQLop.core.plot_hints import PlotHints, AxisHints
        hints = PlotHints(x=AxisHints(label="t", unit="s"),
                          y=AxisHints(label="signal"))
        xy_plot.apply_hints(hints)
        assert xy_plot._impl.x_axis().label() == "t [s]"
        assert xy_plot._impl.y_axis().label() == "signal"


class TestZeroWidthRangeRejected:
    def test_xy_set_x_range_equal_raises(self, xy_plot):
        with pytest.raises(ValueError, match="zero-width x-axis range"):
            xy_plot.set_x_range(1.0, 1.0)

    def test_xy_set_y_range_equal_raises(self, xy_plot):
        with pytest.raises(ValueError, match="zero-width y-axis range"):
            xy_plot.set_y_range(0.0, 0.0)

    def test_time_series_set_y_range_equal_raises(self, time_series_plot):
        with pytest.raises(ValueError, match="zero-width y-axis range"):
            time_series_plot.set_y_range(2.0, 2.0)

    def test_xy_set_x_range_non_zero_ok(self, xy_plot):
        xy_plot.set_x_range(0.0, 1.0)


class TestSecondColormapRejected:
    def test_second_colormap_via_plot_raises_on_xy(self, plot_panel):
        from SciQLop.user_api.plot import PlotType
        nx, ny = 8, 6
        x = np.linspace(0, 1, nx)
        y = np.linspace(0, 1, ny)
        z = np.random.rand(nx, ny)
        plot, _ = plot_panel.plot_data(x, y, z, plot_type=PlotType.XY)
        with pytest.raises(RuntimeError, match="colormap-style plottable"):
            plot.plot(x, y, z)

    def test_second_colormap_via_plot_raises_on_time_series(self, plot_panel):
        x = np.linspace(0, 100, 8)
        y = np.linspace(0, 1, 6)
        z = np.random.rand(8, 6)
        plot, _ = plot_panel.plot_data(x, y, z)
        with pytest.raises(RuntimeError, match="colormap-style plottable"):
            plot.plot(x, y, z)
