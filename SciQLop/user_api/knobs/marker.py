from dataclasses import dataclass
from typing import Any, Literal


@dataclass(frozen=True, slots=True)
class Knob:
    min: Any = None
    max: Any = None
    step: Any = None
    label: str = ""
    unit: str = ""
    description: str = ""
    apply: Literal["live", "manual"] = "live"
    choices: tuple[tuple[str, Any], ...] | None = None
    pattern: str = ""
