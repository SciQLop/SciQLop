from datetime import datetime
from typing import Annotated

import numpy as np
import pytest
from speasy.products import SpeasyVariable

from SciQLop.user_api.knobs import Knob
from SciQLop.components.plotting.backend.dependencies import Depends


@pytest.fixture(autouse=True)
def _isolate_products(qapp, monkeypatch):
    from SciQLop.core.models import products
    monkeypatch.setattr(products, "add_node", lambda *a, **k: None)


def _make_scalar(callback, debug=False):
    from SciQLop.components.plotting.backend.easy_provider import EasyScalar
    return EasyScalar(path=f"vp/{id(callback):x}", get_data_callback=callback,
                      component_name="x", metadata={}, debug=debug)


def test_callable_dependency_injected_with_pad():
    seen = {}
    def upstream(start, stop):
        seen["range"] = (start, stop)
        return ("UPSTREAM",)
    def cb(start: float, stop: float,
           b: Annotated[SpeasyVariable, Depends(upstream, pad=5.0)]):
        seen["b"] = b
        return np.array([start, stop]), np.array([0.0, 0.0])
    _make_scalar(cb).get_data(None, 100.0, 200.0)
    assert seen["b"] == ("UPSTREAM",)
    assert seen["range"] == (95.0, 205.0)


def test_path_dependency_resolves_through_provider(monkeypatch):
    from SciQLop.core.models import products
    from SciQLop.components.plotting.backend import data_provider
    captured = {}

    class FakeNode:
        def provider(self):
            return "FakeProv"

    class FakeProv:
        name = "FakeProv"

        def get_data(self, node, start, stop):
            captured["call"] = (start, stop)
            return ("DATA",)

    monkeypatch.setattr(products, "node",
                        lambda path: FakeNode() if path == ["a", "b"] else None)
    monkeypatch.setitem(data_provider.providers, "FakeProv", FakeProv())

    def cb(start: float, stop: float,
           dep: Annotated[SpeasyVariable, Depends("a//b", pad=1.0)]):
        captured["dep"] = dep
        return np.array([start]), np.array([0.0])
    _make_scalar(cb).get_data(None, 10.0, 20.0)
    assert captured["dep"] == ("DATA",)
    assert captured["call"] == (9.0, 21.0)


def test_virtualproduct_dependency():
    from SciQLop.user_api.virtual_products import (
        create_virtual_product, VirtualProductType,
    )
    def upstream_cb(start: float, stop: float):
        return np.array([start, stop]), np.array([1.0, 2.0])
    up = create_virtual_product("up/vp", upstream_cb,
                                VirtualProductType.Scalar, labels=["u"])
    seen = {}
    def cb(start: float, stop: float,
           dep: Annotated[SpeasyVariable, Depends(up)]):
        seen["dep"] = dep
        return np.array([start]), np.array([0.0])
    _make_scalar(cb).get_data(None, 0.0, 10.0)
    assert isinstance(seen["dep"], SpeasyVariable)
    assert np.allclose(seen["dep"].values.flatten(), [1.0, 2.0])


def test_knob_and_dependency_coexist():
    seen = {}
    def upstream(start, stop):
        return ("U",)
    def cb(start: float, stop: float,
           dep: Annotated[SpeasyVariable, Depends(upstream)],
           gain: Annotated[int, Knob(min=1, max=10)] = 2):
        seen["dep"], seen["gain"] = dep, gain
        return np.array([start]), np.array([float(gain)])
    p = _make_scalar(cb)
    assert [s.name for s in p.get_knobs("any")] == ["gain"]
    p.get_data(None, 0.0, 1.0, knobs={"gain": 5})
    assert seen["dep"] == ("U",) and seen["gain"] == 5


def test_start_stop_type_detection_with_dependency():
    seen = {}
    def upstream(start, stop):
        return ("U",)
    def cb(start: datetime, stop: datetime,
           dep: Annotated[SpeasyVariable, Depends(upstream)]):
        seen["types"] = (type(start), type(stop))
        return np.array([0.0]), np.array([0.0])
    _make_scalar(cb).get_data(None, 0.0, 1.0)
    assert seen["types"] == (datetime, datetime)


def test_unresolvable_path_raises(monkeypatch):
    from SciQLop.core.models import products
    monkeypatch.setattr(products, "node", lambda path: None)
    def cb(start: float, stop: float,
           dep: Annotated[SpeasyVariable, Depends("missing//x")]):
        return np.array([start]), np.array([0.0])
    p = _make_scalar(cb)
    with pytest.raises(RuntimeError) as ei:
        p.get_data(None, 0.0, 1.0)
    msg = str(ei.value)
    assert "missing//x" in msg and "dep" in msg


def test_extended_metadata_lists_dependencies():
    def cb(start: float, stop: float,
           dep: Annotated[SpeasyVariable, Depends("a//b", pad=3.0)]):
        return np.array([start]), np.array([0.0])
    md = _make_scalar(cb).extended_metadata(None)
    assert md["dependencies"] == [{"name": "dep", "target": "a//b", "pad": 3.0}]


def test_dependency_none_discards_in_normal_mode(monkeypatch):
    from SciQLop.components.plotting.backend import easy_provider
    debug_calls = []
    monkeypatch.setattr(easy_provider.log, "debug",
                        lambda *a, **k: debug_calls.append(a))

    def upstream(start, stop):
        return None
    called = {"cb": False}
    def cb(start: float, stop: float,
           dep: Annotated[SpeasyVariable, Depends(upstream)]):
        called["cb"] = True
        return np.array([start]), np.array([0.0])

    result = _make_scalar(cb).get_data(None, 0.0, 1.0)
    assert result is None                      # VP yields no data
    assert called["cb"] is False               # callback never invoked
    assert debug_calls, "expected a debug log on discard"
    assert any("dep" in str(arg) for call in debug_calls for arg in call)


def test_dependency_none_raises_in_debug_mode():
    def upstream(start, stop):
        return None
    def cb(start: float, stop: float,
           dep: Annotated[SpeasyVariable, Depends(upstream)]):
        return np.array([start]), np.array([0.0])
    p = _make_scalar(cb, debug=True)
    with pytest.raises(RuntimeError) as ei:
        p.get_data(None, 0.0, 1.0)
    msg = str(ei.value)
    assert "dep" in msg and "no data" in msg
