"""A product plotted with ``plot_type=Projection`` must actually draw.

`plot_product` hands the graph whatever the provider returns: for a vector
product that is two buffers -- a time array and an (N, k) values array. A
projection plot reads its buffers by *count* (time plus one per subplot), so
two matched nothing, `set_data` rejected it, and the plot stayed empty. The
callback is now reshaped into ``[t, d0 .. dk-1]``.
"""
import numpy as np
import pytest

from SciQLop.components.plotting.ui.time_sync_panel import _projection_shaped_callback


def test_a_vector_product_is_split_into_one_buffer_per_dimension():
    t = np.linspace(0.0, 10.0, 20)
    values = np.random.rand(20, 3)
    shaped = _projection_shaped_callback(lambda a, b: (t, values))(0.0, 10.0)
    assert len(shaped) == 4, "expected time plus one buffer per component"
    assert np.array_equal(shaped[0], t)
    for i in range(3):
        assert np.array_equal(shaped[i + 1], values[:, i])


def test_an_already_shaped_result_is_passed_through():
    payload = [np.arange(5.0)] * 4
    assert _projection_shaped_callback(lambda a, b: payload)(0.0, 1.0) is payload


def test_none_is_passed_through():
    assert _projection_shaped_callback(lambda a, b: None)(0.0, 1.0) is None


def test_a_scalar_product_cannot_be_projected():
    """1-D values have nothing to project; better None than a silent empty plot."""
    t = np.linspace(0.0, 1.0, 5)
    got = _projection_shaped_callback(lambda a, b: (t, np.arange(5.0)))(0.0, 1.0)
    assert got is None


def test_attributes_of_the_wrapped_callback_stay_reachable():
    """plot_product sets on_data_fetched on the callback after wrapping it."""

    class Inner:
        on_data_fetched = None
        node = "some/product"

        def __call__(self, a, b):
            return None

    assert _projection_shaped_callback(Inner()).node == "some/product"
