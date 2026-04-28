"""Tests for data-aware layer callbacks (pure logic, no Qt)."""
from SciQLop.user_api.data_types import Scalar, Vector, Spectrogram
from SciQLop.user_api.layers.types import Marker, Span, HLine


def test_range_only_callback_has_no_data_type():
    from SciQLop.user_api.layers._introspection import extract_data_type

    def my_layer(start: float, stop: float, threshold: float = 0.5):
        return []

    assert extract_data_type(my_layer) is None


def test_data_aware_callback_with_vector_hint():
    from SciQLop.user_api.layers._introspection import extract_data_type

    def my_layer(data: Vector, threshold: float = 0.5):
        return []

    info = extract_data_type(my_layer)
    assert info is not None
    assert info.product_type == "vector"
    assert info.labels is None


def test_data_aware_callback_with_scalar_hint():
    from SciQLop.user_api.layers._introspection import extract_data_type

    def my_layer(data: Scalar):
        return []

    info = extract_data_type(my_layer)
    assert info is not None
    assert info.product_type == "scalar"


def test_data_aware_callback_with_spectrogram_hint():
    from SciQLop.user_api.layers._introspection import extract_data_type

    def my_layer(data: Spectrogram):
        return []

    info = extract_data_type(my_layer)
    assert info is not None
    assert info.product_type == "spectrogram"


def test_data_aware_callback_untyped_data_param():
    from SciQLop.user_api.layers._introspection import extract_data_type

    def my_layer(data):
        return []

    info = extract_data_type(my_layer)
    assert info is not None
    assert info.product_type == "any"


def test_data_param_not_treated_as_knob():
    from SciQLop.user_api.knobs import extract_specs_from_callback

    def my_layer(data: Vector, threshold: float = 0.5):
        return []

    specs = extract_specs_from_callback(my_layer)
    names = {s.name for s in specs}
    assert "data" not in names
    assert "threshold" in names


def test_mutable_callback_forwards_data_kwarg():
    from SciQLop.user_api.layers.registry import MutableCallback
    import numpy as np

    received = {}

    def my_layer(data: Vector, level: float = 1.0):
        received["data"] = data
        received["level"] = level
        return [HLine(value=level)]

    wrapper = MutableCallback(my_layer)
    fake_data = Vector(time=np.arange(5.0), values=np.ones((5, 3)))
    result = wrapper(data=fake_data, level=5.0)
    assert isinstance(received["data"], Vector)
    assert received["data"].time is fake_data.time
    assert received["level"] == 5.0
    assert len(result) == 1
    assert result[0].value == 5.0
