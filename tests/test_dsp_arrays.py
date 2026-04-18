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
