"""Tests for TimeRangeKnob and ThresholdKnob — specs, introspection, values, delegates."""

from typing import Annotated

import pytest
from SciQLopPlots import SciQLopPlotRange

from SciQLop.user_api.knobs import (
    Knob, TimeRangeKnob, ThresholdKnob,
    extract_specs_from_callback, coerce_value, validate_dict,
    canonical_hash, defaults_for,
)


# --- Spec construction ---

def test_time_range_knob_defaults():
    k = TimeRangeKnob(name="window")
    assert k.widget == "vspan"
    assert k.default.start() == pytest.approx(0.25)
    assert k.default.stop() == pytest.approx(0.75)
    assert k.color == "#3498db"


def test_time_range_knob_custom_default():
    k = TimeRangeKnob(name="w", default=SciQLopPlotRange(0.1, 0.9), color="#ff0000")
    assert k.default.start() == pytest.approx(0.1)
    assert k.default.stop() == pytest.approx(0.9)
    assert k.color == "#ff0000"


def test_threshold_knob_defaults():
    k = ThresholdKnob(name="thr", default=5.0)
    assert k.widget == "hline"
    assert k.default == 5.0
    assert k.color == "#e74c3c"


def test_threshold_knob_inherits_float_fields():
    k = ThresholdKnob(name="thr", default=5.0, min=0.0, max=10.0, step=0.5)
    assert k.min == 0.0
    assert k.max == 10.0
    assert k.step == 0.5


def test_threshold_knob_is_frozen():
    import dataclasses
    k = ThresholdKnob(name="t", default=0.0)
    with pytest.raises(dataclasses.FrozenInstanceError):
        k.default = 1.0


# --- Introspection ---

def test_detect_time_range_from_type_hint():
    def f(start, stop, window: SciQLopPlotRange = SciQLopPlotRange(0.2, 0.8)):
        pass
    specs = extract_specs_from_callback(f)
    assert len(specs) == 1
    assert isinstance(specs[0], TimeRangeKnob)
    assert specs[0].default.start() == pytest.approx(0.2)


def test_detect_time_range_from_widget_marker():
    def f(start, stop,
          zone: Annotated[float, Knob(widget="vspan")] = 0.0):
        pass
    specs = extract_specs_from_callback(f)
    assert len(specs) == 1
    assert isinstance(specs[0], TimeRangeKnob)


def test_detect_threshold_from_widget_marker():
    def f(start, stop,
          thr: Annotated[float, Knob(widget="hline", min=0.0, max=10.0)] = 5.0):
        pass
    specs = extract_specs_from_callback(f)
    assert len(specs) == 1
    s = specs[0]
    assert isinstance(s, ThresholdKnob)
    assert s.default == 5.0
    assert s.min == 0.0
    assert s.max == 10.0


def test_detect_threshold_with_custom_color():
    def f(start, stop,
          thr: Annotated[float, Knob(widget="hline", color="#00ff00")] = 1.0):
        pass
    s = extract_specs_from_callback(f)[0]
    assert isinstance(s, ThresholdKnob)
    assert s.color == "#00ff00"


def test_mixed_knob_types_detected():
    def f(start, stop,
          window: SciQLopPlotRange = SciQLopPlotRange(0.3, 0.7),
          threshold: Annotated[float, Knob(widget="hline")] = 5.0,
          fft_size: int = 256):
        pass
    specs = extract_specs_from_callback(f)
    by_name = {s.name: s for s in specs}
    assert isinstance(by_name["window"], TimeRangeKnob)
    assert isinstance(by_name["threshold"], ThresholdKnob)
    from SciQLop.user_api.knobs import IntKnob
    assert isinstance(by_name["fft_size"], IntKnob)


# --- Coercion ---

def test_coerce_time_range_from_plot_range():
    spec = TimeRangeKnob(name="w")
    r = SciQLopPlotRange(1.0, 2.0)
    result = coerce_value(spec, r)
    assert isinstance(result, SciQLopPlotRange)
    assert result.start() == pytest.approx(1.0)
    assert result.stop() == pytest.approx(2.0)


def test_coerce_time_range_from_tuple():
    spec = TimeRangeKnob(name="w")
    result = coerce_value(spec, (3.0, 4.0))
    assert isinstance(result, SciQLopPlotRange)
    assert result.start() == pytest.approx(3.0)


def test_coerce_time_range_from_list():
    spec = TimeRangeKnob(name="w")
    result = coerce_value(spec, [5.0, 6.0])
    assert isinstance(result, SciQLopPlotRange)
    assert result.stop() == pytest.approx(6.0)


def test_coerce_time_range_rejects_wrong_type():
    spec = TimeRangeKnob(name="w")
    with pytest.raises(TypeError):
        coerce_value(spec, "not a range")


def test_coerce_threshold_clamps():
    spec = ThresholdKnob(name="t", default=5.0, min=0.0, max=10.0)
    assert coerce_value(spec, 15.0) == 10.0
    assert coerce_value(spec, -5.0) == 0.0
    assert coerce_value(spec, 7.5) == pytest.approx(7.5)


# --- defaults_for / validate_dict ---

def test_defaults_for_visual_knobs():
    specs = [
        TimeRangeKnob(name="w", default=SciQLopPlotRange(0.2, 0.8)),
        ThresholdKnob(name="t", default=5.0),
    ]
    d = defaults_for(specs)
    assert isinstance(d["w"], SciQLopPlotRange)
    assert d["t"] == 5.0


def test_validate_dict_with_visual_knobs():
    specs = [
        TimeRangeKnob(name="w"),
        ThresholdKnob(name="t", default=5.0, min=0.0, max=10.0),
    ]
    result = validate_dict(specs, {"t": 15.0})
    assert result["t"] == 10.0  # clamped
    assert isinstance(result["w"], SciQLopPlotRange)  # default


# --- Canonical hash ---

def test_canonical_hash_with_time_range():
    h1 = canonical_hash({"w": SciQLopPlotRange(1.0, 2.0)})
    h2 = canonical_hash({"w": SciQLopPlotRange(1.0, 2.0)})
    h3 = canonical_hash({"w": SciQLopPlotRange(1.0, 3.0)})
    assert h1 == h2
    assert h1 != h3


# --- Delegates ---

def test_time_range_delegate_display(qtbot):
    from SciQLop.components.plotting.ui.knob_inspector.delegates import delegate_for_spec
    spec = TimeRangeKnob(name="w", default=SciQLopPlotRange(100.0, 200.0))
    d = delegate_for_spec(spec)
    qtbot.addWidget(d)
    d.set_value(SciQLopPlotRange(100.0, 200.0))
    assert d.get_value().start() == pytest.approx(100.0)
    assert "100.0" in d._label.text()


def test_threshold_delegate_round_trip(qtbot):
    from SciQLop.components.plotting.ui.knob_inspector.delegates import delegate_for_spec
    spec = ThresholdKnob(name="t", default=5.0, min=0.0, max=10.0)
    d = delegate_for_spec(spec)
    qtbot.addWidget(d)
    d.set_value(7.5)
    assert d.get_value() == pytest.approx(7.5)


# --- GraphKnobState ---

def test_graph_knob_state_with_visual_knobs(qtbot):
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    specs = [
        TimeRangeKnob(name="w"),
        ThresholdKnob(name="t", default=5.0),
    ]
    state = GraphKnobState(specs)
    received = []
    state.knobs_changed.connect(lambda d: received.append(dict(d)))

    state.set_value("t", 7.0)
    assert state.values["t"] == 7.0
    assert len(received) == 1

    new_range = SciQLopPlotRange(10.0, 20.0)
    state.set_value("w", new_range)
    assert state.values["w"].start() == pytest.approx(10.0)
    assert len(received) == 2


# --- Plot items integration ---

@pytest.fixture
def sciqlop_plot(qtbot):
    from SciQLopPlots import SciQLopPlot
    plot = SciQLopPlot()
    plot.resize(800, 600)
    plot.show()
    qtbot.addWidget(plot)
    qtbot.waitExposed(plot)
    plot.x_axis().set_range(SciQLopPlotRange(100.0, 200.0))
    qtbot.wait(50)
    return plot


def test_data_span_resolves_fractional_default(sciqlop_plot, qtbot):
    """Fractional default (0.3, 0.7) is converted to data-space using axis range."""
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.components.plotting.ui.knob_inspector.plot_items import _DataSpan

    spec = TimeRangeKnob(name="window", default=SciQLopPlotRange(0.3, 0.7))
    state = GraphKnobState([spec])
    span = _DataSpan(sciqlop_plot, spec, state)

    val = state.values["window"]
    assert isinstance(val, SciQLopPlotRange)
    # axis is 100-200, so 0.3 → 130, 0.7 → 170
    assert val.start() == pytest.approx(130.0)
    assert val.stop() == pytest.approx(170.0)
    span.cleanup()


def test_data_span_resolves_when_axis_range_set_after_construction(sciqlop_plot, qtbot):
    """Reproducer: when the plot's time range is set AFTER the visual knob is created
    (the case in `%%vp --debug`), the span must re-resolve its fractional default
    against the new axis range — otherwise it sits at literal 0.3-0.7 in epoch space
    and is invisible. See MVA tutorial cell."""
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.components.plotting.ui.knob_inspector.plot_items import _DataSpan

    sciqlop_plot.x_axis().set_range(SciQLopPlotRange(0.0, 1.0))
    qtbot.wait(50)

    spec = TimeRangeKnob(name="window", default=SciQLopPlotRange(0.3, 0.7))
    state = GraphKnobState([spec])
    span = _DataSpan(sciqlop_plot, spec, state)

    sciqlop_plot.x_axis().set_range(SciQLopPlotRange(1_447_813_470.0, 1_447_818_240.0))
    qtbot.wait(50)

    val = state.values["window"]
    span_range = span._span.range()
    expected_start = 1_447_813_470.0 + 0.3 * (1_447_818_240.0 - 1_447_813_470.0)
    expected_stop = 1_447_813_470.0 + 0.7 * (1_447_818_240.0 - 1_447_813_470.0)

    assert val.start() == pytest.approx(expected_start)
    assert val.stop() == pytest.approx(expected_stop)
    assert span_range.start() == pytest.approx(expected_start)
    assert span_range.stop() == pytest.approx(expected_stop)
    span.cleanup()


def test_data_span_user_drag_locks_against_axis_changes(sciqlop_plot, qtbot):
    """Once the user drags the span, subsequent axis range changes must NOT
    move it — the span is locked in data coords."""
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.components.plotting.ui.knob_inspector.plot_items import _DataSpan

    spec = TimeRangeKnob(name="window", default=SciQLopPlotRange(0.3, 0.7))
    state = GraphKnobState([spec])
    span = _DataSpan(sciqlop_plot, spec, state)

    span._on_span_dragged(SciQLopPlotRange(150.0, 160.0))
    assert state.values["window"].start() == pytest.approx(150.0)

    sciqlop_plot.x_axis().set_range(SciQLopPlotRange(0.0, 1000.0))
    qtbot.wait(50)

    val = state.values["window"]
    assert val.start() == pytest.approx(150.0)
    assert val.stop() == pytest.approx(160.0)
    span.cleanup()


def test_data_span_drag_updates_state(sciqlop_plot, qtbot):
    """Dragging the span updates the knob state value."""
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.components.plotting.ui.knob_inspector.plot_items import _DataSpan

    spec = TimeRangeKnob(name="window")
    state = GraphKnobState([spec])
    span = _DataSpan(sciqlop_plot, spec, state)

    new_range = SciQLopPlotRange(140.0, 160.0)
    span._on_span_dragged(new_range)
    assert state.values["window"].start() == pytest.approx(140.0)
    assert state.values["window"].stop() == pytest.approx(160.0)
    span.cleanup()


def test_data_span_syncs_from_state(sciqlop_plot, qtbot):
    """update_from_state moves the span to match."""
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.components.plotting.ui.knob_inspector.plot_items import _DataSpan

    spec = TimeRangeKnob(name="window")
    state = GraphKnobState([spec])
    span = _DataSpan(sciqlop_plot, spec, state)

    span.update_from_state({"window": SciQLopPlotRange(110.0, 190.0)})
    r = span._span.range()
    assert r.start() == pytest.approx(110.0)
    assert r.stop() == pytest.approx(190.0)
    span.cleanup()


def test_movable_hline_creates_at_default(sciqlop_plot, qtbot):
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.components.plotting.ui.knob_inspector.plot_items import _MovableHLine

    spec = ThresholdKnob(name="thr", default=5.0, min=0.0, max=10.0)
    state = GraphKnobState([spec])
    hline = _MovableHLine(sciqlop_plot, spec, state)

    assert hline._line.position == pytest.approx(5.0)
    hline.cleanup()


def test_movable_hline_updates_state_on_position_change(sciqlop_plot, qtbot):
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.components.plotting.ui.knob_inspector.plot_items import _MovableHLine

    spec = ThresholdKnob(name="thr", default=5.0, min=0.0, max=10.0)
    state = GraphKnobState([spec])
    hline = _MovableHLine(sciqlop_plot, spec, state)

    hline._line.set_position(7.5)
    qtbot.wait(50)
    assert state.values["thr"] == pytest.approx(7.5)
    hline.cleanup()


def test_movable_hline_syncs_from_state(sciqlop_plot, qtbot):
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.components.plotting.ui.knob_inspector.plot_items import _MovableHLine

    spec = ThresholdKnob(name="thr", default=5.0, min=0.0, max=10.0)
    state = GraphKnobState([spec])
    hline = _MovableHLine(sciqlop_plot, spec, state)

    hline.update_from_state({"thr": 3.0})
    assert hline._line.position == pytest.approx(3.0)
    hline.cleanup()


def test_create_plot_items_wires_both_types(sciqlop_plot, qtbot):
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.components.plotting.ui.knob_inspector.plot_items import (
        create_plot_items, _DataSpan, _MovableHLine,
    )

    specs = [
        TimeRangeKnob(name="window"),
        ThresholdKnob(name="thr", default=5.0),
    ]
    state = GraphKnobState(specs)
    items = create_plot_items(sciqlop_plot, state)

    assert len(items) == 2
    assert isinstance(items[0], _DataSpan)
    assert isinstance(items[1], _MovableHLine)
    for item in items:
        item.cleanup()


def test_resolve_range_defaults_injects_missing_defaults():
    """Fractional SciQLopPlotRange defaults are resolved to absolute values."""
    from SciQLop.user_api.virtual_products.registry import _resolve_range_defaults

    def f(start, stop, window=SciQLopPlotRange(0.3, 0.7), threshold=5.0):
        pass

    resolved = _resolve_range_defaults(f, 100.0, 200.0, {})
    assert "window" in resolved
    assert resolved["window"].start() == pytest.approx(130.0)
    assert resolved["window"].stop() == pytest.approx(170.0)
    assert "threshold" not in resolved


def test_resolve_range_defaults_preserves_explicit_absolute():
    """Absolute SciQLopPlotRange kwargs pass through unchanged."""
    from SciQLop.user_api.virtual_products.registry import _resolve_range_defaults

    def f(start, stop, window=SciQLopPlotRange(0.3, 0.7)):
        pass

    explicit = SciQLopPlotRange(150.0, 180.0)
    resolved = _resolve_range_defaults(f, 100.0, 200.0, {"window": explicit})
    assert resolved["window"].start() == pytest.approx(150.0)
    assert resolved["window"].stop() == pytest.approx(180.0)


def test_create_plot_items_empty_for_non_visual_specs(sciqlop_plot, qtbot):
    from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState
    from SciQLop.components.plotting.ui.knob_inspector.plot_items import create_plot_items
    from SciQLop.user_api.knobs import FloatKnob, IntKnob

    specs = [FloatKnob(name="x", default=1.0), IntKnob(name="n", default=10)]
    state = GraphKnobState(specs)
    items = create_plot_items(sciqlop_plot, state)
    assert items == []
