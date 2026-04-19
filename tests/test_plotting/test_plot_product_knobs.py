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


def test_attach_knob_state_creates_badge_when_plot_resolvable(qapp, tmp_path, monkeypatch):
    from types import SimpleNamespace
    from PySide6.QtWidgets import QWidget
    from SciQLop.components.plotting.ui import time_sync_panel as tsp
    from SciQLop.components.plotting.ui.time_sync_panel import _attach_knob_state
    from SciQLop.components.plotting.ui.knob_inspector.badge import KnobBadge
    from SciQLop.components.settings.backend import entry as entry_mod

    monkeypatch.setattr(entry_mod, "SCIQLOP_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(tsp, "_show_knob_hint", lambda parent: None)

    plot = QWidget()
    graph = QWidget(parent=plot)

    class _Prov:
        def get_knobs(self, _p):
            return [IntKnob(name="fft", default=256, min=64, max=4096)]

    callback = SimpleNamespace(knob_state=None)
    _attach_knob_state(_Prov(), "p", callback, (plot, graph), None)

    assert hasattr(graph, "_knob_state")
    assert isinstance(getattr(graph, "_knob_badge", None), KnobBadge)


def test_attach_knob_state_no_badge_when_plot_none(qapp, tmp_path, monkeypatch):
    from types import SimpleNamespace
    from PySide6.QtWidgets import QWidget
    from SciQLop.components.plotting.ui import time_sync_panel as tsp
    from SciQLop.components.plotting.ui.time_sync_panel import _attach_knob_state
    from SciQLop.components.settings.backend import entry as entry_mod

    monkeypatch.setattr(entry_mod, "SCIQLOP_CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(tsp, "_show_knob_hint", lambda parent: None)

    graph = QWidget()

    class _Prov:
        def get_knobs(self, _p):
            return [IntKnob(name="fft", default=256, min=64, max=4096)]

    callback = SimpleNamespace(knob_state=None)
    _attach_knob_state(_Prov(), "p", callback, graph, None)

    assert hasattr(graph, "_knob_state")
    assert not hasattr(graph, "_knob_badge")
