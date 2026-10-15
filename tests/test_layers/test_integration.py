"""Integration tests for the layer system: define a layer, invoke it, hot-reload it."""
import pytest

from SciQLop.user_api.layers.types import Marker, Span, HLine
from ..fixtures import *  # noqa: F401,F403


@pytest.fixture
def define(main_window):
    from SciQLop.user_api.layers._provider import LAYERS, define_layer, follow_layers
    follow_layers()
    yield define_layer
    for key in LAYERS.keys():
        if key.startswith("Layers/li/"):
            LAYERS.remove(key)


def test_register_and_invoke_marker_layer(define):
    def find_peaks(start: float, stop: float, threshold: float = 0.5) -> list[Marker]:
        mid = (start + stop) / 2
        return [Marker(time=mid, value=threshold)]

    result = define("li/find_peaks", find_peaks).callback(0.0, 100.0)
    assert len(result) == 1
    assert isinstance(result[0], Marker)
    assert result[0].time == 50.0
    assert result[0].value == 0.5


def test_register_and_invoke_span_layer(define):
    def detect_intervals(start: float, stop: float) -> list[Span]:
        mid = (start + stop) / 2
        return [Span(start=mid - 1, stop=mid + 1, label="event")]

    result = define("li/detect_intervals", detect_intervals).callback(0.0, 100.0)
    assert len(result) == 1
    assert isinstance(result[0], Span)
    assert result[0].label == "event"


def test_register_and_invoke_mixed_layer(define):
    def annotate(start: float, stop: float) -> list[Marker | Span | HLine]:
        return [
            Marker(time=start, value=1.0),
            Span(start=start, stop=stop),
            HLine(value=0.0),
        ]

    result = define("li/annotate", annotate).callback(0.0, 10.0)
    assert len(result) == 3
    assert isinstance(result[0], Marker)
    assert isinstance(result[1], Span)
    assert isinstance(result[2], HLine)


def test_hot_reload_swaps_callback(define):
    def v1(start, stop):
        return [Marker(time=0, value=1)]

    def v2(start, stop):
        return [Marker(time=0, value=2)]

    first = define("li/layer", v1)
    wrapper = first.callback
    assert wrapper(0, 1)[0].value == 1

    second = define("li/layer", v2)
    assert second.callback(0, 1)[0].value == 2
    assert second.callback is wrapper


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
