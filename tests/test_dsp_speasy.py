"""Tests for the SciQLop.user_api.dsp facade with SpeasyVariable inputs."""
from .fixtures import *  # noqa: F401, F403  (qapp + plot fixtures)
import numpy as np
import pytest
from numpy.testing import assert_allclose
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


from speasy.core.data_containers import DataContainer, VariableAxis, VariableTimeAxis
from speasy.products.variable import SpeasyVariable

from SciQLop.user_api import dsp as user_dsp


def _spectrogram_var(n_time=200, n_freq=4, units='sfu'):
    t0 = np.datetime64('2025-07-26T13:00:00', 'ns')
    times = (t0.astype('int64') + np.arange(n_time) * 1_000_000_000).astype('datetime64[ns]')
    freqs = np.linspace(10e6, 240e6, n_freq)
    levels = np.array([10.0 ** (k + 1) for k in range(n_freq)])
    values = np.tile(levels, (n_time, 1))
    return SpeasyVariable(
        axes=[VariableTimeAxis(values=times),
              VariableAxis(name='frequency', values=freqs, meta={'UNITS': 'Hz'})],
        values=DataContainer(values=values, meta={'UNITS': units}, name='ILOFAR'),
        columns=['ILOFAR'],
    )


class TestBackgroundSubtractSpeasy:
    def test_diff_on_flat_input_is_zero(self):
        out = user_dsp.background_subtract(_spectrogram_var())
        assert_allclose(np.asarray(out.values), 0.0, atol=1e-9)

    def test_time_and_frequency_axes_are_preserved(self):
        var = _spectrogram_var()
        out = user_dsp.background_subtract(var)
        assert np.array_equal(out.time, var.time)
        assert_allclose(np.asarray(out.axes[1].values), np.asarray(var.axes[1].values))
        assert np.asarray(out.values).shape == np.asarray(var.values).shape

    def test_name_is_suffixed(self):
        out = user_dsp.background_subtract(_spectrogram_var())
        assert out.name.endswith('_bgsub')

    def test_units_per_mode(self):
        var = _spectrogram_var(units='sfu')
        assert user_dsp.background_subtract(var, mode='diff').meta['UNITS'] == 'sfu'
        assert user_dsp.background_subtract(var, mode='ratio').meta['UNITS'] == ''
        assert user_dsp.background_subtract(var, mode='db').meta['UNITS'] == 'dB'

    def test_sliding_window_accepts_a_duration(self):
        from datetime import timedelta
        var = _spectrogram_var(n_time=300)
        by_samples = user_dsp.background_subtract(var, window=31)
        by_time = user_dsp.background_subtract(var, window=timedelta(seconds=31))
        assert_allclose(np.asarray(by_samples.values), np.asarray(by_time.values), atol=1e-12)

    def test_non_positive_values_give_nan_not_inf(self):
        var = _spectrogram_var(n_time=50, n_freq=1)
        vals = np.asarray(var.values).copy()
        vals[10, 0] = 0.0
        var = SpeasyVariable(axes=list(var.axes),
                             values=DataContainer(values=vals, meta=dict(var.meta),
                                                  name=var.name),
                             columns=var.columns)
        out = np.asarray(user_dsp.background_subtract(var, mode='db').values)
        assert np.isnan(out[10, 0])
        assert not np.isinf(out).any()

    def test_rejects_raw_arrays(self):
        with pytest.raises(TypeError, match="SpeasyVariable"):
            user_dsp.background_subtract(np.ones((10, 2)))
