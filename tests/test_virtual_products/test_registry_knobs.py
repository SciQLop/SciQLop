from typing import Annotated

import pytest

from SciQLop.user_api.knobs import Knob


@pytest.fixture(autouse=True)
def _isolate_products(qapp, monkeypatch):
    from SciQLop.core.models import products
    monkeypatch.setattr(products, "add_node", lambda *a, **k: None)


def test_mutablecallback_forwards_kwargs():
    from SciQLop.user_api.virtual_products.registry import MutableCallback
    seen = {}

    def f(start, stop, fft: Annotated[int, Knob(min=64)] = 256):
        seen["fft"] = fft
        return None

    cb = MutableCallback(f)
    cb(0.0, 1.0, fft=1024)
    assert seen["fft"] == 1024


def test_mutablecallback_after_call_still_invoked():
    from SciQLop.user_api.virtual_products.registry import MutableCallback
    received = {}

    def f(start, stop, fft: int = 256):
        return ("ok", fft)

    cb = MutableCallback(f)
    cb.after_call = lambda r, e, start, stop: received.update(
        result=r, elapsed=e, start=start, stop=stop)
    cb(0.0, 1.0, fft=128)
    assert received["result"] == ("ok", 128)
    assert received["elapsed"] >= 0
    assert received["start"] == 0.0
    assert received["stop"] == 1.0


def test_registry_marks_signature_changed_when_knob_added():
    from SciQLop.user_api.virtual_products.registry import VPRegistry

    reg = VPRegistry()

    def f1(start, stop): ...
    def f2(start, stop, fft: int = 256): ...

    e1 = reg.register("p", f1, "scalar", ["x"])
    assert e1.signature_changed is False

    e2 = reg.register("p", f2, "scalar", ["x"])
    assert e2.signature_changed is True


def test_registry_keeps_signature_when_only_body_changes():
    from SciQLop.user_api.virtual_products.registry import VPRegistry

    reg = VPRegistry()

    def f1(start, stop, fft: int = 256):
        return None

    def f2(start, stop, fft: int = 256):
        return [1, 2]

    reg.register("p", f1, "scalar", ["x"])
    e2 = reg.register("p", f2, "scalar", ["x"])
    assert e2.signature_changed is False
