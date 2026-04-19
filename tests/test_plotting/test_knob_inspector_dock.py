from types import SimpleNamespace

from SciQLop.user_api.knobs import IntKnob
from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
from SciQLop.components.plotting.ui.knob_inspector.dock import KnobInspectorDock
from SciQLop.components.plotting.ui.knob_inspector.section import KnobsSection


def test_dock_shows_placeholder_when_empty(qtbot):
    dock = KnobInspectorDock()
    qtbot.addWidget(dock)
    assert dock.current_section() is None


def test_set_graph_without_state_shows_no_params_message(qtbot):
    dock = KnobInspectorDock()
    qtbot.addWidget(dock)
    graph = SimpleNamespace()
    dock.set_graph(graph)
    assert dock.current_section() is None


def test_set_graph_mounts_section_when_state_present(qtbot):
    dock = KnobInspectorDock()
    qtbot.addWidget(dock)
    state = GraphKnobState([IntKnob(name="fft", default=256, min=64, max=4096)])
    graph = SimpleNamespace(_knob_state=state)
    dock.set_graph(graph)
    section = dock.current_section()
    assert isinstance(section, KnobsSection)
    assert section.widget_for("fft") is not None


def test_set_graph_replaces_previous_section(qtbot):
    dock = KnobInspectorDock()
    qtbot.addWidget(dock)
    state_a = GraphKnobState([IntKnob(name="a", default=1, min=0, max=10)])
    state_b = GraphKnobState([IntKnob(name="b", default=2, min=0, max=10)])
    dock.set_graph(SimpleNamespace(_knob_state=state_a))
    first = dock.current_section()
    dock.set_graph(SimpleNamespace(_knob_state=state_b))
    second = dock.current_section()
    assert second is not first
    assert second.widget_for("b") is not None
    assert second.widget_for("a") is None
