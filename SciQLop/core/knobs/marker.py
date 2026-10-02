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
    widget: str = ""
    color: str = ""
    # Visual time knobs (vspan, vline): draw on every plot of the panel or only
    # on the product's own plot.
    scope: Literal["panel", "plot"] = "panel"

    def __post_init__(self):
        if self.scope not in ("panel", "plot"):
            raise ValueError(f"scope must be 'panel' or 'plot', got {self.scope!r}")
