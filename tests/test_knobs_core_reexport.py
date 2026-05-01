"""Verify knobs are accessible both via core (new home) and user_api (re-export shim)."""
from .fixtures import *


def test_core_knobs_exports_all_symbols(qapp):
    from SciQLop.core import knobs as core_knobs
    expected = {
        "Knob", "KnobSpec", "IntKnob", "FloatKnob", "BoolKnob", "ChoiceKnob",
        "StringKnob", "TimeRangeKnob", "ThresholdKnob",
        "coerce_value", "validate_dict", "canonical_hash", "defaults_for",
        "extract_specs_from_callback", "extract_specs_from_model",
    }
    for name in expected:
        assert hasattr(core_knobs, name), f"core.knobs missing {name}"


def test_user_api_knobs_reexports_from_core(qapp):
    from SciQLop.user_api import knobs as user_api_knobs
    from SciQLop.core import knobs as core_knobs
    for name in (
        "Knob", "KnobSpec", "IntKnob", "FloatKnob", "BoolKnob", "ChoiceKnob",
        "StringKnob", "TimeRangeKnob", "ThresholdKnob",
        "coerce_value", "validate_dict", "canonical_hash", "defaults_for",
        "extract_specs_from_callback", "extract_specs_from_model",
    ):
        assert getattr(user_api_knobs, name) is getattr(core_knobs, name), \
            f"{name} mismatch between user_api.knobs and core.knobs (must be the same object)"


def test_intknob_constructor_works_after_move(qapp):
    from SciQLop.core.knobs import IntKnob
    spec = IntKnob(name="n", min=1, max=5, default=3)
    # Just verify the constructor runs and produces a usable object
    assert spec is not None


def test_extract_specs_from_callback_works_after_move(qapp):
    from SciQLop.core.knobs import extract_specs_from_callback
    from SciQLop.core.knobs import IntKnob, Knob
    from typing import Annotated

    def my_vp(start: float, end: float, n: Annotated[int, Knob(IntKnob(name="n", min=1, max=10, default=5))] = 5):
        pass

    specs = extract_specs_from_callback(my_vp)
    assert any(s.name == "n" for s in specs)
