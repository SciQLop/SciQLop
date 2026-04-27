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
