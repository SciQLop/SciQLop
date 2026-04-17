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
from SciQLop.user_api.virtual_products.validation import (
    validate_and_call, validate_with_data, ValidationResult, Diagnostic,
)


def _scalar_callback(start, stop):
    x = np.linspace(start, stop, 100)
    return x, np.sin(x)


def _raising_callback(start, stop):
    raise ValueError("test error")


# ---------------------------------------------------------------------------
# Basic validation
# ---------------------------------------------------------------------------

def test_validate_success_scalar():
    result = validate_and_call(_scalar_callback, 0.0, 10.0, "scalar", ["v"])
    assert result.data is not None
    assert not any(d.level == "error" for d in result.diagnostics)
    assert result.elapsed > 0


def test_validate_exception():
    result = validate_and_call(_raising_callback, 0.0, 10.0, "scalar", ["v"])
    assert result.data is None
    assert len(result.diagnostics) == 1
    assert result.diagnostics[0].level == "error"
    assert "ValueError" in result.diagnostics[0].message


def test_validate_none_returned():
    result = validate_and_call(lambda s, e: None, 0.0, 10.0, "scalar", ["v"])
    assert result.data is None
    assert any(d.level == "warning" and "No data" in d.message for d in result.diagnostics)


# ---------------------------------------------------------------------------
# Return type checks
# ---------------------------------------------------------------------------

def test_wrong_return_type_dict():
    result = validate_with_data({"x": [1, 2]}, "scalar", ["v"])
    assert any(d.level == "error" and "SpeasyVariable" in d.message for d in result.diagnostics)


def test_wrong_return_type_single_array():
    result = validate_with_data(np.array([1, 2, 3]), "scalar", ["v"])
    assert any(d.level == "error" and "SpeasyVariable" in d.message for d in result.diagnostics)


def test_tuple_too_short():
    result = validate_with_data((np.array([1, 2]),), "scalar", ["v"])
    assert any(d.level == "error" and "Expected (x, y)" in d.message for d in result.diagnostics)


def test_spectrogram_tuple_too_short():
    x = np.linspace(0, 10, 50)
    result = validate_with_data((x, np.sin(x)), "spectrogram", None)
    assert any(d.level == "error" and "Spectrogram requires (x, y, z)" in d.message
               for d in result.diagnostics)


# ---------------------------------------------------------------------------
# Empty data
# ---------------------------------------------------------------------------

def test_empty_arrays_warning():
    result = validate_with_data((np.array([]), np.array([])), "scalar", ["v"])
    assert any(d.level == "warning" and "0 data points" in d.message for d in result.diagnostics)


# ---------------------------------------------------------------------------
# Time/values length mismatch
# ---------------------------------------------------------------------------

def test_time_values_length_mismatch():
    x = np.linspace(0, 10, 100)
    y = np.sin(np.linspace(0, 10, 50))  # wrong length
    result = validate_with_data((x, y), "scalar", ["v"])
    assert any(d.level == "error" and "length" in d.message for d in result.diagnostics)


def test_spectrogram_z_shape_mismatch():
    x = np.linspace(0, 10, 50)
    y = np.linspace(0, 100, 20)
    z = np.random.randn(50, 10)  # cols should be 20
    result = validate_with_data((x, y, z), "spectrogram", None)
    assert any(d.level == "error" and "z" in d.message.lower() for d in result.diagnostics)


# ---------------------------------------------------------------------------
# Time dtype
# ---------------------------------------------------------------------------

def test_time_dtype_float32_warning():
    x = np.linspace(0, 10, 100).astype(np.float32)
    result = validate_with_data((x, np.sin(x.astype(np.float64))), "scalar", ["v"])
    assert any(d.level == "warning" and "float64" in d.message for d in result.diagnostics)


def test_time_dtype_int64_warning():
    x = np.arange(100, dtype=np.int64)
    result = validate_with_data((x, np.sin(x.astype(np.float64))), "scalar", ["v"])
    assert any(d.level == "warning" and "float64" in d.message for d in result.diagnostics)


def test_time_dtype_float64_ok():
    x = np.linspace(0, 10, 100)
    result = validate_with_data((x, np.sin(x)), "scalar", ["v"])
    assert not any("Time vector dtype" in d.message for d in result.diagnostics)


def test_time_dtype_datetime64ns_ok():
    x = np.arange('2020-01-01', '2020-01-02', dtype='datetime64[h]').astype('datetime64[ns]')
    result = validate_with_data((x, np.random.randn(len(x))), "scalar", ["v"])
    assert not any("Time vector dtype" in d.message for d in result.diagnostics)


# ---------------------------------------------------------------------------
# Time NaN/Inf
# ---------------------------------------------------------------------------

def test_time_nan_error():
    x = np.linspace(0, 10, 100)
    x[50] = np.nan
    result = validate_with_data((x, np.sin(x)), "scalar", ["v"])
    assert any(d.level == "error" and "NaN" in d.message for d in result.diagnostics)


def test_time_inf_error():
    x = np.linspace(0, 10, 100)
    x[0] = np.inf
    result = validate_with_data((x, np.sin(x)), "scalar", ["v"])
    assert any(d.level == "error" and "Inf" in d.message for d in result.diagnostics)


# ---------------------------------------------------------------------------
# Shape mismatch (existing)
# ---------------------------------------------------------------------------

def test_validate_shape_mismatch_vector():
    x = np.linspace(0, 10, 100)
    result = validate_and_call(
        lambda s, e: (x, np.column_stack([np.sin(x)] * 5)),
        0.0, 10.0, "vector", ["X", "Y", "Z"])
    assert any(d.level == "error" and "shape" in d.message.lower() for d in result.diagnostics)


# ---------------------------------------------------------------------------
# Spectrogram shape
# ---------------------------------------------------------------------------

def test_spectrogram_z_not_2d():
    x = np.linspace(0, 10, 50)
    y = np.linspace(0, 100, 20)
    z = np.random.randn(50 * 20)  # 1D instead of 2D
    result = validate_with_data((x, y, z), "spectrogram", None)
    assert any(d.level == "error" and "2D" in d.message for d in result.diagnostics)


def test_spectrogram_valid():
    x = np.linspace(0, 10, 50)
    y = np.linspace(0, 100, 20)
    z = np.random.randn(50, 20)
    result = validate_with_data((x, y, z), "spectrogram", None)
    assert not any(d.level == "error" for d in result.diagnostics)


# ---------------------------------------------------------------------------
# Value dtype
# ---------------------------------------------------------------------------

def test_validate_dtype_float32_warning():
    def float32_callback(start, stop):
        x = np.linspace(start, stop, 100)
        return x, np.sin(x).astype(np.float32)

    result = validate_and_call(float32_callback, 0.0, 10.0, "scalar", ["v"])
    assert result.data is not None
    warnings = [d for d in result.diagnostics if d.level == "warning" and "float32" in d.message]
    assert len(warnings) == 1


# ---------------------------------------------------------------------------
# Time coverage
# ---------------------------------------------------------------------------

def test_time_coverage_ok():
    x = np.linspace(0.0, 10.0, 100)
    result = validate_with_data((x, np.sin(x)), "scalar", ["v"], start=0.0, stop=10.0)
    assert not any(d.level == "error" for d in result.diagnostics)
    assert not any("starts" in d.message or "ends" in d.message or "outside" in d.message
                   for d in result.diagnostics)


def test_time_completely_outside_requested_range():
    x = np.linspace(100.0, 200.0, 100)
    result = validate_with_data((x, np.sin(x)), "scalar", ["v"], start=0.0, stop=10.0)
    assert any(d.level == "error" and "outside" in d.message.lower() for d in result.diagnostics)


def test_time_partial_coverage_late_start():
    x = np.linspace(5.0, 10.0, 50)
    result = validate_with_data((x, np.sin(x)), "scalar", ["v"], start=0.0, stop=10.0)
    assert any("starts" in d.message and "50%" in d.message for d in result.diagnostics)


def test_time_partial_coverage_early_stop():
    x = np.linspace(0.0, 4.0, 50)
    result = validate_with_data((x, np.sin(x)), "scalar", ["v"], start=0.0, stop=10.0)
    assert any("ends" in d.message and "60%" in d.message for d in result.diagnostics)


def test_time_not_monotonic():
    x = np.array([0.0, 5.0, 3.0, 10.0])
    result = validate_with_data((x, np.sin(x)), "scalar", ["v"], start=0.0, stop=10.0)
    assert any("monotonic" in d.message.lower() for d in result.diagnostics)


def test_time_small_gap_no_warning():
    x = np.linspace(0.2, 9.8, 100)
    result = validate_with_data((x, np.sin(x)), "scalar", ["v"], start=0.0, stop=10.0)
    assert not any("starts" in d.message or "ends" in d.message for d in result.diagnostics)


def test_no_time_check_without_start_stop():
    x = np.linspace(100.0, 200.0, 100)
    result = validate_with_data((x, np.sin(x)), "scalar", ["v"])
    assert not any("outside" in d.message.lower() for d in result.diagnostics)


# ---------------------------------------------------------------------------
# Execution time
# ---------------------------------------------------------------------------

def test_slow_callback_warning():
    """Callback taking >10% of the requested duration triggers a warning."""
    x = np.linspace(0.0, 10.0, 100)
    # elapsed=5s for a 10s range = 50% → should warn
    result = validate_with_data((x, np.sin(x)), "scalar", ["v"],
                                elapsed=5.0, start=0.0, stop=10.0)
    assert any("pan/zoom" in d.message for d in result.diagnostics)


def test_fast_callback_no_warning():
    x = np.linspace(0.0, 86400.0, 100)
    # elapsed=0.01s for a 1-day range → should not warn
    result = validate_with_data((x, np.sin(x)), "scalar", ["v"],
                                elapsed=0.01, start=0.0, stop=86400.0)
    assert not any("pan/zoom" in d.message for d in result.diagnostics)


def test_slow_callback_no_range():
    """Without start/stop, fall back to absolute threshold (>5s)."""
    x = np.linspace(0.0, 10.0, 100)
    result = validate_with_data((x, np.sin(x)), "scalar", ["v"], elapsed=6.0)
    assert any("pan/zoom" in d.message for d in result.diagnostics)
