from dataclasses import asdict


def test_marker_defaults():
    from SciQLop.user_api.layers.types import Marker
    m = Marker(time=1.0, value=2.0)
    assert m.time == 1.0
    assert m.value == 2.0
    assert m.label is None
    assert m.color is None
    assert m.meta == {}


def test_marker_with_metadata():
    from SciQLop.user_api.layers.types import Marker
    m = Marker(time=1.0, value=2.0, label="peak", color="#ff0000", meta={"confidence": 0.9})
    assert m.label == "peak"
    assert m.color == "#ff0000"
    assert m.meta["confidence"] == 0.9


def test_span_defaults():
    from SciQLop.user_api.layers.types import Span
    s = Span(start=1.0, stop=2.0)
    assert s.start == 1.0
    assert s.stop == 2.0
    assert s.label is None
    assert s.color is None
    assert s.meta == {}


def test_span_with_metadata():
    from SciQLop.user_api.layers.types import Span
    s = Span(start=1.0, stop=2.0, label="event", color="#00ff00", meta={"type": "dipolarization"})
    assert s.label == "event"


def test_hline_defaults():
    from SciQLop.user_api.layers.types import HLine
    h = HLine(value=3.14)
    assert h.value == 3.14
    assert h.label is None
    assert h.color is None


def test_hline_with_metadata():
    from SciQLop.user_api.layers.types import HLine
    h = HLine(value=0.0, label="zero crossing", color="#0000ff")
    assert h.label == "zero crossing"


def test_infer_annotation_type_markers():
    from SciQLop.user_api.layers.types import Marker, infer_annotation_type
    items = [Marker(time=1.0, value=2.0), Marker(time=3.0, value=4.0)]
    assert infer_annotation_type(items) == "marker"


def test_infer_annotation_type_spans():
    from SciQLop.user_api.layers.types import Span, infer_annotation_type
    items = [Span(start=1.0, stop=2.0)]
    assert infer_annotation_type(items) == "span"


def test_infer_annotation_type_hlines():
    from SciQLop.user_api.layers.types import HLine, infer_annotation_type
    items = [HLine(value=1.0)]
    assert infer_annotation_type(items) == "hline"


def test_infer_annotation_type_mixed():
    from SciQLop.user_api.layers.types import Marker, Span, infer_annotation_type
    items = [Marker(time=1.0, value=2.0), Span(start=1.0, stop=2.0)]
    assert infer_annotation_type(items) == "mixed"


def test_infer_annotation_type_empty():
    from SciQLop.user_api.layers.types import infer_annotation_type
    assert infer_annotation_type([]) is None


def test_infer_type_from_return_annotation():
    from SciQLop.user_api.layers.types import Marker, Span, HLine, infer_type_from_annotation
    assert infer_type_from_annotation(list[Marker]) == "marker"
    assert infer_type_from_annotation(list[Span]) == "span"
    assert infer_type_from_annotation(list[HLine]) == "hline"
    assert infer_type_from_annotation(list[Marker | Span]) == "mixed"
    assert infer_type_from_annotation(None) is None
    assert infer_type_from_annotation(int) is None
