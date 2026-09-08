"""``plot_product(..., product_inputs={...})`` seeds the graph's knob values
instead of leaking into the SciQLopPlots call (which rejects the keyword)."""
import pytest
from PySide6.QtCore import QObject

from SciQLop.core.knobs import ChoiceKnob, IntKnob
from SciQLop.components.plotting.ui import time_sync_panel as tsp


class _Graph(QObject):
    def __init__(self):
        super().__init__()
        self.setObjectName("g0")
        self.calls = []

    def set_name(self, n): self.setObjectName(n)

    def name(self): return self.objectName()


class _Plot(QObject):
    def __init__(self):
        super().__init__()
        self.setObjectName("plot0")


class _Provider:
    name = "Fake"

    def __init__(self, specs):
        self._specs = specs

    def get_knobs(self, node): return self._specs

    def labels(self, node): return ["x"]


class _Node:
    def name(self): return "prod"

    def display_name(self): return "prod"

    def provider(self): return "Fake"

    def parameter_type(self):
        from SciQLop.core.enums import ParameterType
        return ParameterType.Scalar

    def metadata(self, key=None): return {}


class _Target:
    def __init__(self):
        self.kwargs = None
        self.graph = _Graph()
        self.plot = _Plot()

    def plots(self): return [self.plot]

    def windowTitle(self): return "T"

    def __call__(self, *a, **kw): raise AssertionError

    def plot_(self, callback, **kwargs):
        self.kwargs = kwargs
        return (self.plot, self.graph)


@pytest.fixture
def wiring(monkeypatch):
    specs = [ChoiceKnob(name="coordinate_frame", label="f", default="J2000",
                        choices=(("J2000", "J2000"), ("GSE", "GSE"))),
             IntKnob(name="level", label="l", default=1)]
    provider = _Provider(specs)
    monkeypatch.setattr(tsp.ProductsModel, "node", staticmethod(lambda path: _Node()))
    monkeypatch.setattr(tsp, "providers", {"Fake": provider})
    monkeypatch.setattr(tsp, "_set_product_path", lambda *a, **k: None)
    monkeypatch.setattr(tsp, "_register_graph_hints", lambda *a, **k: None)
    monkeypatch.setattr(tsp, "_attach_graph_context", lambda *a, **k: None)
    monkeypatch.setattr(tsp, "_trigger_refetch", lambda graph: graph.calls.append("refetch"))
    import SciQLop.components.plotting.backend.remote.registry as reg
    monkeypatch.setattr(reg, "remote_registry", lambda: type("R", (), {"is_remote": lambda self, p: False})())
    target = _Target()
    target.plot = target.plot_  # SciQLopPlots-style .plot(callback, **kwargs)
    return target


def test_product_inputs_seed_knob_values_and_stay_out_of_the_plot_call(qtbot, wiring):
    target = wiring
    plot, graph = tsp.plot_product(target, ["root", "Fake", "prod"],
                                   product_inputs={"coordinate_frame": "GSE"})
    assert "product_inputs" not in target.kwargs
    assert graph._knob_state.values == {"coordinate_frame": "GSE", "level": 1}
    assert graph.calls == ["refetch"]


def test_product_inputs_absent_keeps_defaults_without_refetch(qtbot, wiring):
    target = wiring
    plot, graph = tsp.plot_product(target, ["root", "Fake", "prod"])
    assert graph._knob_state.values == {"coordinate_frame": "J2000", "level": 1}
    assert graph.calls == []


def test_unknown_product_input_is_dropped(qtbot, wiring):
    target = wiring
    plot, graph = tsp.plot_product(target, ["root", "Fake", "prod"],
                                   product_inputs={"nope": 3, "level": "7"})
    assert graph._knob_state.values == {"coordinate_frame": "J2000", "level": 7}
