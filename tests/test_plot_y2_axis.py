"""Tests for the secondary y-axis (y2) surface on XYPlot / TimeSeriesPlot.

Covers label/scale/range/visibility, the generic ``set_axis_range`` helper,
``Graph.y_axis`` retargeting, and the ``y_axis="y2"`` kwarg on ``plot()``.
"""
from .fixtures import *
import pytest
import numpy as np


@pytest.fixture
def time_series_plot(plot_panel):
    x = np.linspace(0, 100, 50)
    y = np.sin(x)
    plot, _graph = plot_panel.plot_data(x, y)
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


class TestY2Range:
    def test_set_y2_range_round_trip(self, time_series_plot):
        time_series_plot.set_y2_range(-2.0, 5.0)
        lo, hi = time_series_plot._impl.y2_axis().range()
        assert lo == pytest.approx(-2.0)
        assert hi == pytest.approx(5.0)

    def test_set_y2_range_swaps_inverted(self, time_series_plot):
        time_series_plot.set_y2_range(5.0, -2.0)
        lo, hi = time_series_plot._impl.y2_axis().range()
        assert lo == pytest.approx(-2.0)
        assert hi == pytest.approx(5.0)

    def test_set_y2_range_zero_width_raises(self, time_series_plot):
        with pytest.raises(ValueError, match="zero-width y2-axis range"):
            time_series_plot.set_y2_range(1.0, 1.0)

    def test_set_y2_range_on_xy_plot(self, xy_plot):
        xy_plot.set_y2_range(-1.0, 1.0)
        lo, hi = xy_plot._impl.y2_axis().range()
        assert lo == pytest.approx(-1.0)
        assert hi == pytest.approx(1.0)


class TestY2ScaleType:
    def test_y2_scale_default_linear(self, time_series_plot):
        from SciQLop.user_api.plot import ScaleType
        assert time_series_plot.y2_scale_type == ScaleType.Linear

    def test_y2_scale_set_log(self, time_series_plot):
        from SciQLop.user_api.plot import ScaleType
        time_series_plot.y2_scale_type = ScaleType.Logarithmic
        assert time_series_plot.y2_scale_type == ScaleType.Logarithmic
        assert time_series_plot._impl.y2_axis().log() is True

    def test_y2_scale_does_not_touch_y(self, time_series_plot):
        from SciQLop.user_api.plot import ScaleType
        time_series_plot.y2_scale_type = ScaleType.Logarithmic
        assert time_series_plot._impl.y_axis().log() is False


class TestY2Visible:
    def test_y2_visible_round_trip(self, time_series_plot):
        time_series_plot.y2_visible = False
        assert time_series_plot.y2_visible is False
        time_series_plot.y2_visible = True
        assert time_series_plot.y2_visible is True


class TestSetAxisRangeGeneric:
    def test_set_axis_range_y(self, time_series_plot):
        time_series_plot.set_axis_range("y", -3.0, 7.0)
        lo, hi = time_series_plot._impl.y_axis().range()
        assert lo == pytest.approx(-3.0)
        assert hi == pytest.approx(7.0)

    def test_set_axis_range_y2(self, time_series_plot):
        time_series_plot.set_axis_range("y2", 0.0, 10.0)
        lo, hi = time_series_plot._impl.y2_axis().range()
        assert lo == pytest.approx(0.0)
        assert hi == pytest.approx(10.0)

    def test_set_axis_range_unknown_raises(self, time_series_plot):
        with pytest.raises(ValueError, match="axis 'bogus'"):
            time_series_plot.set_axis_range("bogus", 0.0, 1.0)

    def test_set_axis_range_zero_width_raises(self, time_series_plot):
        with pytest.raises(ValueError, match="zero-width y2-axis range"):
            time_series_plot.set_axis_range("y2", 4.0, 4.0)


class TestY2LabelAndScaleViaGeneric:
    def test_set_axis_label_y2(self, time_series_plot):
        time_series_plot.set_axis_label("y2", "Energy", unit="eV")
        assert time_series_plot._impl.y2_axis().label() == "Energy [eV]"

    def test_set_axis_scale_y2(self, time_series_plot):
        from SciQLop.user_api.plot import ScaleType
        time_series_plot.set_axis_scale("y2", ScaleType.Logarithmic)
        assert time_series_plot._impl.y2_axis().log() is True


class TestGraphYAxisRetarget:
    def test_graph_default_on_y(self, time_series_plot):
        x = np.array([1.0, 2.0, 3.0])
        y = np.array([10.0, 20.0, 30.0])
        g = time_series_plot.scatter(x, y)
        assert g.y_axis == "y"

    def test_graph_y_axis_setter_to_y2(self, time_series_plot):
        x = np.array([1.0, 2.0, 3.0])
        y = np.array([10.0, 20.0, 30.0])
        g = time_series_plot.scatter(x, y)
        g.y_axis = "y2"
        assert g.y_axis == "y2"
        assert g._impl.y_axis() is time_series_plot._impl.y2_axis()

    def test_graph_y_axis_setter_back_to_y(self, time_series_plot):
        x = np.array([1.0, 2.0, 3.0])
        y = np.array([10.0, 20.0, 30.0])
        g = time_series_plot.scatter(x, y)
        g.y_axis = "y2"
        g.y_axis = "y"
        assert g.y_axis == "y"
        assert g._impl.y_axis() is time_series_plot._impl.y_axis()

    def test_graph_y_axis_setter_unknown_raises(self, time_series_plot):
        x = np.array([1.0, 2.0])
        y = np.array([10.0, 20.0])
        g = time_series_plot.scatter(x, y)
        with pytest.raises(ValueError, match="axis 'bogus'"):
            g.y_axis = "bogus"


class TestPlotYAxisKwarg:
    def test_time_series_plot_y2_kwarg(self, time_series_plot):
        x = np.array([1.0, 2.0, 3.0])
        y = np.array([10.0, 20.0, 30.0])
        g = time_series_plot.plot(x, y, y_axis="y2")
        assert g.y_axis == "y2"

    def test_xy_plot_y2_kwarg(self, xy_plot):
        x = np.array([1.0, 2.0, 3.0])
        y = np.array([10.0, 20.0, 30.0])
        g = xy_plot.plot(x, y, y_axis="y2")
        assert g.y_axis == "y2"

    def test_default_axis_is_y(self, time_series_plot):
        x = np.array([1.0, 2.0, 3.0])
        y = np.array([10.0, 20.0, 30.0])
        g = time_series_plot.plot(x, y)
        assert g.y_axis == "y"
