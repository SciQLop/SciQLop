"""A provider that owns the variables it returns (Speasy: a fresh variable per fetch)
gets its datetime64 time converted to epoch seconds in the same buffer, so a fetch of
tens of millions of points does not hold a second time array. A provider that may
hand back a variable it keeps (a virtual product) must get its variable untouched."""
import numpy as np
import pytest
from speasy.core import datetime64_to_epoch, epoch_to_datetime64
from speasy.core.data_containers import DataContainer
from speasy.products import SpeasyVariable, VariableTimeAxis

from SciQLop.components.plotting.backend import data_provider
from SciQLop.components.plotting.backend.data_provider import DataProvider, epoch_in_place


def _variable(n=1000):
    epoch = 1_780_000_000.123456 + np.arange(n) * 1.000003e-3
    data = DataContainer(values=np.arange(n, dtype=np.float64).reshape(-1, 1), name="v")
    return SpeasyVariable(axes=[VariableTimeAxis(values=epoch_to_datetime64(epoch))], values=data)


class _Returns(DataProvider):
    def __init__(self, variable, owns):
        super().__init__(name=f"returns-{owns}", owns_fetched_variables=owns)
        self._variable = variable

    def get_data(self, product, start, stop, knobs=None):
        return self._variable


@pytest.mark.parametrize("n", [0, 1, 7, 1000])
def test_epoch_in_place_matches_speasy_and_reuses_the_buffer(n, monkeypatch):
    monkeypatch.setattr(data_provider, "_EPOCH_CHUNK", 3)
    time = _variable(n).time
    expected = datetime64_to_epoch(time)

    epoch = epoch_in_place(time)

    assert np.array_equal(epoch, expected)
    assert epoch.dtype == np.float64
    assert n == 0 or np.shares_memory(epoch, time)


def test_owning_provider_gets_its_time_converted_in_place():
    v = _variable()
    time_buffer = v.time
    expected = datetime64_to_epoch(time_buffer)

    time, values = _Returns(v, owns=True)._get_data("prod", 0.0, 1.0)

    assert np.array_equal(time, expected)
    assert np.shares_memory(time, time_buffer)


def test_other_providers_keep_their_variable_intact():
    v = _variable()
    before = v.time.copy()

    time, values = _Returns(v, owns=False)._get_data("prod", 0.0, 1.0)

    assert np.array_equal(v.time, before)
    assert not np.shares_memory(time, v.time)


def test_a_non_contiguous_time_falls_back_to_a_copy():
    v = _variable(20)
    strided = v.time[::2]

    epoch = epoch_in_place(strided)

    assert np.array_equal(epoch, datetime64_to_epoch(strided))
