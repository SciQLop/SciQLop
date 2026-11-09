import numpy as np
import pytest

from SciQLop.components.scenes.boundary import Plane
from SciQLop.plugins.planetary_scenes import MODELS, solar_wind
from SciQLop.plugins.planetary_scenes.models import (Jelinek2012BowShock, Jelinek2012BowShockOmni, Shue1998,
                                                     Shue1998Omni)

_T0 = 1.4449e9   # 2015-10-16


def _omni(pressure, bz, step=60.0):
    """A stand-in for OMNI: constant series on a 1-min grid; NaN entries are fill values or gaps."""
    def get(product, start, stop):
        t = np.arange(start - start % step, stop + step, step)
        value = pressure if product == solar_wind.PRESSURE else bz
        return t, np.broadcast_to(np.asarray(value(t) if callable(value) else value, dtype=float), t.shape).copy()
    return get


@pytest.fixture
def fetches(monkeypatch):
    calls = []

    def install(get):
        def counted(product, start, stop):
            calls.append(product)
            return get(product, start, stop)
        monkeypatch.setattr(solar_wind, "_get", counted)
        solar_wind._upstream.cache_clear()
        return calls
    yield install
    solar_wind._upstream.cache_clear()


def test_values_are_interpolated_onto_the_sample_times(fetches):
    fetches(_omni(lambda t: (t - _T0) / 60, 0.0))
    times = _T0 + np.array([0.0, 30.0, 90.0])
    assert solar_wind.upstream(solar_wind.PRESSURE, times) == pytest.approx([0.0, 0.5, 1.5])


def test_a_gap_longer_than_the_limit_gives_nan_not_a_bridged_value(fetches):
    def with_gap(t):
        return np.where((t > _T0) & (t < _T0 + 3600), np.nan, 2.0)
    fetches(_omni(with_gap, 0.0))
    times = _T0 + np.array([-600.0, 1800.0, 4200.0])
    out = solar_wind.upstream(solar_wind.PRESSURE, times)
    assert out[0] == 2.0 and np.isnan(out[1]) and out[2] == 2.0


def test_the_series_is_fetched_once_for_every_bisection_step(fetches):
    calls = fetches(_omni(2.0, 0.0))
    times = _T0 + np.linspace(0, 3600, 20)
    Shue1998Omni().cross_section(Plane(np.tile([0, 0, 1.0], (20, 1)), np.zeros(20)), times)
    assert sorted(calls) == sorted([solar_wind.PRESSURE, solar_wind.BZ_GSM])


def test_no_data_at_all_is_an_error_the_curve_can_show(monkeypatch):
    monkeypatch.setattr(solar_wind, "_fetch", lambda product, start, stop: None)
    solar_wind._upstream.cache_clear()
    with pytest.raises(ValueError, match="OMNI"):
        solar_wind.upstream(solar_wind.PRESSURE, _T0 + np.arange(3.0))
    solar_wind._upstream.cache_clear()


@pytest.mark.parametrize("driven, nominal", [(Shue1998Omni(), Shue1998()),
                                             (Jelinek2012BowShockOmni(), Jelinek2012BowShock())])
def test_nominal_inputs_give_the_nominal_boundary(fetches, driven, nominal):
    fetches(_omni(2.0, 0.0))
    theta = np.deg2rad(np.array([[0.0, 90.0]]))
    times = np.array([[_T0]])
    assert driven.radius(theta, theta * 0, times) == pytest.approx(nominal.radius(theta, theta * 0, times))


def test_a_higher_pressure_pushes_the_magnetopause_in(fetches):
    fetches(_omni(lambda t: np.where(t < _T0 + 1800, 2.0, 8.0), 0.0))
    theta = np.zeros((2, 1))
    r = Shue1998Omni().radius(theta, theta, _T0 + np.array([[0.0], [3600.0]]))
    assert r[1, 0] == pytest.approx(r[0, 0] * 4 ** (-1 / 6.6))


def test_a_time_without_solar_wind_drops_its_section(fetches):
    fetches(_omni(lambda t: np.where(t < _T0 + 1800, 2.0, np.nan), 0.0))
    times = _T0 + np.array([0.0, 7200.0])
    sections = Shue1998Omni().cross_section(Plane(np.tile([0, 0, 1.0], (2, 1)), np.zeros(2)), times)
    assert np.isfinite(sections[0]).any() and np.isnan(sections[1]).all()


def test_driven_models_are_registered_next_to_the_nominal_ones():
    names = {m.name for m in MODELS}
    assert {"shue1998", "shue1998_omni", "jelinek2012", "jelinek2012_omni"} <= names
