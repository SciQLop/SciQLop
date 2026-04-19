import sys
import types

import pytest

from tests.fixtures import *  # noqa: F401,F403 - provides qapp/sciqlop_resources

from SciQLop.user_api.knobs import (
    IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob,
)

pytestmark = pytest.mark.usefixtures("qapp")


def _install_fake_ipywidgets(monkeypatch):
    fake = types.ModuleType("ipywidgets")

    class _Widget:
        def __init__(self, **kwargs):
            self.__dict__.update(kwargs)
            self._observers = []

        def observe(self, fn, names="value"):
            self._observers.append((fn, names))

        def _fire(self, new):
            old = getattr(self, "value", None)
            self.value = new
            for fn, _ in self._observers:
                fn(types.SimpleNamespace(name="value", old=old, new=new))

    class IntSlider(_Widget):
        pass

    class FloatSlider(_Widget):
        pass

    class Checkbox(_Widget):
        pass

    class Dropdown(_Widget):
        pass

    class Text(_Widget):
        pass

    class HBox(_Widget):
        def __init__(self, children=()):
            super().__init__(children=children)

    fake.IntSlider = IntSlider
    fake.FloatSlider = FloatSlider
    fake.Checkbox = Checkbox
    fake.Dropdown = Dropdown
    fake.Text = Text
    fake.HBox = HBox
    monkeypatch.setitem(sys.modules, "ipywidgets", fake)
    return fake


def test_widget_for_int(monkeypatch):
    fake = _install_fake_ipywidgets(monkeypatch)
    from SciQLop.user_api.virtual_products.ipywidgets_binding import widget_for_spec
    w = widget_for_spec(IntKnob(name="fft", default=256, min=64, max=4096))
    assert isinstance(w, fake.IntSlider)
    assert w.min == 64 and w.max == 4096 and w.value == 256


def test_widget_for_float(monkeypatch):
    fake = _install_fake_ipywidgets(monkeypatch)
    from SciQLop.user_api.virtual_products.ipywidgets_binding import widget_for_spec
    w = widget_for_spec(FloatKnob(name="thr", default=0.5, min=0.0, max=1.0, step=0.01))
    assert isinstance(w, fake.FloatSlider)


def test_widget_for_choice(monkeypatch):
    fake = _install_fake_ipywidgets(monkeypatch)
    from SciQLop.user_api.virtual_products.ipywidgets_binding import widget_for_spec
    w = widget_for_spec(ChoiceKnob(name="win", default="hann",
                                   choices=(("Hann", "hann"), ("Hamming", "hamming"))))
    assert isinstance(w, fake.Dropdown)
    assert w.options == [("Hann", "hann"), ("Hamming", "hamming")]


def test_widget_for_bool(monkeypatch):
    fake = _install_fake_ipywidgets(monkeypatch)
    from SciQLop.user_api.virtual_products.ipywidgets_binding import widget_for_spec
    w = widget_for_spec(BoolKnob(name="cache", default=True))
    assert isinstance(w, fake.Checkbox)
    assert w.value is True


def test_widget_for_string(monkeypatch):
    fake = _install_fake_ipywidgets(monkeypatch)
    from SciQLop.user_api.virtual_products.ipywidgets_binding import widget_for_spec
    w = widget_for_spec(StringKnob(name="s", default="x"))
    assert isinstance(w, fake.Text)


def test_no_ipywidgets_returns_none(monkeypatch):
    monkeypatch.setitem(sys.modules, "ipywidgets", None)
    from SciQLop.user_api.virtual_products import ipywidgets_binding
    monkeypatch.setattr(ipywidgets_binding, "_import_ipywidgets",
                        lambda: None)
    assert ipywidgets_binding.widget_for_spec(IntKnob(name="x", default=0)) is None


def test_bidirectional_binding(qtbot, monkeypatch):
    fake = _install_fake_ipywidgets(monkeypatch)
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.user_api.virtual_products.ipywidgets_binding import (
        bind_state_to_widgets,
    )

    state = GraphKnobState([IntKnob(name="fft", default=256, min=64, max=4096)])
    widget = fake.IntSlider(min=64, max=4096, value=256)
    bind_state_to_widgets(state, {"fft": widget})

    widget._fire(1024)
    assert state.values["fft"] == 1024

    state.set_value("fft", 512)
    assert widget.value == 512
