"""Tests for the SciQLop.user_api.dsp facade with SpeasyVariable inputs."""
from .fixtures import *  # noqa: F401, F403  (qapp + plot fixtures)
import numpy as np
import pytest
from speasy.products import SpeasyVariable, VariableTimeAxis
from speasy.core.data_containers import DataContainer
from speasy.core import epoch_to_datetime64


def _make_var(n: int = 1000, dt: float = 0.01, name: str = "test") -> SpeasyVariable:
    epoch = np.arange(n, dtype=np.float64) * dt
    time = epoch_to_datetime64(epoch)
    values = np.sin(2 * np.pi * 1.0 * epoch).astype(np.float64)
    data = DataContainer(values=values, meta={"UNITS": "nT"}, name=name)
    return SpeasyVariable(axes=[VariableTimeAxis(values=time)], values=data)


@pytest.fixture
def dsp(qapp):
    """Defer SciQLop.user_api import past Qt static-init."""
    from SciQLop.user_api import dsp as _dsp
    return _dsp


@pytest.fixture
def var():
    return _make_var()


@pytest.fixture
def var_with_nan():
    v = _make_var()
    v.values[100, 0] = np.nan
    return v


class TestSameAxisTransforms:
    def test_filtfilt_returns_speasy_variable(self, dsp, var):
        coeffs = np.array([0.25, 0.5, 0.25], dtype=np.float64)
        out = dsp.filtfilt(var, coeffs)
        assert isinstance(out, SpeasyVariable)
        assert out.name.endswith("_filtfilt")
        assert out.values.shape == var.values.shape

    def test_interpolate_nan_returns_var(self, dsp, var_with_nan):
        out = dsp.interpolate_nan(var_with_nan, max_consecutive=2)
        assert isinstance(out, SpeasyVariable)
        assert out.name.endswith("_interp_nan")
        assert not np.isnan(out.values[100, 0])

    def test_rolling_mean_returns_var(self, dsp, var):
        out = dsp.rolling_mean(var, window=5)
        assert isinstance(out, SpeasyVariable)
        assert out.name.endswith("_rmean")

    def test_rolling_std_returns_var(self, dsp, var):
        out = dsp.rolling_std(var, window=5)
        assert isinstance(out, SpeasyVariable)
        assert out.name.endswith("_rstd")


class TestNewAxisTransforms:
    def test_resample_changes_time_axis(self, dsp, var):
        out = dsp.resample(var, target_dt=0.02)
        assert isinstance(out, SpeasyVariable)
        assert out.name.endswith("_resample")
        # Roughly half the samples (dt doubled).
        assert 400 <= out.values.shape[0] <= 600

    def test_fft_returns_list_of_tuples(self, dsp, var):
        # fft() returns raw (freqs, magnitude) tuples — SpeasyVariable
        # cannot represent a frequency-only axis.
        result = dsp.fft(var)
        assert isinstance(result, list)
        assert len(result) >= 1
        freqs, magnitude = result[0]
        assert isinstance(freqs, np.ndarray)
        assert isinstance(magnitude, np.ndarray)
        assert freqs.ndim == 1

    def test_spectrogram_returns_list_of_2d_vars(self, dsp, var):
        result = dsp.spectrogram(var, window_size=128, overlap=64)
        assert isinstance(result, list)
        assert len(result) >= 1
        first = result[0]
        assert isinstance(first, SpeasyVariable)
        assert first.name.endswith("_spectrogram")
        assert first.values.ndim == 2
        assert first.axes[1].unit == "Hz"

    def test_split_segments_no_gap(self, dsp, var):
        result = dsp.split_segments(var)
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], SpeasyVariable)


class TestRejectsRawArrays:
    def test_filtfilt_rejects_arrays(self, dsp):
        x = np.arange(10, dtype=np.float64)
        with pytest.raises(TypeError):
            dsp.filtfilt(x, np.array([1.0]))
