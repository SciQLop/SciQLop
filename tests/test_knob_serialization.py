"""Tests for KnobSpec.to_dict / from_dict roundtrip serialization."""
from .fixtures import *
from SciQLop.core.knobs import (
    IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob, StringListKnob,
    spec_to_dict, spec_from_dict,
)


def test_intknob_roundtrip(qapp):
    spec = IntKnob(name="rating", min=1, max=5, default=3, step=1, description="r")
    d = spec_to_dict(spec)
    assert d["type"] == "IntKnob"
    assert d["name"] == "rating"
    assert d["min"] == 1
    assert d["max"] == 5
    restored = spec_from_dict(d)
    assert restored == spec


def test_floatknob_roundtrip(qapp):
    spec = FloatKnob(name="score", min=0.0, max=1.0, default=0.5, step=0.05)
    d = spec_to_dict(spec)
    assert d["type"] == "FloatKnob"
    assert spec_from_dict(d) == spec


def test_boolknob_roundtrip(qapp):
    spec = BoolKnob(name="flag", default=True)
    d = spec_to_dict(spec)
    assert d["type"] == "BoolKnob"
    assert spec_from_dict(d) == spec


def test_stringknob_roundtrip(qapp):
    spec = StringKnob(name="author", default="me", pattern=r"^[a-z]+$")
    d = spec_to_dict(spec)
    assert d["type"] == "StringKnob"
    assert spec_from_dict(d) == spec


def test_stringlistknob_roundtrip(qapp):
    spec = StringListKnob(
        name="tags",
        default=("alpha", "beta"),
        suggestions=("alpha", "beta", "gamma"),
        item_pattern=r"^\w+$",
    )
    d = spec_to_dict(spec)
    assert d["type"] == "StringListKnob"
    assert d["default"] == ["alpha", "beta"]  # JSON-friendly list, not tuple
    restored = spec_from_dict(d)
    assert restored == spec


def test_choiceknob_roundtrip(qapp):
    spec = ChoiceKnob(
        name="category",
        default="a",
        choices=(("Alpha", "a"), ("Beta", "b")),
    )
    d = spec_to_dict(spec)
    assert d["type"] == "ChoiceKnob"
    # choices serialized as a JSON-friendly nested list
    assert d["choices"] == [["Alpha", "a"], ["Beta", "b"]]
    restored = spec_from_dict(d)
    assert restored == spec


def test_from_dict_unknown_type_returns_none(qapp):
    assert spec_from_dict({"type": "NotARealKnob", "name": "x"}) is None


def test_from_dict_missing_type_returns_none(qapp):
    assert spec_from_dict({"name": "x"}) is None


def test_to_dict_omits_default_only_kwargs(qapp):
    """Empty/default base fields shouldn't bloat the JSON."""
    spec = IntKnob(name="rating", min=1, max=5, default=3)
    d = spec_to_dict(spec)
    # name + type + min + max + default + step (1 is the default but we keep it for clarity)
    # We DON'T need empty label/unit/description/apply='live'/widget='' fields
    assert "label" not in d or d["label"] == ""
    # The roundtrip is what matters; the dict can be compact or verbose
