# tests/test_vp_types.py
"""Tests for virtual product type annotations.

We pre-register the types module to avoid importing the heavy
virtual_products __init__.py which requires a running Qt application.
"""
import sys
import importlib.util

# Register types.py directly before importing through the package path,
# so Python never needs to execute virtual_products/__init__.py
_spec = importlib.util.spec_from_file_location(
    "SciQLop.user_api.virtual_products.types",
    "SciQLop/user_api/virtual_products/types.py",
    submodule_search_locations=[],
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

from SciQLop.user_api.virtual_products.types import (
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
    def my_func(start, stop) -> Vector["Bx", "By", "Bz"]:
        pass
    info = extract_vp_type_info(my_func.__annotations__["return"])
    assert info.product_type == "vector"
    assert info.labels == ["Bx", "By", "Bz"]


def test_no_annotation_returns_none():
    info = extract_vp_type_info(None)
    assert info is None
