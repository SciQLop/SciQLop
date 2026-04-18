"""Tests for Histogram2D plottable and panel/plot histogram2d() methods."""
from .fixtures import *  # qapp_cls, sciqlop_resources, main_window, plot_panel
import numpy as np
import pytest


def _scatter(n: int = 5000, seed: int = 0):
    rng = np.random.default_rng(seed)
    x = rng.normal(0.0, 1.0, n)
    y = rng.normal(0.0, 1.0, n)
    return x, y


class TestPanelHistogram2D:
    def test_creates_xy_plot_and_histogram(self, plot_panel):
        from SciQLop.user_api.plot import Histogram2D, XYPlot
        x, y = _scatter()
        plot, hist = plot_panel.histogram2d(x, y, name="density",
                                            key_bins=64, value_bins=32)
        assert isinstance(plot, XYPlot)
        assert isinstance(hist, Histogram2D)

    def test_z_log_scale_round_trip(self, plot_panel):
        x, y = _scatter()
        _plot, hist = plot_panel.histogram2d(x, y, z_log_scale=True)
        assert hist.z_log_scale is True
        hist.z_log_scale = False
        assert hist.z_log_scale is False

    def test_visible_round_trip(self, plot_panel):
        x, y = _scatter()
        _plot, hist = plot_panel.histogram2d(x, y)
        assert hist.visible is True
        hist.visible = False
        assert hist.visible is False

    def test_set_data_replaces_arrays(self, plot_panel):
        x, y = _scatter(1000, seed=1)
        _plot, hist = plot_panel.histogram2d(x, y)
        x2, y2 = _scatter(2000, seed=2)
        hist.set_data(x2, y2)

    def test_gradient_accessor(self, plot_panel):
        x, y = _scatter()
        _plot, hist = plot_panel.histogram2d(x, y)
        g = hist.gradient
        assert g is not None


class TestXYPlotHistogram2D:
    def test_adds_histogram_to_existing_plot(self, plot_panel):
        from SciQLop.user_api.plot import Histogram2D
        x, y = _scatter()
        plot, _h1 = plot_panel.histogram2d(x, y, name="h1")
        h2 = plot.histogram2d(x, y, name="h2", key_bins=20, value_bins=20)
        assert isinstance(h2, Histogram2D)
