"""Integration tests for the layer system (pure logic, no Qt)."""
from SciQLop.user_api.layers.types import Marker, Span, HLine
from SciQLop.user_api.layers.registry import LayerRegistry


def test_register_and_invoke_marker_layer():
    reg = LayerRegistry()

    def find_peaks(start: float, stop: float, threshold: float = 0.5) -> list[Marker]:
        mid = (start + stop) / 2
        return [Marker(time=mid, value=threshold)]

    entry = reg.register("find_peaks", find_peaks)
    result = entry.wrapper(0.0, 100.0)
    assert len(result) == 1
    assert isinstance(result[0], Marker)
    assert result[0].time == 50.0
    assert result[0].value == 0.5


def test_register_and_invoke_span_layer():
    reg = LayerRegistry()

    def detect_intervals(start: float, stop: float) -> list[Span]:
        mid = (start + stop) / 2
        return [Span(start=mid - 1, stop=mid + 1, label="event")]

    entry = reg.register("detect_intervals", detect_intervals)
    result = entry.wrapper(0.0, 100.0)
    assert len(result) == 1
    assert isinstance(result[0], Span)
    assert result[0].label == "event"


def test_register_and_invoke_mixed_layer():
    reg = LayerRegistry()

    def annotate(start: float, stop: float) -> list[Marker | Span | HLine]:
        return [
            Marker(time=start, value=1.0),
            Span(start=start, stop=stop),
            HLine(value=0.0),
        ]

    entry = reg.register("annotate", annotate)
    result = entry.wrapper(0.0, 10.0)
    assert len(result) == 3
    assert isinstance(result[0], Marker)
    assert isinstance(result[1], Span)
    assert isinstance(result[2], HLine)


def test_hot_reload_swaps_callback():
    reg = LayerRegistry()

    def v1(start, stop):
        return [Marker(time=0, value=1)]

    def v2(start, stop):
        return [Marker(time=0, value=2)]

    entry = reg.register("layer", v1)
    assert entry.wrapper(0, 1)[0].value == 1

    entry2 = reg.register("layer", v2)
    assert entry2.wrapper(0, 1)[0].value == 2
    # same wrapper object (hot-reloaded)
    assert entry.wrapper is entry2.wrapper


def test_partition_end_to_end():
    from SciQLop.user_api.layers._renderer import _partition

    items = [
        Marker(time=1, value=2),
        Span(start=0, stop=5),
        HLine(value=3),
        Marker(time=2, value=4),
    ]
    groups = _partition(items)
    assert len(groups["marker"]) == 2
    assert len(groups["span"]) == 1
    assert len(groups["hline"]) == 1


def test_knob_extraction_from_layer_callback():
    from SciQLop.user_api.knobs import extract_specs_from_callback
    from SciQLop.user_api.knobs.specs import FloatKnob, IntKnob

    def detector(start: float, stop: float, threshold: float = 0.5, window: int = 10):
        return []

    specs = extract_specs_from_callback(detector)
    assert len(specs) == 2
    names = {s.name for s in specs}
    assert names == {"threshold", "window"}
    threshold = next(s for s in specs if s.name == "threshold")
    assert isinstance(threshold, FloatKnob)
    assert threshold.default == 0.5
    window = next(s for s in specs if s.name == "window")
    assert isinstance(window, IntKnob)
    assert window.default == 10
