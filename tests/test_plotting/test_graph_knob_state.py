import pytest

from SciQLop.user_api.knobs import IntKnob, ChoiceKnob
from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState


SPECS = [
    IntKnob(name="fft", default=256, min=64, max=4096, step=64),
    ChoiceKnob(name="win", default="hann",
               choices=(("Hann", "hann"), ("Hamming", "hamming"))),
]


def test_state_initializes_with_defaults():
    s = GraphKnobState(SPECS)
    assert s.values == {"fft": 256, "win": "hann"}


def test_set_value_validates_and_signals(qtbot):
    s = GraphKnobState(SPECS)
    received = []
    s.knobs_changed.connect(lambda d: received.append(dict(d)))
    s.set_value("fft", "1024")
    assert s.values["fft"] == 1024
    assert received[-1]["fft"] == 1024


def test_set_value_invalid_keeps_old(qtbot):
    s = GraphKnobState(SPECS)
    with pytest.raises(ValueError):
        s.set_value("win", "rect")
    assert s.values["win"] == "hann"


def test_bulk_set_load_rules():
    s = GraphKnobState(SPECS)
    s.set_all({"fft": 128, "removed": 99})
    assert s.values == {"fft": 128, "win": "hann"}


def test_replace_specs_migrates_values():
    s = GraphKnobState(SPECS)
    s.set_value("fft", 1024)
    new_specs = [
        IntKnob(name="fft", default=256, min=64, max=4096, step=64),
        IntKnob(name="overlap", default=8, min=0, max=64),
    ]
    s.replace_specs(new_specs)
    assert s.values == {"fft": 1024, "overlap": 8}
