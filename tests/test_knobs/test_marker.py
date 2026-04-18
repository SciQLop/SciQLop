from typing import Annotated, get_type_hints, get_args

from SciQLop.user_api.knobs.marker import Knob


def test_knob_marker_carries_metadata():
    m = Knob(min=0, max=10, step=2, label="Threshold",
             unit="V", description="d", apply="manual",
             choices=(("Hann", "hann"),), pattern=r"^x$")
    assert m.min == 0 and m.max == 10 and m.step == 2
    assert m.label == "Threshold" and m.unit == "V"
    assert m.description == "d" and m.apply == "manual"
    assert m.choices == (("Hann", "hann"),)
    assert m.pattern == r"^x$"


def test_knob_defaults_are_none_or_empty():
    m = Knob()
    assert m.min is None and m.max is None and m.step is None
    assert m.label == "" and m.unit == "" and m.description == ""
    assert m.apply == "live"
    assert m.choices is None and m.pattern == ""


def test_knob_survives_annotated_round_trip():
    def f(x: Annotated[int, Knob(min=0, max=5, label="X")] = 1) -> None: ...
    hints = get_type_hints(f, include_extras=True)
    args = get_args(hints["x"])
    assert args[0] is int
    marker = next(a for a in args[1:] if isinstance(a, Knob))
    assert marker.min == 0 and marker.max == 5 and marker.label == "X"
