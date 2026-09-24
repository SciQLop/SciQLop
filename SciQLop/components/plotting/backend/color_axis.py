"""How a virtual product's colour axis looks on a plot."""
from dataclasses import dataclass

from SciQLopPlots import ColorGradient


@dataclass(frozen=True)
class ColorAxis:
    label: str = ""
    gradient: ColorGradient = ColorGradient.Jet
