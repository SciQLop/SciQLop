"""How a virtual product's colour axis looks on a plot."""
import logging
from dataclasses import dataclass
from typing import Optional

from SciQLopPlots import ColorGradient

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ColorAxis:
    label: str = ""
    gradient: ColorGradient = ColorGradient.Jet


def apply_color_axis(plot, graph, axis: Optional[ColorAxis]) -> None:
    if axis is None or graph is None:
        return
    if not hasattr(graph, "set_color_gradient"):
        log.warning("%s can't show a colour scale; plot this coloured product as a line graph",
                    type(graph).__name__)
        return
    graph.set_color_gradient(axis.gradient)
    if axis.label and plot is not None:
        plot.z_axis().set_label(axis.label)
