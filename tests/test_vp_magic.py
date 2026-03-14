# tests/test_vp_magic.py
"""Tests for MutableCallback and VPRegistry.

We pre-register magic.py directly to avoid importing the heavy
virtual_products __init__.py which requires a running Qt application.
"""
import sys
import importlib.util

import pytest
import numpy as np

_spec = importlib.util.spec_from_file_location(
    "SciQLop.user_api.virtual_products.magic",
    "SciQLop/user_api/virtual_products/magic.py",
    submodule_search_locations=[],
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _mod
_spec.loader.exec_module(_mod)

from SciQLop.user_api.virtual_products.magic import MutableCallback, VPRegistry


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
