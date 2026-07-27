"""Tests for the dsp arrays layer (numpy pass-through to SciQLopPlots.dsp)."""
from .fixtures import *  # qapp_cls, sciqlop_resources (sets up Qt app before SciQLopPlots import)
import numpy as np
import pytest


@pytest.fixture
def dsp(qapp):
    """Import the dsp arrays layer after Qt has been initialised."""
    from SciQLop.user_api.dsp import _arrays as _dsp
    return _dsp


@pytest.fixture
def synthetic_signal():
    """A 1000-sample signal: 1 Hz sine + DC, sampled at 100 Hz."""
    t = np.arange(0, 10, 0.01, dtype=np.float64)
    y = (np.sin(2 * np.pi * 1.0 * t) + 0.5).astype(np.float64)
    return t, y


@pytest.fixture
def signal_with_gap():
    t1 = np.arange(0, 5, 0.01, dtype=np.float64)
    t2 = np.arange(10, 15, 0.01, dtype=np.float64)
    t = np.concatenate([t1, t2])
    y = np.sin(2 * np.pi * 1.0 * t).astype(np.float64)
    return t, y


class TestPassthrough:
    def test_split_segments_no_gap(self, dsp, synthetic_signal):
        t, y = synthetic_signal
        segs = dsp.split_segments(t, y)
        assert len(segs) == 1
        assert segs[0] == (0, len(t))

    def test_split_segments_with_gap(self, dsp, signal_with_gap):
        t, y = signal_with_gap
        segs = dsp.split_segments(t, y)
        assert len(segs) == 2

    def test_interpolate_nan_returns_y_only(self, dsp, synthetic_signal):
        t, y = synthetic_signal
        y_with_nan = y.copy()
        y_with_nan[100] = np.nan
        out = dsp.interpolate_nan(t, y_with_nan, max_consecutive=2)
        assert isinstance(out, np.ndarray)
        assert out.shape == y.shape
        assert not np.isnan(out[100])

    def test_filtfilt_returns_xy_pair(self, dsp, synthetic_signal):
        t, y = synthetic_signal
        coeffs = np.array([0.25, 0.5, 0.25], dtype=np.float64)
        x_out, y_out = dsp.filtfilt(t, y, coeffs)
        assert x_out.shape == t.shape
        assert y_out.shape == y.shape

    def test_rolling_mean_returns_xy_pair(self, dsp, synthetic_signal):
        t, y = synthetic_signal
        x_out, y_out = dsp.rolling_mean(t, y, window=5)
        assert x_out.shape[0] == y_out.shape[0]

    def test_resample_target_dt(self, dsp, synthetic_signal):
        t, y = synthetic_signal
        x_out, y_out = dsp.resample(t, y, target_dt=0.02)
        assert x_out.shape[0] == y_out.shape[0]
        assert 400 <= x_out.shape[0] <= 600

    def test_fft_returns_list_of_segments(self, dsp, synthetic_signal):
        t, y = synthetic_signal
        result = dsp.fft(t, y)
        assert isinstance(result, list)
        assert len(result) >= 1
        freqs, mag = result[0]
        assert freqs.dtype == np.float64
        assert mag.shape[0] == freqs.shape[0]

    def test_spectrogram_returns_list_of_triples(self, dsp, synthetic_signal):
        t, y = synthetic_signal
        result = dsp.spectrogram(t, y, window_size=128, overlap=64)
        assert isinstance(result, list)
        assert len(result) >= 1
        st, sf, sp = result[0]
        assert sp.shape == (sf.shape[0], st.shape[0]) or sp.shape == (st.shape[0], sf.shape[0])

    def test_reduce_norm(self, dsp, synthetic_signal):
        t, y = synthetic_signal
        y2 = np.column_stack([y, y, y]).astype(np.float64)
        x_out, y_out = dsp.reduce(t, y2, 'norm')
        assert y_out.ndim == 1
        assert y_out.shape[0] == y.shape[0]


from datetime import timedelta

import numpy as np
import pytest
from numpy.testing import assert_allclose

from SciQLop.user_api.dsp import arrays as dsp_arrays


def _flat_spectrogram(n_time=200, n_freq=4, dt=1.0):
    """Per-channel constant level: channel k sits at 10**(k+1)."""
    x = np.arange(n_time, dtype=np.float64) * dt
    levels = np.array([10.0 ** (k + 1) for k in range(n_freq)])
    y = np.tile(levels, (n_time, 1))
    return x, y


class TestBackgroundSubtractArrays:
    def test_constant_background_diff_is_zero_on_flat_input(self):
        x, y = _flat_spectrogram()
        out = dsp_arrays.background_subtract(x, y)
        assert_allclose(out, np.zeros_like(y), atol=1e-9)

    def test_constant_background_ratio_is_one_on_flat_input(self):
        x, y = _flat_spectrogram()
        out = dsp_arrays.background_subtract(x, y, mode='ratio')
        assert_allclose(out, np.ones_like(y), atol=1e-9)

    def test_constant_background_db_is_zero_on_flat_input(self):
        x, y = _flat_spectrogram()
        out = dsp_arrays.background_subtract(x, y, mode='db')
        assert_allclose(out, np.zeros_like(y), atol=1e-9)

    def test_burst_survives_low_percentile_background(self):
        x, y = _flat_spectrogram(n_time=200, n_freq=2)
        y = y.copy()
        y[100:110, 0] *= 5.0                       # a burst on channel 0
        out = dsp_arrays.background_subtract(x, y, q=10.0)
        assert out[100:110, 0].min() > 0.0
        assert_allclose(out[:100, 0], 0.0, atol=1e-9)

    def test_sliding_background_removes_drift_that_constant_cannot(self):
        n = 400
        x = np.arange(n, dtype=np.float64)
        drift = np.linspace(0.0, 100.0, n)
        y = (np.full(n, 50.0) + drift).reshape(n, 1)
        const = dsp_arrays.background_subtract(x, y)
        slide = dsp_arrays.background_subtract(x, y, window=31)
        margin = 40                                # skip the shrinking edges
        assert np.abs(slide[margin:-margin]).max() < np.abs(const[margin:-margin]).max() / 10.0

    def test_sliding_background_realigns_across_a_gap(self):
        # rolling_percentile goes through the gap-aware pipeline, which
        # reassembles segments with one extra NaN separator row per gap. The
        # background must still line up row-for-row with the input.
        x = np.concatenate([np.arange(100.0), np.arange(100.0) + 150.0])
        y = np.concatenate([np.full(100, 10.0), np.full(100, 50.0)]).reshape(200, 1)
        out = dsp_arrays.background_subtract(x, y, window=11)
        assert out.shape == y.shape
        assert np.isfinite(out).all()
        assert_allclose(out, 0.0, atol=1e-9)

    def test_window_as_timedelta_matches_equivalent_samples(self):
        n = 300
        x = np.arange(n, dtype=np.float64) * 2.0   # dt = 2 s
        y = np.random.default_rng(3).normal(size=(n, 2)) + 100.0
        by_samples = dsp_arrays.background_subtract(x, y, window=15)
        by_time = dsp_arrays.background_subtract(x, y, window=timedelta(seconds=30))
        assert_allclose(by_samples, by_time, atol=1e-12)

    def test_window_as_numpy_timedelta64_matches_equivalent_samples(self):
        n = 300
        x = np.arange(n, dtype=np.float64) * 2.0
        y = np.random.default_rng(4).normal(size=(n, 2)) + 100.0
        by_samples = dsp_arrays.background_subtract(x, y, window=15)
        by_time = dsp_arrays.background_subtract(x, y, window=np.timedelta64(30, 's'))
        assert_allclose(by_samples, by_time, atol=1e-12)

    def test_bare_float_window_is_rejected(self):
        x, y = _flat_spectrogram()
        with pytest.raises(TypeError, match="int"):
            dsp_arrays.background_subtract(x, y, window=30.0)

    def test_bool_window_is_rejected(self):
        x, y = _flat_spectrogram()
        with pytest.raises(TypeError):
            dsp_arrays.background_subtract(x, y, window=True)

    def test_non_positive_values_give_nan_not_inf(self):
        x, y = _flat_spectrogram(n_time=50, n_freq=1)
        y = y.copy()
        y[10, 0] = 0.0
        y[11, 0] = -5.0
        for mode in ('ratio', 'db'):
            out = dsp_arrays.background_subtract(x, y, mode=mode)
            assert np.isnan(out[10, 0])
            assert np.isnan(out[11, 0])
            assert not np.isinf(out).any()

    def test_diff_needs_no_guard_for_non_positive_values(self):
        x, y = _flat_spectrogram(n_time=50, n_freq=1)
        y = y.copy()
        y[10, 0] = -5.0
        out = dsp_arrays.background_subtract(x, y, mode='diff')
        assert np.isfinite(out).all()

    def test_preserves_float32(self):
        x, y = _flat_spectrogram()
        out = dsp_arrays.background_subtract(x, y.astype(np.float32))
        assert out.dtype == np.float32

    def test_unknown_mode_is_rejected(self):
        x, y = _flat_spectrogram()
        with pytest.raises(ValueError, match="mode"):
            dsp_arrays.background_subtract(x, y, mode='decibels')
