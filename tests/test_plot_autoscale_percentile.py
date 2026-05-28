"""Tests for percentile-based robust-autoscale defaults applied to fresh plots.

PlotBackendSettings now declares four percentile fields; TimeSyncPanel wires
them onto every new plot's y/y2 axes and colormap plottables.
"""
from .fixtures import *  # noqa: F401, F403 — pulls qapp_cls, main_window, plot_panel
import numpy as np
import pytest
from unittest.mock import patch


@pytest.fixture
def tmp_config_dir(tmp_path):
    with patch("SciQLop.components.settings.backend.entry.SCIQLOP_CONFIG_DIR",
               str(tmp_path)):
        yield tmp_path


class TestSettingsShape:
    def test_default_graph_percentiles_are_pass_through(self, tmp_config_dir):
        from SciQLop.components.settings.backend.plot_backend_settings import (
            PlotBackendSettings,
        )
        s = PlotBackendSettings()
        assert s.graph_autoscale_percentile_low == 0.0
        assert s.graph_autoscale_percentile_high == 100.0

    def test_default_colormap_percentiles_clip_tails(self, tmp_config_dir):
        from SciQLop.components.settings.backend.plot_backend_settings import (
            PlotBackendSettings,
        )
        s = PlotBackendSettings()
        assert s.colormap_autoscale_percentile_low == 2.0
        assert s.colormap_autoscale_percentile_high == 98.0

    def test_invalid_yaml_falls_back_to_defaults(self, tmp_config_dir):
        """ConfigEntry.__init__ catches ValidationError on bad YAML and
        rewrites defaults. Confirms the percentile validators are wired and
        that bad on-disk state can't poison startup."""
        import yaml
        from SciQLop.components.settings.backend.plot_backend_settings import (
            PlotBackendSettings,
        )
        with open(PlotBackendSettings.config_file(), "w") as f:
            yaml.safe_dump(
                {
                    "graph_autoscale_percentile_low": 99.0,
                    "graph_autoscale_percentile_high": 1.0,
                    "colormap_autoscale_percentile_low": 50.0,
                    "colormap_autoscale_percentile_high": 50.0,
                },
                f,
            )
        s = PlotBackendSettings()
        assert s.graph_autoscale_percentile_low == 0.0
        assert s.graph_autoscale_percentile_high == 100.0
        assert s.colormap_autoscale_percentile_low == 2.0
        assert s.colormap_autoscale_percentile_high == 98.0


class TestApplicationToNewPlot:
    def test_y_axis_gets_graph_defaults(self, qtbot, qapp, main_window):
        from SciQLop.user_api.plot import create_plot_panel
        panel = create_plot_panel()
        x = np.linspace(0, 10, 50)
        y = np.sin(x)
        plot, _g = panel.plot_data(x, y)
        ax = plot._impl.y_axis()
        assert ax.autoscale_percentile_low() == pytest.approx(0.0)
        assert ax.autoscale_percentile_high() == pytest.approx(100.0)

    def test_y2_axis_gets_graph_defaults(self, qtbot, qapp, main_window):
        from SciQLop.user_api.plot import create_plot_panel
        panel = create_plot_panel()
        x = np.linspace(0, 10, 50)
        y = np.sin(x)
        plot, _g = panel.plot_data(x, y)
        ax = plot._impl.y2_axis()
        assert ax.autoscale_percentile_low() == pytest.approx(0.0)
        assert ax.autoscale_percentile_high() == pytest.approx(100.0)

    def test_histogram2d_gets_colormap_defaults(self, qtbot, qapp, main_window):
        from SciQLop.user_api.plot import create_plot_panel
        panel = create_plot_panel()
        rng = np.random.default_rng(0)
        x = rng.normal(0.0, 1.0, 2000)
        y = rng.normal(0.0, 1.0, 2000)
        _plot, hist = panel.histogram2d(x, y)
        assert hist._impl.autoscale_percentile_low() == pytest.approx(2.0)
        assert hist._impl.autoscale_percentile_high() == pytest.approx(98.0)


class TestSettingsHonored:
    def test_custom_graph_low_applies_to_new_plot(self, qtbot, qapp, main_window,
                                                  tmp_config_dir):
        from SciQLop.components.settings.backend.plot_backend_settings import (
            PlotBackendSettings,
        )
        with PlotBackendSettings() as s:
            s.graph_autoscale_percentile_low = 5.0
            s.graph_autoscale_percentile_high = 95.0
        from SciQLop.user_api.plot import create_plot_panel
        panel = create_plot_panel()
        x = np.linspace(0, 10, 50)
        y = np.sin(x)
        plot, _g = panel.plot_data(x, y)
        ax = plot._impl.y_axis()
        assert ax.autoscale_percentile_low() == pytest.approx(5.0)
        assert ax.autoscale_percentile_high() == pytest.approx(95.0)

    def test_custom_colormap_high_applies_to_new_histogram(
        self, qtbot, qapp, main_window, tmp_config_dir
    ):
        from SciQLop.components.settings.backend.plot_backend_settings import (
            PlotBackendSettings,
        )
        with PlotBackendSettings() as s:
            s.colormap_autoscale_percentile_low = 1.0
            s.colormap_autoscale_percentile_high = 99.0
        from SciQLop.user_api.plot import create_plot_panel
        panel = create_plot_panel()
        rng = np.random.default_rng(1)
        x = rng.normal(0.0, 1.0, 2000)
        y = rng.normal(0.0, 1.0, 2000)
        _plot, hist = panel.histogram2d(x, y)
        assert hist._impl.autoscale_percentile_low() == pytest.approx(1.0)
        assert hist._impl.autoscale_percentile_high() == pytest.approx(99.0)
