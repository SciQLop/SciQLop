from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class KnobSpec:
    """Base for all knob specs; instantiate a concrete subclass instead."""
    name: str
    label: str = ""
    unit: str = ""
    description: str = ""
    apply: Literal["live", "manual"] = "live"


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
