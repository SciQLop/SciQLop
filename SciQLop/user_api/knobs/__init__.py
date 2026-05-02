"""Public API alias for SciQLop.core.knobs.

The implementations live in SciQLop.core.knobs. This module re-exports them
so the public surface (used from notebooks and external scripts) is preserved.

Submodule paths (e.g. `SciQLop.user_api.knobs.specs`) are also aliased to
their `SciQLop.core.knobs.*` counterparts for backward compatibility.
"""
import sys as _sys

from SciQLop.core.knobs import (
    Knob,
    KnobSpec, IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob,
    StringListKnob, DatetimeKnob, TimeRangeKnob, ThresholdKnob,
    spec_to_dict, spec_from_dict,
    coerce_value, validate_dict, canonical_hash, defaults_for,
    extract_specs_from_callback, extract_specs_from_model,
)
from SciQLop.core.knobs import marker as _marker
from SciQLop.core.knobs import specs as _specs
from SciQLop.core.knobs import values as _values
from SciQLop.core.knobs import introspection as _introspection

_sys.modules[__name__ + ".marker"] = _marker
_sys.modules[__name__ + ".specs"] = _specs
_sys.modules[__name__ + ".values"] = _values
_sys.modules[__name__ + ".introspection"] = _introspection

marker = _marker
specs = _specs
values = _values
introspection = _introspection

__all__ = [
    "Knob",
    "KnobSpec", "IntKnob", "FloatKnob", "BoolKnob", "ChoiceKnob", "StringKnob",
    "StringListKnob", "DatetimeKnob", "TimeRangeKnob", "ThresholdKnob",
    "spec_to_dict", "spec_from_dict",
    "coerce_value", "validate_dict", "canonical_hash", "defaults_for",
    "extract_specs_from_callback", "extract_specs_from_model",
]
