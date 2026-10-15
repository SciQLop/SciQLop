import pytest
from SciQLop.user_api.layers.types import Marker
from ..fixtures import *  # noqa: F401,F403


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


def test_signature_kwargs_skips_the_named_parameters():
    from SciQLop.user_api.layers.registry import signature_kwargs

    def f(start, stop, data=None, threshold: float = 0.5):
        return []

    assert signature_kwargs(f) == (("threshold", float),)
    assert signature_kwargs(f, skip=("start", "stop")) == (("data", type(None)), ("threshold", float))


@pytest.fixture
def define(main_window):
    from SciQLop.user_api.layers._provider import LAYERS, define_layer, follow_layers
    follow_layers()
    yield define_layer
    for key in LAYERS.keys():
        if key.startswith("Layers/lr/"):
            LAYERS.remove(key)


class TestDefineLayer:
    def test_define_new(self, define):
        provider = define("lr/find_peaks", _peaks_a)
        assert provider.callback(0.0, 1000.0)[0].time == 100.0

    def test_redefine_same_sig_swaps(self, define):
        wrapper1 = define("lr/find_peaks", _peaks_a).callback
        provider = define("lr/find_peaks", _peaks_b)
        assert provider.callback is wrapper1
        assert provider.callback(0.0, 1000.0)[0].time == 200.0

    def test_redefine_different_sig_rebuilds(self, define):
        wrapper1 = define("lr/find_peaks", _peaks_a).callback
        provider = define("lr/find_peaks", _peaks_new_sig)
        assert provider.callback is not wrapper1
        assert "window" in {k.name for k in provider.get_knobs()}

    def test_lookup_by_path(self, define):
        from SciQLop.user_api.layers._provider import LAYERS
        provider = define("lr/find_peaks", _peaks_a)
        assert LAYERS.get("Layers/lr/find_peaks") is provider
        assert "Layers/lr/nonexistent" not in LAYERS
