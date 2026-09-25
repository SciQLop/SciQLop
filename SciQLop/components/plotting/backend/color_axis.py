"""How a virtual product's colour axis looks on a plot."""
from dataclasses import dataclass
from typing import Optional

from SciQLopPlots import ColorGradient


@dataclass(frozen=True)
class ColorAxis:
    label: str = ""
    gradient: ColorGradient = ColorGradient.Jet


def apply_color_axis(plot, graph, axis: Optional[ColorAxis]) -> None:
    if axis is None or graph is None:
        return
    graph.set_color_gradient(axis.gradient)
    if axis.label and plot is not None:
        plot.z_axis().set_label(axis.label)
