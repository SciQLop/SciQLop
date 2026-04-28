"""Tests for data type annotations (shared by virtual products and layers)."""
from SciQLop.user_api.data_types import (
    Scalar, Vector, MultiComponent, Spectrogram, VPTypeInfo, extract_vp_type_info,
)


def test_scalar_no_label():
    info = extract_vp_type_info(Scalar)
    assert info.product_type == "scalar"
    assert info.labels is None


def test_scalar_with_label():
    info = extract_vp_type_info(Scalar["Temperature"])
    assert info.product_type == "scalar"
    assert info.labels == ["Temperature"]


def test_vector_no_labels():
    info = extract_vp_type_info(Vector)
    assert info.product_type == "vector"
    assert info.labels is None


def test_vector_with_labels():
    info = extract_vp_type_info(Vector["Bx", "By", "Bz"])
    assert info.product_type == "vector"
    assert info.labels == ["Bx", "By", "Bz"]


def test_multicomponent_with_labels():
    info = extract_vp_type_info(MultiComponent["E1", "E2", "E3", "E4"])
    assert info.product_type == "multicomponent"
    assert info.labels == ["E1", "E2", "E3", "E4"]


def test_spectrogram():
    info = extract_vp_type_info(Spectrogram)
    assert info.product_type == "spectrogram"
    assert info.labels is None


def test_extract_from_function_annotation():
    def my_func(start, stop) -> Vector["Bx", "By", "Bz"]:  # noqa: F821
        pass
    info = extract_vp_type_info(my_func.__annotations__["return"])
    assert info.product_type == "vector"
    assert info.labels == ["Bx", "By", "Bz"]


def test_no_annotation_returns_none():
    info = extract_vp_type_info(None)
    assert info is None
