"""A provider returning a zero-width component array (e.g. ``values[:, 4:3]``
yields shape ``(N, 0)``) must NOT reach the C++ ``set_data``: the row-major
multi data source asserts ``stride > 0`` and aborts the whole process.
``_get_data`` is the single Python choke point that has to reject it.
"""
import numpy as np

from SciQLop.components.plotting.backend.data_provider import DataProvider


class _ReturnsTuple(DataProvider):
    def __init__(self, value):
        super().__init__(name="returns-tuple")
        self._value = value

    def get_data(self, product, start, stop, knobs=None):
        return self._value


def test_zero_width_component_tuple_is_rejected():
    t = np.arange(10, dtype=np.float64)
    degenerate = (t, np.empty((10, 0), dtype=np.float32))  # the broken-VP shape
    p = _ReturnsTuple(degenerate)
    assert p._get_data("prod", 0.0, 1.0) == []


def test_valid_vector_tuple_passes_through():
    t = np.arange(10, dtype=np.float64)
    valid = (t, np.zeros((10, 3), dtype=np.float64))
    p = _ReturnsTuple(valid)
    out = p._get_data("prod", 0.0, 1.0)
    assert out is valid


def test_empty_time_vector_tuple_passes_through():
    t = np.empty((0,), dtype=np.float64)
    empty = (t, np.empty((0, 3), dtype=np.float64))  # rows=0 is valid for the C++ source
    p = _ReturnsTuple(empty)
    out = p._get_data("prod", 0.0, 1.0)
    assert out is empty
