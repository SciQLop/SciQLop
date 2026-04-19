from typing import Annotated, Literal

import numpy as np
import pytest
from pydantic import BaseModel, Field

from SciQLop.user_api.knobs import Knob, IntKnob, ChoiceKnob


@pytest.fixture(autouse=True)
def _isolate_products(qapp, monkeypatch):
    from SciQLop.core.models import products
    monkeypatch.setattr(products, "add_node", lambda *a, **k: None)


def _make_easy_scalar(callback, knobs_model=None):
    from SciQLop.components.plotting.backend.easy_provider import EasyScalar
    return EasyScalar(path=f"vp/{id(callback):x}",
                      get_data_callback=callback,
                      component_name="x",
                      metadata={},
                      knobs_model=knobs_model)


def test_easyprovider_get_knobs_from_callback_kwargs():
    def f(start: float, stop: float,
          fft: Annotated[int, Knob(min=64, max=4096, step=64)] = 256,
          window: Literal["hann", "hamming"] = "hann"):
        n = 8
        return np.linspace(start, stop, n), np.zeros(n)
    p = _make_easy_scalar(f)
    specs = p.get_knobs("any")
    by_name = {s.name: s for s in specs}
    assert isinstance(by_name["fft"], IntKnob)
    assert isinstance(by_name["window"], ChoiceKnob)


def test_easyprovider_dispatches_kwargs_to_callback():
    seen = {}

    def f(start: float, stop: float,
          fft: Annotated[int, Knob(min=64, max=4096)] = 256):
        seen["fft"] = fft
        n = 4
        return np.linspace(start, stop, n), np.zeros(n)

    p = _make_easy_scalar(f)
    p.get_data(product=None, start=0.0, stop=1.0, knobs={"fft": 1024})
    assert seen["fft"] == 1024


def test_easyprovider_no_knobs_kwarg_is_byte_identical():
    seen = {}

    def f(start: float, stop: float):
        seen["called"] = True
        n = 4
        return np.linspace(start, stop, n), np.zeros(n)

    p = _make_easy_scalar(f)
    p.get_data(product=None, start=0.0, stop=1.0)
    assert seen["called"]


def test_easyprovider_pydantic_model_dispatch():
    class K(BaseModel):
        fft: int = Field(256, ge=64, le=4096)
        thr: float = Field(0.5, ge=0.0, le=1.0)

    seen = {}

    def f(start: float, stop: float, knobs: K) -> None:
        seen["fft"] = knobs.fft
        seen["thr"] = knobs.thr
        n = 4
        return np.linspace(start, stop, n), np.zeros(n)

    p = _make_easy_scalar(f, knobs_model=K)
    p.get_data(product=None, start=0.0, stop=1.0,
               knobs={"fft": 1024, "thr": 0.7})
    assert seen == {"fft": 1024, "thr": 0.7}
