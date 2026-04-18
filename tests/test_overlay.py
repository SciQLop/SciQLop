"""Tests for the Overlay wrapper exposed via plot.overlay."""
from .fixtures import *  # qapp_cls, sciqlop_resources, main_window, plot_panel
import pytest
import numpy as np


@pytest.fixture
def time_series_plot(plot_panel):
    """A TimeSeriesPlot inside the panel, ready for overlay tests."""
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


class TestEnumTranslation:
    def test_level_round_trip(self, qapp):
        from SciQLop.user_api.plot import OverlayLevel
        from SciQLop.user_api.plot._overlay import _to_sqp_level, _from_sqp_level
        for lvl in OverlayLevel:
            assert _from_sqp_level(_to_sqp_level(lvl)) == lvl

    def test_size_mode_round_trip(self, qapp):
        from SciQLop.user_api.plot import OverlaySizeMode
        from SciQLop.user_api.plot._overlay import _to_sqp_size_mode, _from_sqp_size_mode
        for sm in OverlaySizeMode:
            assert _from_sqp_size_mode(_to_sqp_size_mode(sm)) == sm

    def test_position_round_trip(self, qapp):
        from SciQLop.user_api.plot import OverlayPosition
        from SciQLop.user_api.plot._overlay import _to_sqp_position, _from_sqp_position
        for pos in OverlayPosition:
            assert _from_sqp_position(_to_sqp_position(pos)) == pos


class TestOverlayOnTimeSeriesPlot:
    def test_overlay_property_returns_wrapper(self, time_series_plot):
        from SciQLop.user_api.plot import Overlay
        ov = time_series_plot.overlay
        assert isinstance(ov, Overlay)

    def test_show_text_round_trip(self, time_series_plot):
        from SciQLop.user_api.plot import OverlayLevel
        time_series_plot.overlay.show("hello", level=OverlayLevel.Warning)
        assert time_series_plot.overlay.text == "hello"
        assert time_series_plot.overlay.level == OverlayLevel.Warning

    def test_show_with_size_mode_and_position(self, time_series_plot):
        from SciQLop.user_api.plot import OverlayLevel, OverlaySizeMode, OverlayPosition
        time_series_plot.overlay.show("alert",
                                      level=OverlayLevel.Error,
                                      size_mode=OverlaySizeMode.FullWidget,
                                      position=OverlayPosition.Bottom)
        ov = time_series_plot.overlay
        assert ov.text == "alert"
        assert ov.level == OverlayLevel.Error
        assert ov.size_mode == OverlaySizeMode.FullWidget
        assert ov.position == OverlayPosition.Bottom

    def test_clear_empties_text(self, time_series_plot):
        time_series_plot.overlay.show("temporary")
        assert time_series_plot.overlay.text == "temporary"
        time_series_plot.overlay.clear()
        assert time_series_plot.overlay.text == ""

    def test_collapsible_round_trip(self, time_series_plot):
        time_series_plot.overlay.collapsible = True
        assert time_series_plot.overlay.collapsible is True
        time_series_plot.overlay.collapsible = False
        assert time_series_plot.overlay.collapsible is False

    def test_collapsed_round_trip(self, time_series_plot):
        time_series_plot.overlay.collapsible = True
        time_series_plot.overlay.collapsed = True
        assert time_series_plot.overlay.collapsed is True
        time_series_plot.overlay.collapsed = False
        assert time_series_plot.overlay.collapsed is False

    def test_opacity_round_trip(self, time_series_plot):
        time_series_plot.overlay.opacity = 0.42
        assert time_series_plot.overlay.opacity == pytest.approx(0.42, abs=1e-3)


class TestOverlayOnXYPlot:
    def test_overlay_available_on_xy_plot(self, xy_plot):
        xy_plot.overlay.show("xy hi")
        assert xy_plot.overlay.text == "xy hi"
