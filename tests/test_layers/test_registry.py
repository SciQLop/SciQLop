import numpy as np
import pytest
from SciQLop.user_api.layers.types import Marker


def _peaks_a(start: float, stop: float, threshold: float = 0.5):
    return [Marker(time=start + 100, value=1.0)]


def _peaks_b(start: float, stop: float, threshold: float = 0.5):
    return [Marker(time=start + 200, value=2.0)]


def _peaks_new_sig(start: float, stop: float, threshold: float = 0.5, window: int = 10):
    return [Marker(time=start + 100, value=1.0)]


class TestMutableCallback:
    def test_calls_wrapped(self):
        from SciQLop.user_api.layers.registry import MutableCallback
        w = MutableCallback(_peaks_a)
        result = w(0.0, 1000.0)
        assert len(result) == 1
        assert result[0].time == 100.0

    def test_swap_callback(self):
        from SciQLop.user_api.layers.registry import MutableCallback
        w = MutableCallback(_peaks_a)
        w.callback = _peaks_b
        result = w(0.0, 1000.0)
        assert result[0].time == 200.0

    def test_annotations_recoverable_after_wrapping(self):
        """Python 3.14 (PEP 749) doesn't expose __annotations__ as a plain
        attribute on instances wrapped with functools.update_wrapper. Callers
        must reach the underlying function via inspect.unwrap to read return
        type hints; this test pins that contract so the layer/VP type-inference
        paths keep working under 3.14."""
        import inspect
        from SciQLop.user_api.layers.registry import MutableCallback

        def annotated(start: float, stop: float) -> list:
            return []

        w = MutableCallback(annotated)
        target = inspect.unwrap(w)
        ann = inspect.get_annotations(target)
        assert ann.get("return") is list


class TestLayerRegistry:
    def test_register_new(self):
        from SciQLop.user_api.layers.registry import LayerRegistry
        reg = LayerRegistry()
        entry = reg.register("find_peaks", _peaks_a)
        assert entry.wrapper(0.0, 1000.0)[0].time == 100.0
        assert entry.signature_changed is False

    def test_re_register_same_sig_swaps(self):
        from SciQLop.user_api.layers.registry import LayerRegistry
        reg = LayerRegistry()
        entry1 = reg.register("find_peaks", _peaks_a)
        wrapper1 = entry1.wrapper
        entry2 = reg.register("find_peaks", _peaks_b)
        assert entry2.wrapper is wrapper1
        assert entry2.signature_changed is False
        assert entry2.wrapper(0.0, 1000.0)[0].time == 200.0

    def test_re_register_different_sig_rebuilds(self):
        from SciQLop.user_api.layers.registry import LayerRegistry
        reg = LayerRegistry()
        entry1 = reg.register("find_peaks", _peaks_a)
        entry2 = reg.register("find_peaks", _peaks_new_sig)
        assert entry2.wrapper is not entry1.wrapper
        assert entry2.signature_changed is True

    def test_get_existing(self):
        from SciQLop.user_api.layers.registry import LayerRegistry
        reg = LayerRegistry()
        reg.register("find_peaks", _peaks_a)
        assert reg.get("find_peaks") is not None
        assert reg.get("nonexistent") is None
