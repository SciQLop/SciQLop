def test_reset_action_resets_state(qtbot):
    from SciQLop.user_api.knobs import IntKnob
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.components.plotting.ui.time_sync_panel import _build_knob_reset_action

    state = GraphKnobState([IntKnob(name="fft", default=256, min=64, max=4096)])
    state.set_value("fft", 1024)
    action = _build_knob_reset_action(state, parent=None)
    action.trigger()
    assert state.values == {"fft": 256}


def test_reset_action_with_multiple_knobs(qtbot):
    from SciQLop.user_api.knobs import IntKnob, ChoiceKnob
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.components.plotting.ui.time_sync_panel import _build_knob_reset_action

    state = GraphKnobState([
        IntKnob(name="fft", default=256, min=64, max=4096),
        ChoiceKnob(name="win", default="hann", choices=(("Hann", "hann"), ("Hamming", "hamming"))),
    ])
    state.set_value("fft", 1024)
    state.set_value("win", "hamming")
    action = _build_knob_reset_action(state, parent=None)
    action.trigger()
    assert state.values == {"fft": 256, "win": "hann"}
