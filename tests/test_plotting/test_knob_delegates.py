import pytest

from SciQLop.user_api.knobs import (
    IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob,
)
from SciQLop.components.plotting.ui.knob_inspector.delegates import (
    delegate_for_spec, KnobDelegate,
)


def test_int_knob_delegate(qtbot):
    spec = IntKnob(name="fft", default=256, min=64, max=4096, step=64)
    d = delegate_for_spec(spec)
    qtbot.addWidget(d)
    d.set_value(1024)
    assert d.get_value() == 1024


def test_float_knob_delegate(qtbot):
    spec = FloatKnob(name="thr", default=0.5, min=0.0, max=1.0, step=0.01)
    d = delegate_for_spec(spec)
    qtbot.addWidget(d)
    d.set_value(0.75)
    assert d.get_value() == pytest.approx(0.75)


def test_bool_knob_delegate(qtbot):
    spec = BoolKnob(name="cache", default=False)
    d = delegate_for_spec(spec)
    qtbot.addWidget(d)
    d.set_value(True)
    assert d.get_value() is True


def test_choice_knob_delegate(qtbot):
    spec = ChoiceKnob(name="w", default="hann",
                      choices=(("Hann", "hann"), ("Hamming", "hamming")))
    d = delegate_for_spec(spec)
    qtbot.addWidget(d)
    d.set_value("hamming")
    assert d.get_value() == "hamming"


def test_string_knob_delegate(qtbot):
    spec = StringKnob(name="s", default="x", pattern=r"^[a-z]+$")
    d = delegate_for_spec(spec)
    qtbot.addWidget(d)
    d.set_value("abc")
    assert d.get_value() == "abc"


def test_value_changed_signal(qtbot):
    spec = IntKnob(name="x", default=0, min=0, max=10)
    d = delegate_for_spec(spec)
    qtbot.addWidget(d)
    received = []
    d.value_changed.connect(lambda v: received.append(v))
    d.set_value(5)
    d.value_changed.emit(5)
    assert received[-1] == 5
