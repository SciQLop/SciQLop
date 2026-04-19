from typing import Annotated

import numpy as np
import pytest

from SciQLop.user_api.knobs import Knob, IntKnob


@pytest.fixture(autouse=True)
def _isolate_products(qapp, monkeypatch):
    from SciQLop.core.models import products
    monkeypatch.setattr(products, "add_node", lambda *a, **k: None)


def test_plot_product_callback_passes_knobs():
    from SciQLop.components.plotting.backend.easy_provider import EasyScalar
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.components.plotting.ui.time_sync_panel import _plot_product_callback

    seen = {}

    def f(start: float, stop: float,
          fft: Annotated[int, Knob(min=64, max=4096)] = 256):
        seen["fft"] = fft
        n = 4
        return np.linspace(start, stop, n), np.zeros(n)

    p = EasyScalar(path="vp/test", get_data_callback=f, component_name="x", metadata={})
    state = GraphKnobState([IntKnob(name="fft", default=256, min=64, max=4096)])
    state.set_value("fft", 1024)

    cb = _plot_product_callback(provider=p, node=None, knob_state=state)
    cb(0.0, 1.0)
    assert seen["fft"] == 1024


def test_plot_product_callback_without_state_calls_unchanged():
    from SciQLop.components.plotting.backend.easy_provider import EasyScalar
    from SciQLop.components.plotting.ui.time_sync_panel import _plot_product_callback

    seen = {}

    def f(start: float, stop: float):
        seen["called"] = True
        n = 4
        return np.linspace(start, stop, n), np.zeros(n)

    p = EasyScalar(path="vp/test2", get_data_callback=f, component_name="x", metadata={})
    cb = _plot_product_callback(provider=p, node=None)
    cb(0.0, 1.0)
    assert seen["called"]
