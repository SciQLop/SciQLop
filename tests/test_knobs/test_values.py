import pytest

from SciQLop.user_api.knobs.specs import (
    IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob,
)
from SciQLop.user_api.knobs.values import (
    coerce_value, validate_dict, canonical_hash, defaults_for,
)


SPECS = [
    IntKnob(name="fft", default=256, min=64, max=4096, step=64),
    FloatKnob(name="thr", default=0.5, min=0.0, max=1.0, step=0.01),
    BoolKnob(name="cache", default=False),
    ChoiceKnob(name="window", default="hann",
               choices=(("Hann", "hann"), ("Hamming", "hamming"))),
    StringKnob(name="label", default="x", pattern=r"^[a-z]+$"),
]


def test_defaults_for():
    assert defaults_for(SPECS) == {
        "fft": 256, "thr": 0.5, "cache": False,
        "window": "hann", "label": "x",
    }


def test_coerce_int_clamps_and_steps():
    spec = IntKnob(name="x", default=0, min=64, max=4096, step=64)
    assert coerce_value(spec, "128") == 128
    assert coerce_value(spec, 5000) == 4096  # clamp high
    assert coerce_value(spec, 10) == 64       # clamp low
    assert coerce_value(spec, 100) == 128     # snap to step (round)


def test_coerce_float_clamps_no_step_snap():
    spec = FloatKnob(name="x", default=0.5, min=0.0, max=1.0, step=0.01)
    assert coerce_value(spec, 1.5) == 1.0
    assert coerce_value(spec, "0.7") == 0.7


def test_coerce_choice_membership():
    spec = ChoiceKnob(name="w", default="hann",
                      choices=(("Hann", "hann"), ("Hamming", "hamming")))
    assert coerce_value(spec, "hamming") == "hamming"
    with pytest.raises(ValueError):
        coerce_value(spec, "rect")


def test_coerce_string_pattern():
    spec = StringKnob(name="s", default="x", pattern=r"^[a-z]+$")
    assert coerce_value(spec, "abc") == "abc"
    with pytest.raises(ValueError):
        coerce_value(spec, "ABC")


def test_coerce_bool():
    spec = BoolKnob(name="b", default=False)
    assert coerce_value(spec, "true") is True
    assert coerce_value(spec, 0) is False
    assert coerce_value(spec, True) is True


def test_validate_dict_load_rules():
    in_values = {"fft": 128, "thr": 0.7, "cache": True,
                 "window": "hamming", "label": "abc",
                 "removed_knob": 42}
    out = validate_dict(SPECS, in_values)
    assert "removed_knob" not in out
    assert out["fft"] == 128
    assert out["thr"] == 0.7


def test_validate_dict_missing_uses_defaults():
    out = validate_dict(SPECS, {"fft": 128})
    assert out == {"fft": 128, "thr": 0.5, "cache": False,
                   "window": "hann", "label": "x"}


def test_validate_dict_invalid_resets_to_default():
    out = validate_dict(SPECS, {"window": "rect"})
    assert out["window"] == "hann"


def test_canonical_hash_stable():
    a = canonical_hash({"a": 1, "b": 2.5})
    b = canonical_hash({"b": 2.5, "a": 1})
    assert a == b


def test_canonical_hash_none_sentinel():
    assert canonical_hash(None) == canonical_hash({})


def test_canonical_hash_float_precision():
    a = canonical_hash({"x": 0.1 + 0.2})
    b = canonical_hash({"x": 0.3})
    assert a == b
