# tests/test_vp_magic.py
"""Tests for MutableCallback and VPRegistry.

We pre-register magic.py directly to avoid importing the heavy
virtual_products __init__.py which requires a running Qt application.
"""
import sys
import importlib.util

import pytest
import numpy as np

def _load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path, submodule_search_locations=[])
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# Pre-register types module (no Qt deps) before magic.py so its lazy
# imports resolve without pulling in the full virtual_products __init__.py.
_load_module("SciQLop.user_api.virtual_products.types",
             "SciQLop/user_api/virtual_products/types.py")
_load_module("SciQLop.user_api.virtual_products.magic",
             "SciQLop/user_api/virtual_products/magic.py")

from SciQLop.user_api.virtual_products.magic import (
    MutableCallback, VPRegistry, _extract_function, _infer_type_from_data,
    _infer_multicomponent_labels,
)


def _callback_a(start: float, stop: float):
    return np.linspace(start, stop, 10), np.ones(10)


def _callback_b(start: float, stop: float):
    return np.linspace(start, stop, 10), np.zeros(10)


class TestMutableCallback:
    def test_calls_wrapped_callback(self):
        wrapper = MutableCallback(_callback_a)
        x, y = wrapper(0.0, 1.0)
        assert np.all(y == 1.0)

    def test_swap_callback(self):
        wrapper = MutableCallback(_callback_a)
        wrapper.callback = _callback_b
        x, y = wrapper(0.0, 1.0)
        assert np.all(y == 0.0)


class TestVPRegistry:
    def test_register_new(self):
        reg = VPRegistry()
        entry = reg.register("my_func", _callback_a, "scalar", ["v"])
        assert entry.wrapper(0.0, 1.0) is not None
        assert entry.product_type == "scalar"

    def test_re_register_same_signature_swaps_callback(self):
        reg = VPRegistry()
        entry1 = reg.register("my_func", _callback_a, "scalar", ["v"])
        wrapper1 = entry1.wrapper
        entry2 = reg.register("my_func", _callback_b, "scalar", ["v"])
        # Same wrapper object, just swapped callback
        assert entry2.wrapper is wrapper1
        assert entry2.signature_changed is False
        x, y = entry2.wrapper(0.0, 1.0)
        assert np.all(y == 0.0)

    def test_re_register_different_signature_rebuilds(self):
        reg = VPRegistry()
        entry1 = reg.register("my_func", _callback_a, "scalar", ["v"])
        wrapper1 = entry1.wrapper
        entry2 = reg.register("my_func", _callback_b, "vector", ["X", "Y", "Z"])
        # Different wrapper (signature changed)
        assert entry2.wrapper is not wrapper1
        assert entry2.signature_changed is True
        assert entry2.product_type == "vector"


class TestExtractFunction:
    def test_extracts_function_from_cell(self):
        cell = "def foo(start, stop):\n    return start + stop\n"
        ns = {}
        func = _extract_function(cell, ns)
        assert func.__name__ == "foo"
        assert func(1, 2) == 3

    def test_function_sees_user_namespace(self):
        cell = "def bar(start, stop):\n    return MY_VAR + start\n"
        ns = {"MY_VAR": 100}
        func = _extract_function(cell, ns)
        assert func(5, 0) == 105

    def test_function_sees_imports_from_namespace(self):
        import math
        cell = "def use_math(start, stop):\n    return math.pi\n"
        ns = {"math": math}
        func = _extract_function(cell, ns)
        assert func(0, 0) == math.pi


class TestInferType:
    def test_scalar_1d(self):
        data = (np.zeros(10), np.ones(10))
        info = _infer_type_from_data(data)
        assert info.product_type == "scalar"

    def test_vector_3col(self):
        data = (np.zeros(10), np.ones((10, 3)))
        info = _infer_type_from_data(data)
        assert info.product_type == "vector"

    def test_multicomponent_5col(self):
        data = (np.zeros(10), np.ones((10, 5)))
        info = _infer_type_from_data(data)
        assert info.product_type == "multicomponent"


class TestInferMulticomponentLabels:
    def test_from_cached_data(self):
        data = (np.zeros(10), np.ones((10, 4)))
        labels = _infer_multicomponent_labels(data)
        assert labels == ["C0", "C1", "C2", "C3"]

    def test_fallback_when_no_data(self):
        labels = _infer_multicomponent_labels(None)
        assert labels == ["C0"]
