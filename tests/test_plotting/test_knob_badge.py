from SciQLop.user_api.knobs import IntKnob, ChoiceKnob, FloatKnob
from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
from SciQLop.components.plotting.ui.knob_inspector.badge import (
    KnobBadge, format_summary,
)


SPECS = [
    IntKnob(name="fft", default=256),
    ChoiceKnob(name="win", default="hann",
               choices=(("Hann", "hann"), ("Hamming", "hamming"))),
    FloatKnob(name="thr", default=0.5),
]


def test_format_summary_short():
    assert format_summary({"fft": 256, "win": "hann", "thr": 0.5}) == \
        "fft=256 | win=hann | thr=0.50"


def test_format_summary_handles_missing_state():
    assert format_summary({}) == ""


def test_badge_updates_on_state_change(qtbot):
    state = GraphKnobState(SPECS)
    b = KnobBadge(state)
    qtbot.addWidget(b)
    assert b.summary_text() == format_summary(state.values)
    state.set_value("fft", 1024)
    assert b.summary_text() == format_summary(state.values)


def test_badge_clicked_emits(qtbot):
    state = GraphKnobState(SPECS)
    b = KnobBadge(state)
    qtbot.addWidget(b)
    received = []
    b.clicked.connect(lambda: received.append(True))
    b.clicked.emit()
    assert received == [True]
