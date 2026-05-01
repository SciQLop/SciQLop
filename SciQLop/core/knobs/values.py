import hashlib
import json
import re
from typing import Any, Iterable

from SciQLopPlots import SciQLopPlotRange

from SciQLop.core.knobs.specs import (
    KnobSpec, IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob,
    TimeRangeKnob, ThresholdKnob,
)


def defaults_for(specs: Iterable[KnobSpec]) -> dict[str, Any]:
    return {s.name: s.default for s in specs}


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _clamp(v, lo, hi):
    if lo is not None and v < lo:
        return lo
    if hi is not None and v > hi:
        return hi
    return v


def _coerce_time_range(value: Any) -> SciQLopPlotRange:
    if isinstance(value, SciQLopPlotRange):
        return value
    if isinstance(value, (list, tuple)) and len(value) == 2:
        return SciQLopPlotRange(float(value[0]), float(value[1]))
    raise TypeError(f"Cannot coerce {type(value).__name__} to TimeRange")


def coerce_value(spec: KnobSpec, value: Any) -> Any:
    if isinstance(spec, TimeRangeKnob):
        return _coerce_time_range(value)
    if isinstance(spec, ThresholdKnob):
        v = float(value)
        return _clamp(v, spec.min, spec.max)
    if isinstance(spec, IntKnob):
        v = int(value)
        v = _clamp(v, spec.min, spec.max)
        if spec.step and spec.step > 0 and spec.min is not None:
            offset = v - spec.min
            v = spec.min + round(offset / spec.step) * spec.step
            v = _clamp(v, spec.min, spec.max)
        return v
    if isinstance(spec, FloatKnob):
        v = float(value)
        return _clamp(v, spec.min, spec.max)
    if isinstance(spec, BoolKnob):
        return _to_bool(value)
    if isinstance(spec, ChoiceKnob):
        valid = {pair[1] for pair in spec.choices}
        if value not in valid:
            raise ValueError(f"{value!r} not in {sorted(valid)!r}")
        return value
    if isinstance(spec, StringKnob):
        s = str(value)
        if spec.pattern and not re.match(spec.pattern, s):
            raise ValueError(f"{s!r} does not match {spec.pattern!r}")
        return s
    raise TypeError(f"Unknown spec type: {type(spec).__name__}")


def validate_dict(specs: Iterable[KnobSpec], values: dict[str, Any]) -> dict[str, Any]:
    by_name = {s.name: s for s in specs}
    out: dict[str, Any] = {}
    for name, spec in by_name.items():
        if name in values:
            try:
                out[name] = coerce_value(spec, values[name])
            except (ValueError, TypeError):
                out[name] = spec.default
        else:
            out[name] = spec.default
    return out


def _canonicalize(value: Any) -> Any:
    if isinstance(value, SciQLopPlotRange):
        return [round(value.start(), 9), round(value.stop(), 9)]
    if isinstance(value, float):
        return round(value, 9)
    if isinstance(value, dict):
        return {k: _canonicalize(value[k]) for k in sorted(value)}
    if isinstance(value, (list, tuple)):
        return [_canonicalize(v) for v in value]
    return value


def canonical_hash(values: dict[str, Any] | None) -> str:
    payload = _canonicalize(values or {})
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha1(blob).hexdigest()
