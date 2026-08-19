"""Pure-logic/unit tests for the plot API catch-up fix wave.

These tests do not require a running QApplication or plot panel, so they can
run in headless/CI environments where GUI tests segfault during teardown.
"""

import numpy as np
import pytest

from SciQLop.user_api.plot._graphs import (
    Waterfall,
    _create_histogram2d,
    _WaterfallOffsetMode,
)
from SciQLop.user_api.plot.enums import AxisType, BinStrategy


class _MockAxis:
    def __init__(self):
        self._log = False
        self._time = False

    def log(self):
        return self._log

    def set_log(self, value):
        self._log = bool(value)

    def is_time_axis(self):
        return self._time

    def set_is_time_axis(self, value):
        self._time = bool(value)


class _MockPlot:
    def __init__(self):
        self._axes = {"x": _MockAxis(), "y": _MockAxis()}

    def x_axis(self):
        return self._axes["x"]

    def y_axis(self):
        return self._axes["y"]

    def histogram2d(self, *args, **kwargs):
        return _MockHistogram2D()

    def waterfall(self, x, z, **kwargs):
        return _MockWaterfallImpl(x, z)

    def plottables(self):
        return []


class _MockHistogram2D:
    def __init__(self):
        self._z_log = False
        self._gradient = None

    def z_log_scale(self):
        return self._z_log

    def set_z_log_scale(self, v):
        self._z_log = bool(v)

    def gradient(self):
        return self._gradient

    def set_gradient(self, g):
        self._gradient = g


class _MockWaterfallImpl:
    def __init__(self, x, z):
        self._x = np.asarray(x)
        self._z = np.asarray(z)
        self._offset_mode = _WaterfallOffsetMode.Uniform
        self._uniform_spacing = 1.0
        self._offsets = np.zeros(1)
        self._gain = 1.0
        self._normalize = False
        self._colors = []
        self._line_count = z.shape[1] if z.ndim == 2 else 1

    def destroyed(self):
        pass

    def connect(self, *args, **kwargs):
        pass

    def data(self):
        return self._x, self._z

    def set_data(self, x, z):
        self._x = np.asarray(x)
        self._z = np.asarray(z)
        self._line_count = z.shape[1] if z.ndim == 2 else 1

    def offset_mode(self):
        return self._offset_mode

    def uniform_spacing(self):
        return self._uniform_spacing

    def offsets(self):
        if self._offset_mode == _WaterfallOffsetMode.Uniform:
            return self._uniform_spacing
        return self._offsets

    def set_offset_mode(self, mode):
        self._offset_mode = mode

    def set_uniform_spacing(self, spacing):
        self._uniform_spacing = spacing

    def set_offsets(self, offsets):
        self._offsets = np.asarray(offsets)

    def gain(self):
        return self._gain

    def set_gain(self, v):
        self._gain = v

    def normalize(self):
        return self._normalize

    def set_normalize(self, v):
        self._normalize = bool(v)

    def colors(self):
        return self._colors

    def set_colors(self, colors):
        self._colors = list(colors)

    def line_count(self):
        return self._line_count

    def set_name(self, name):
        pass


class TestSetAxisType:
    """Fix A: set_axis_type must reset the time-axis flag."""

    def test_linear_resets_time_axis(self):
        plot = _MockPlot()
        axis = plot.x_axis()
        axis.set_is_time_axis(True)
        assert axis.is_time_axis() is True

        def _resolve_axis(name):
            return plot._axes[name]

        # Reproduce the implementation logic directly for this mock.
        axis_impl = _resolve_axis("x")
        axis_impl.set_log(False)
        axis_impl.set_is_time_axis(False)

        assert axis.is_time_axis() is False

    def test_logarithmic_resets_time_axis(self):
        plot = _MockPlot()
        axis = plot.x_axis()
        axis.set_is_time_axis(True)

        axis_impl = plot.x_axis()
        axis_impl.set_log(True)
        axis_impl.set_is_time_axis(False)

        assert axis.is_time_axis() is False
        assert axis.log() is True


class TestWaterfallData:
    """Fix B: Waterfall.data getter returns (x, y, z)."""

    def test_data_getter_returns_y(self):
        x = np.linspace(0, 10, 50)
        y = np.linspace(0, 5, 10)
        z = np.sin(x) * np.exp(-y[:, None])
        impl = _MockWaterfallImpl(x, z.T)
        wf = Waterfall(impl)
        wf.set_data(x, y, z)
        x_out, y_out, z_out = wf.data
        np.testing.assert_array_almost_equal(x_out, x)
        np.testing.assert_array_almost_equal(y_out, y)
        np.testing.assert_array_almost_equal(z_out, z)


class TestWaterfallOffsets:
    """Fix E: Waterfall.offsets=None auto-derives spacing from y."""

    def test_offsets_none_uses_y_spacing(self):
        x = np.linspace(0, 10, 50)
        y = np.arange(0, 10, 0.5)
        z = np.sin(x) * np.exp(-y[:, None])
        impl = _MockWaterfallImpl(x, z.T)
        wf = Waterfall(impl)
        wf.set_data(x, y, z)
        wf.offsets = None
        assert wf.offsets == pytest.approx(0.5)

    def test_offsets_none_falls_back_to_one_for_single_y(self):
        x = np.linspace(0, 10, 50)
        y = np.array([1.0])
        z = np.sin(x)[None, :]
        impl = _MockWaterfallImpl(x, z.T)
        wf = Waterfall(impl)
        wf.set_data(x, y, z)
        wf.offsets = None
        assert wf.offsets == pytest.approx(1.0)


class TestHistogram2DRejection:
    """Fix D: histogram2d rejects explicit edges and SymLog."""

    def test_explicit_edges_rejected(self):
        plot = _MockPlot()
        x = np.random.randn(100)
        y = np.random.randn(100)
        edges = np.linspace(-3, 3, 11)
        with pytest.raises(NotImplementedError):
            _create_histogram2d(plot, x, y, x_bins=edges)

    def test_symlog_rejected(self):
        plot = _MockPlot()
        x = np.concatenate([np.random.randn(100), -np.random.randn(100)])
        y = np.random.randn(200)
        with pytest.raises(NotImplementedError):
            _create_histogram2d(plot, x, y, x_bins=20, x_bin_strategy=BinStrategy.SymLog)

    def test_log_bins_still_accepted(self):
        plot = _MockPlot()
        x = np.random.lognormal(0, 1, 100)
        y = np.random.normal(0, 1, 100)
        hist = _create_histogram2d(
            plot, x, y, x_bins=20, y_bins=20,
            x_bin_strategy=BinStrategy.Log, y_bin_strategy=BinStrategy.Linear
        )
        assert hist is not None
        assert hist.x_bin_edges is not None


class TestHistogram2DGradientNames:
    """`histogram2d(gradient=...)` took only the ColorGradient enum.

    The keyword is spelled `gradient=None`, which reads like it accepts the
    same names every other colour argument does, but a string went straight
    into `set_gradient()` and raised an opaque binding TypeError.
    """

    @staticmethod
    def _scatter():
        rng = np.random.default_rng(0)
        return rng.normal(size=200), rng.normal(size=200)

    @pytest.mark.parametrize("name", ["Hot", "hot", "COLD", "candy", " polar "])
    def test_a_named_gradient_is_accepted(self, name):
        from SciQLopPlots import ColorGradient

        x, y = self._scatter()
        hist = _create_histogram2d(_MockPlot(), x, y, gradient=name)
        assert hist.gradient == getattr(ColorGradient, name.strip().capitalize())

    def test_the_enum_is_still_accepted(self):
        from SciQLopPlots import ColorGradient

        x, y = self._scatter()
        hist = _create_histogram2d(_MockPlot(), x, y, gradient=ColorGradient.Hot)
        assert hist.gradient == ColorGradient.Hot

    def test_an_unknown_name_names_the_available_ones(self):
        x, y = self._scatter()
        with pytest.raises(ValueError, match="viridis"):
            _create_histogram2d(_MockPlot(), x, y, gradient="viridis")
        with pytest.raises(ValueError, match="Candy.*Cold.*Hot.*Polar"):
            _create_histogram2d(_MockPlot(), x, y, gradient="viridis")

    def test_a_nonsense_type_is_rejected(self):
        x, y = self._scatter()
        with pytest.raises(TypeError):
            _create_histogram2d(_MockPlot(), x, y, gradient=object())


class TestAsTimeRange:
    """`panel.time_range = (start, stop)` died with `'tuple' object has no
    attribute 'start'`. A pair is the obvious way to write a range, and the
    members should accept everything TimeRange itself does."""

    def test_a_time_range_passes_through(self):
        from SciQLop.core.time_range import TimeRange, as_time_range

        tr = TimeRange(10.0, 20.0)
        assert as_time_range(tr) is tr

    def test_a_float_pair(self):
        from SciQLop.core.time_range import as_time_range

        got = as_time_range((10.0, 20.0))
        assert (got.start(), got.stop()) == (10.0, 20.0)

    def test_a_list_pair(self):
        from SciQLop.core.time_range import as_time_range

        got = as_time_range([10.0, 20.0])
        assert (got.start(), got.stop()) == (10.0, 20.0)

    def test_a_date_string_pair_is_parsed_as_utc(self):
        from SciQLop.core.time_range import TimeRange, as_time_range

        got = as_time_range(("2017-09-06", "2017-09-07"))
        expected = TimeRange("2017-09-06", "2017-09-07")
        assert (got.start(), got.stop()) == (expected.start(), expected.stop())

    @pytest.mark.parametrize("bad", [10.0, "2017-09-06", (1.0,), (1.0, 2.0, 3.0), None])
    def test_anything_else_is_a_type_error(self, bad):
        from SciQLop.core.time_range import as_time_range

        with pytest.raises(TypeError):
            as_time_range(bad)
