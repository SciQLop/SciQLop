import dataclasses
from dataclasses import dataclass, field
from typing import Any, Literal

from SciQLopPlots import SciQLopPlotRange


@dataclass(frozen=True, slots=True)
class KnobSpec:
    """Base for all knob specs; instantiate a concrete subclass instead."""
    name: str
    label: str = ""
    unit: str = ""
    description: str = ""
    apply: Literal["live", "manual"] = "live"
    widget: str = ""


@dataclass(frozen=True, slots=True)
class IntKnob(KnobSpec):
    default: int = 0
    min: int | None = None
    max: int | None = None
    step: int = 1


@dataclass(frozen=True, slots=True)
class FloatKnob(KnobSpec):
    default: float = 0.0
    min: float | None = None
    max: float | None = None
    step: float = 0.01


@dataclass(frozen=True, slots=True)
class BoolKnob(KnobSpec):
    default: bool = False


@dataclass(frozen=True, slots=True)
class ChoiceKnob(KnobSpec):
    default: Any = None
    choices: tuple[tuple[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class StringKnob(KnobSpec):
    default: str = ""
    pattern: str = ""


@dataclass(frozen=True, slots=True)
class StringListKnob(KnobSpec):
    """A list of short strings (e.g. tags). Edited inline as chips/tokens."""
    default: tuple[str, ...] = ()
    suggestions: tuple[str, ...] = ()
    item_pattern: str = ""


@dataclass(frozen=True, slots=True)
class TimeRangeKnob(KnobSpec):
    default: SciQLopPlotRange = field(default_factory=lambda: SciQLopPlotRange(0.25, 0.75))
    widget: str = "vspan"
    color: str = "#3498db"


@dataclass(frozen=True, slots=True)
class ThresholdKnob(FloatKnob):
    widget: str = "hline"
    color: str = "#e74c3c"


# ---------------------------------------------------------------------------
# JSON-friendly serialization
# ---------------------------------------------------------------------------

# Concrete spec classes that can roundtrip through plain JSON. TimeRangeKnob /
# ThresholdKnob carry SciQLopPlotRange defaults and aren't covered.
_SERIALIZABLE_SPECS: dict[str, type[KnobSpec]] = {
    cls.__name__: cls
    for cls in (IntKnob, FloatKnob, BoolKnob, ChoiceKnob, StringKnob, StringListKnob)
}


def _normalize_for_json(value: Any) -> Any:
    if isinstance(value, tuple):
        return [_normalize_for_json(v) for v in value]
    if isinstance(value, list):
        return [_normalize_for_json(v) for v in value]
    return value


def spec_to_dict(spec: KnobSpec) -> dict:
    """Serialize a KnobSpec subclass to a JSON-friendly dict.

    Tuples are flattened to lists; the spec's class name lands in the ``type``
    field so ``spec_from_dict`` can dispatch.
    """
    cls_name = type(spec).__name__
    result: dict = {"type": cls_name}
    for field_name in spec.__dataclass_fields__:
        value = getattr(spec, field_name)
        result[field_name] = _normalize_for_json(value)
    return result


def spec_from_dict(data: dict) -> KnobSpec | None:
    """Deserialize a dict produced by :func:`spec_to_dict`. Returns ``None`` if
    the type is unknown or missing."""
    cls_name = data.get("type")
    if not cls_name:
        return None
    cls = _SERIALIZABLE_SPECS.get(cls_name)
    if cls is None:
        return None
    kwargs = {k: v for k, v in data.items() if k != "type"}
    field_types = {f.name: f.type for f in dataclasses.fields(cls)}
    for k, v in list(kwargs.items()):
        ftype = field_types.get(k, "")
        if isinstance(v, list) and "tuple" in str(ftype):
            if "tuple[tuple" in str(ftype):
                kwargs[k] = tuple(tuple(item) for item in v)
            else:
                kwargs[k] = tuple(v)
    try:
        return cls(**kwargs)
    except TypeError:
        return None
