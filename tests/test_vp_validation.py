# tests/test_vp_validation.py
"""Tests for virtual product validation pipeline.

We pre-register the validation module to avoid importing the heavy
virtual_products __init__.py which requires a running Qt application.
"""
import sys
import importlib.util

_spec = importlib.util.spec_from_file_location(
    "SciQLop.user_api.virtual_products.validation",
    "SciQLop/user_api/virtual_products/validation.py",
    submodule_search_locations=[],
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

import pytest
import numpy as np
from SciQLop.user_api.virtual_products.validation import validate_and_call, ValidationResult, Diagnostic


def _scalar_callback(start, stop):
    x = np.linspace(start, stop, 100)
    return x, np.sin(x)


def _bad_shape_callback(start, stop):
    x = np.linspace(start, stop, 100)
    return x, np.column_stack([np.sin(x)] * 5)


def _raising_callback(start, stop):
    raise ValueError("test error")


def _none_callback(start, stop):
    return None


def test_validate_success_scalar():
    result = validate_and_call(_scalar_callback, 0.0, 10.0, "scalar", ["v"])
    assert result.data is not None
    assert len(result.diagnostics) == 0
    assert result.elapsed > 0


def test_validate_exception():
    result = validate_and_call(_raising_callback, 0.0, 10.0, "scalar", ["v"])
    assert result.data is None
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].level == "error"
    assert "ValueError" in result.diagnostics[0].message
    assert "test error" in result.diagnostics[0].message


def test_validate_none_returned():
    result = validate_and_call(_none_callback, 0.0, 10.0, "scalar", ["v"])
    assert result.data is None
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].level == "warning"


def test_validate_shape_mismatch_vector():
    result = validate_and_call(_bad_shape_callback, 0.0, 10.0, "vector", ["X", "Y", "Z"])
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].level == "error"
    assert "shape" in result.diagnostics[0].message.lower()


def test_validate_dtype_coercion():
    def float32_callback(start, stop):
        x = np.linspace(start, stop, 100)
        return x, np.sin(x).astype(np.float32)

    result = validate_and_call(float32_callback, 0.0, 10.0, "scalar", ["v"])
    assert result.data is not None
    # Should have a warning about dtype conversion
    warnings = [d for d in result.diagnostics if d.level == "warning"]
    assert len(warnings) == 1
    assert "float32" in warnings[0].message
