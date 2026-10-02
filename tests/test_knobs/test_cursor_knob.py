"""Tests for CursorKnob — a draggable vertical line holding one time value."""

from typing import Annotated

import pytest
from SciQLopPlots import SciQLopPlotRange

from SciQLop.user_api.knobs import (
    Knob, CursorKnob, extract_specs_from_callback, coerce_value, defaults_for,
)


def test_cursor_knob_defaults():
    k = CursorKnob(name="t")
    assert k.widget == "vline"
    assert k.default == pytest.approx(0.5)


def test_introspection_vline_marker_gives_cursor_knob():
    def f(start, stop,
          t: Annotated[float, Knob(widget="vline", color="#00ff00", label="At")] = 0.25):
        pass
    [spec] = extract_specs_from_callback(f)
    assert isinstance(spec, CursorKnob)
    assert spec.default == pytest.approx(0.25)
    assert spec.color == "#00ff00"
    assert spec.label == "At"


def test_introspection_carries_cursor_scope():
    def f(start, stop,
          a: Annotated[float, Knob(widget="vline")] = 0.5,
          b: Annotated[float, Knob(widget="vline", scope="plot")] = 0.5):
        pass
    by_name = {s.name: s for s in extract_specs_from_callback(f)}
    assert by_name["a"].scope == "panel"
    assert by_name["b"].scope == "plot"


def test_coerce_cursor_to_float():
    spec = CursorKnob(name="t")
    assert coerce_value(spec, "12.5") == pytest.approx(12.5)
    assert defaults_for([spec]) == {"t": 0.5}


def test_cursor_knob_json_round_trip():
    from SciQLop.user_api.knobs import spec_to_dict, spec_from_dict
    spec = CursorKnob(name="t", default=0.3, color="#123456", label="At")
    assert spec_from_dict(spec_to_dict(spec)) == spec


def test_cursor_delegate_shows_time(qtbot):
    from SciQLop.components.plotting.ui.knob_inspector.delegates import delegate_for_spec
    d = delegate_for_spec(CursorKnob(name="t"))
    qtbot.addWidget(d)
    d.set_value(0.0)
    assert d.get_value() == pytest.approx(0.0)
    assert "1970-01-01" in d._label.text()


@pytest.fixture
def sciqlop_panel(qtbot):
    from SciQLopPlots import SciQLopMultiPlotPanel, PlotType
    panel = SciQLopMultiPlotPanel(synchronize_x=False, synchronize_time=True)
    panel.resize(800, 600)
    qtbot.addWidget(panel)
    panel.set_time_axis_range(SciQLopPlotRange(100.0, 200.0))
    panel.create_plot(0, PlotType.TimeSeries)
    qtbot.wait(50)
    return panel


@pytest.fixture
def sciqlop_plot(sciqlop_panel):
    return sciqlop_panel.plots()[0]


def _cursor(plot, default):
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.components.plotting.ui.knob_inspector.plot_items import _DataCursor
    spec = CursorKnob(name="t", default=default)
    state = GraphKnobState([spec])
    return _DataCursor(plot, spec, state), state


def test_fractional_default_resolves_against_view(sciqlop_plot, qtbot):
    cursor, state = _cursor(sciqlop_plot, 0.3)
    assert state.values["t"] == pytest.approx(130.0)
    assert cursor._line.position == pytest.approx(130.0)
    cursor.cleanup()


def test_fractional_cursor_follows_pan(sciqlop_panel, sciqlop_plot, qtbot):
    cursor, state = _cursor(sciqlop_plot, 0.5)
    sciqlop_panel.set_time_axis_range(SciQLopPlotRange(1000.0, 1100.0))
    qtbot.waitUntil(lambda: state.values["t"] == pytest.approx(1050.0), timeout=1000)
    cursor.cleanup()


def test_dragged_cursor_keeps_its_place_in_view(sciqlop_panel, sciqlop_plot, qtbot):
    cursor, state = _cursor(sciqlop_plot, 0.5)
    cursor._line.set_position(190.0)
    qtbot.waitUntil(lambda: state.values["t"] == pytest.approx(190.0), timeout=1000)
    sciqlop_panel.set_time_axis_range(SciQLopPlotRange(1000.0, 1100.0))
    qtbot.waitUntil(lambda: state.values["t"] == pytest.approx(1090.0), timeout=1000)
    cursor.cleanup()


def test_absolute_default_never_moves(sciqlop_panel, sciqlop_plot, qtbot):
    cursor, state = _cursor(sciqlop_plot, 150.0)
    sciqlop_panel.set_time_axis_range(SciQLopPlotRange(120.0, 220.0))
    qtbot.wait(50)
    assert state.values["t"] == pytest.approx(150.0)
    cursor.cleanup()


def test_cursor_syncs_from_state(sciqlop_plot, qtbot):
    cursor, _ = _cursor(sciqlop_plot, 150.0)
    cursor.update_from_state({"t": 170.0})
    assert cursor._line.position == pytest.approx(170.0)
    cursor.cleanup()


def test_create_plot_items_wires_cursor(sciqlop_plot, qtbot):
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.components.plotting.ui.knob_inspector.plot_items import create_plot_items
    state = GraphKnobState([CursorKnob(name="t", default=150.0)])
    dispose = create_plot_items(sciqlop_plot, state)
    state.set_value("t", 160.0)
    assert state.values["t"] == pytest.approx(160.0)
    dispose()
