from typing import Annotated

import numpy as np
import pytest

from SciQLop.user_api.knobs import Knob, IntKnob


def test_attach_knob_state_populates_graph_and_callback(qapp):
    from SciQLop.components.plotting.backend.easy_provider import EasyScalar
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.components.plotting.ui.time_sync_panel import (
        _attach_knob_state,
        _plot_product_callback,
    )
    from PySide6.QtCore import QObject

    def f(start: float, stop: float,
          fft: Annotated[int, Knob(min=64, max=4096)] = 256):
        n = 4
        return np.linspace(start, stop, n), np.zeros(n)

    provider = EasyScalar(path="vp/knobtest", get_data_callback=f, component_name="x", metadata={})
    graph = QObject()
    callback = _plot_product_callback(provider=provider, node=None)

    _attach_knob_state(provider, "vp/knobtest", callback, graph)

    state = getattr(graph, "_knob_state", None)
    assert state is not None
    assert state.values == {"fft": 256}
    assert callback.knob_state is state


def test_attach_knob_state_no_op_for_no_knobs(qapp):
    from SciQLop.components.plotting.backend.easy_provider import EasyScalar
    from SciQLop.components.plotting.ui.time_sync_panel import (
        _attach_knob_state,
        _plot_product_callback,
    )
    from PySide6.QtCore import QObject

    def f(start: float, stop: float):
        n = 4
        return np.linspace(start, stop, n), np.zeros(n)

    provider = EasyScalar(path="vp/noknobs", get_data_callback=f, component_name="x", metadata={})
    graph = QObject()
    callback = _plot_product_callback(provider=provider, node=None)

    _attach_knob_state(provider, "vp/noknobs", callback, graph)

    assert not hasattr(graph, "_knob_state")
    assert callback.knob_state is None


def test_attach_knob_state_knobs_changed_signal_fires(qapp, qtbot):
    from SciQLop.components.plotting.backend.easy_provider import EasyScalar
    from SciQLop.components.plotting.ui.time_sync_panel import (
        _attach_knob_state,
        _plot_product_callback,
    )
    from PySide6.QtCore import QObject

    def f(start: float, stop: float,
          fft: Annotated[int, Knob(min=64, max=4096)] = 256):
        n = 4
        return np.linspace(start, stop, n), np.zeros(n)

    provider = EasyScalar(path="vp/signaltest", get_data_callback=f, component_name="x", metadata={})
    graph = QObject()
    callback = _plot_product_callback(provider=provider, node=None)

    _attach_knob_state(provider, "vp/signaltest", callback, graph)

    state = graph._knob_state
    fired = []
    state.knobs_changed.connect(lambda d: fired.append(d))
    state.set_value("fft", 512)
    assert fired == [{"fft": 512}]
