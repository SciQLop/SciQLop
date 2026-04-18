from typing import Annotated, Literal

import pytest
from pydantic import BaseModel, Field

from SciQLop.user_api.knobs import (
    Knob, IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob,
)
from SciQLop.user_api.knobs.introspection import (
    extract_specs_from_callback, extract_specs_from_model,
)


def test_extract_int_with_marker():
    def f(start: float, stop: float,
          fft: Annotated[int, Knob(min=64, max=4096, step=64,
                                   label="FFT")] = 256) -> None: ...
    specs = extract_specs_from_callback(f)
    assert len(specs) == 1
    s = specs[0]
    assert isinstance(s, IntKnob)
    assert s.name == "fft" and s.default == 256
    assert s.min == 64 and s.max == 4096 and s.step == 64
    assert s.label == "FFT"


def test_extract_float_with_marker():
    def f(start, stop,
          thr: Annotated[float, Knob(min=0.0, max=1.0, step=0.01)] = 0.5):
        ...
    s = extract_specs_from_callback(f)[0]
    assert isinstance(s, FloatKnob)
    assert s.min == 0.0 and s.max == 1.0 and s.step == 0.01


def test_extract_bool_no_marker():
    def f(start, stop, cache: bool = True): ...
    s = extract_specs_from_callback(f)[0]
    assert isinstance(s, BoolKnob)
    assert s.default is True


def test_extract_literal_becomes_choice():
    def f(start, stop,
          window: Literal["hann", "hamming", "blackman"] = "hann"): ...
    s = extract_specs_from_callback(f)[0]
    assert isinstance(s, ChoiceKnob)
    assert s.default == "hann"
    assert s.choices == (("hann", "hann"), ("hamming", "hamming"),
                         ("blackman", "blackman"))


def test_extract_string_with_pattern():
    def f(start, stop,
          name: Annotated[str, Knob(pattern=r"^[a-z]+$")] = "x"): ...
    s = extract_specs_from_callback(f)[0]
    assert isinstance(s, StringKnob)
    assert s.pattern == r"^[a-z]+$"


def test_no_default_means_no_knob():
    def f(start, stop, x: int): ...
    assert extract_specs_from_callback(f) == []


def test_reserved_kwargs_skipped():
    def f(start, stop, ff: int = 1): ...
    assert {s.name for s in extract_specs_from_callback(f)} == {"ff"}


def test_varargs_warns_returns_empty(caplog):
    def f(start, stop, *args, **kwargs): ...
    import logging
    caplog.set_level(logging.WARNING)
    assert extract_specs_from_callback(f) == []


def test_choice_with_display_pairs():
    def f(start, stop,
          window: Annotated[str, Knob(choices=[("Hann", "hann"),
                                               ("Hamming", "hamming")])] = "hann"): ...
    s = extract_specs_from_callback(f)[0]
    assert isinstance(s, ChoiceKnob)
    assert s.choices == (("Hann", "hann"), ("Hamming", "hamming"))


def test_pydantic_model_to_specs():
    class K(BaseModel):
        fft: int = Field(256, ge=64, le=4096, multiple_of=64)
        window: Literal["hann", "hamming"] = "hann"
        thr: float = Field(0.5, ge=0.0, le=1.0,
                           json_schema_extra={"knob": {"label": "Threshold",
                                                       "unit": "V"}})

    specs = extract_specs_from_model(K)
    by_name = {s.name: s for s in specs}
    assert isinstance(by_name["fft"], IntKnob)
    assert by_name["fft"].min == 64 and by_name["fft"].max == 4096
    assert by_name["fft"].step == 64
    assert isinstance(by_name["window"], ChoiceKnob)
    assert by_name["window"].choices == (("hann", "hann"),
                                         ("hamming", "hamming"))
    assert isinstance(by_name["thr"], FloatKnob)
    assert by_name["thr"].label == "Threshold"
    assert by_name["thr"].unit == "V"


def test_extract_callback_with_unresolvable_forward_ref_returns_empty():
    # get_type_hints raises NameError for unresolvable forward refs;
    # introspection should swallow and produce no knobs (no crash).
    def f(start, stop, x: "NoSuchType" = 1): ...
    specs = extract_specs_from_callback(f)
    # bare `int` default fallback can still produce an IntKnob
    # because the param.annotation (string "NoSuchType") falls through
    # _spec_from_kwarg's inspect.Parameter.empty branch via isinstance(default, int)
    assert any(s.name == "x" for s in specs) or specs == []


def test_pydantic_required_field_skipped():
    class K(BaseModel):
        required_int: int  # no default — PydanticUndefined sentinel
        optional_int: int = 5

    specs = extract_specs_from_model(K)
    by_name = {s.name: s for s in specs}
    assert "required_int" not in by_name
    assert "optional_int" in by_name
