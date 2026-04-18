from SciQLop.user_api.knobs.specs import (
    KnobSpec, IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob,
)


def test_intknob_defaults():
    k = IntKnob(name="fft_size", default=256, min=64, max=4096, step=64,
                label="FFT size", unit="samples")
    assert k.name == "fft_size"
    assert k.default == 256
    assert k.min == 64 and k.max == 4096 and k.step == 64
    assert k.label == "FFT size" and k.unit == "samples"
    assert k.apply == "live"


def test_floatknob_defaults():
    k = FloatKnob(name="thr", default=0.5, min=0.0, max=1.0, step=0.01)
    assert k.default == 0.5 and k.step == 0.01


def test_boolknob_defaults():
    k = BoolKnob(name="cache", default=True)
    assert k.default is True


def test_choiceknob_pairs():
    k = ChoiceKnob(name="window", default="hann",
                   choices=(("Hann", "hann"), ("Hamming", "hamming")))
    assert k.choices[0] == ("Hann", "hann")
    assert k.default == "hann"


def test_stringknob_pattern():
    k = StringKnob(name="label", default="x", pattern=r"^[a-z]+$")
    assert k.pattern == r"^[a-z]+$"


def test_knobspec_is_frozen():
    import dataclasses
    k = IntKnob(name="x", default=0)
    try:
        k.default = 1
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("KnobSpec should be frozen")


def test_apply_field_round_trip():
    k = IntKnob(name="x", default=0, apply="manual")
    assert k.apply == "manual"
