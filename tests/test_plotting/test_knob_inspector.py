from SciQLop.user_api.knobs import IntKnob, ChoiceKnob
from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
from SciQLop.components.plotting.ui.knob_inspector.section import KnobsSection


SPECS = [
    IntKnob(name="fft", default=256, min=64, max=4096, step=64),
    ChoiceKnob(name="win", default="hann",
               choices=(("Hann", "hann"), ("Hamming", "hamming"))),
]


def test_section_renders_one_widget_per_spec(qtbot):
    state = GraphKnobState(SPECS)
    sec = KnobsSection(state)
    qtbot.addWidget(sec)
    assert sec.widget_for("fft") is not None
    assert sec.widget_for("win") is not None


def test_widget_change_debounces_into_state(qtbot, monkeypatch):
    state = GraphKnobState(SPECS)
    sec = KnobsSection(state, debounce_ms=10)
    qtbot.addWidget(sec)
    sec.widget_for("fft").set_value(1024)
    sec.widget_for("fft").value_changed.emit(1024)
    qtbot.wait(50)
    assert state.values["fft"] == 1024


def test_state_change_resyncs_widget_without_loop(qtbot):
    state = GraphKnobState(SPECS)
    sec = KnobsSection(state, debounce_ms=10)
    qtbot.addWidget(sec)
    state.set_value("fft", 512)
    assert sec.widget_for("fft").get_value() == 512


def test_reset_button_restores_defaults(qtbot):
    state = GraphKnobState(SPECS)
    state.set_value("fft", 1024)
    sec = KnobsSection(state, debounce_ms=10)
    qtbot.addWidget(sec)
    sec.reset_to_defaults()
    qtbot.wait(50)
    assert state.values["fft"] == 256


def test_manual_apply_knob_skips_debouncer(qtbot):
    spec_manual = IntKnob(name="fft", default=256, min=64, max=4096,
                          step=64, apply="manual")
    state = GraphKnobState([spec_manual])
    sec = KnobsSection(state, debounce_ms=2000)
    qtbot.addWidget(sec)
    sec.widget_for("fft").set_value(1024)
    sec.widget_for("fft").value_changed.emit(1024)
    assert state.values["fft"] == 256
    sec.apply_manual()
    assert state.values["fft"] == 1024
