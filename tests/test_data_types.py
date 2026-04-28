"""Tests for the shared data type module."""
import numpy as np
from SciQLop.user_api.data_types import (
    Scalar, Vector, MultiComponent, Spectrogram,
    _DataType, wrap_graph_data, data_class_for_product_type,
    extract_vp_type_info,
)


class TestDataContainers:
    def test_vector_holds_data(self):
        t = np.arange(10, dtype=np.float64)
        v = np.ones((10, 3), dtype=np.float64)
        d = Vector(time=t, values=v)
        assert isinstance(d, Vector)
        assert isinstance(d, _DataType)
        np.testing.assert_array_equal(d.time, t)
        np.testing.assert_array_equal(d.values, v)

    def test_scalar_holds_data(self):
        t = np.arange(5, dtype=np.float64)
        v = np.sin(t)
        d = Scalar(time=t, values=v)
        assert isinstance(d, Scalar)
        assert len(d) == 5

    def test_len_matches_time_length(self):
        d = Vector(time=np.arange(20.0), values=np.ones((20, 3)))
        assert len(d) == 20

    def test_vector_is_type_hint(self):
        def my_func(data: Vector): pass
        assert my_func.__annotations__["data"] is Vector

    def test_vector_with_labels_is_instance_not_type(self):
        labeled = Vector["Bx", "By", "Bz"]
        assert not isinstance(labeled, type)
        assert labeled.product_type == "vector"
        assert labeled.labels == ["Bx", "By", "Bz"]

    def test_subclass_check(self):
        assert issubclass(Vector, _DataType)
        assert issubclass(Scalar, _DataType)
        assert issubclass(MultiComponent, _DataType)
        assert issubclass(Spectrogram, _DataType)


class TestWrapGraphData:
    def test_wraps_raw_data_into_vector(self):
        raw = [np.arange(10.0), np.ones((10, 3))]
        result = wrap_graph_data(raw, Vector)
        assert isinstance(result, Vector)
        assert len(result) == 10
        assert result.values.shape == (10, 3)

    def test_wraps_raw_data_into_scalar(self):
        raw = [np.arange(5.0), np.sin(np.arange(5.0))]
        result = wrap_graph_data(raw, Scalar)
        assert isinstance(result, Scalar)
        assert len(result) == 5

    def test_returns_none_for_empty(self):
        assert wrap_graph_data(None, Vector) is None
        assert wrap_graph_data([], Vector) is None
        assert wrap_graph_data([np.array([])], Vector) is None

    def test_preserves_array_data(self):
        t = np.array([1.0, 2.0, 3.0])
        v = np.array([[10, 20, 30], [40, 50, 60], [70, 80, 90]], dtype=np.float64)
        result = wrap_graph_data([t, v], Vector)
        np.testing.assert_array_equal(result.time, t)
        np.testing.assert_array_equal(result.values, v)


class TestDataClassForProductType:
    def test_known_types(self):
        assert data_class_for_product_type("scalar") is Scalar
        assert data_class_for_product_type("vector") is Vector
        assert data_class_for_product_type("multicomponent") is MultiComponent
        assert data_class_for_product_type("spectrogram") is Spectrogram

    def test_any_returns_base(self):
        assert data_class_for_product_type("any") is _DataType

    def test_unknown_returns_base(self):
        assert data_class_for_product_type("nonexistent") is _DataType


class TestExtractVPTypeInfo:
    def test_extract_works(self):
        info = extract_vp_type_info(Vector["Bx", "By", "Bz"])
        assert info.product_type == "vector"
        assert info.labels == ["Bx", "By", "Bz"]

    def test_plain_type_gives_no_labels(self):
        info = extract_vp_type_info(Scalar)
        assert info.product_type == "scalar"
        assert info.labels is None
