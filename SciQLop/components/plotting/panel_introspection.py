"""Enumerate a panel's plots and plottables the way every exporter needs them.
The one place that knows the Qt-side quirks; ``PanelTemplate.from_panel``
turns the result into the shared panel model."""
from __future__ import annotations

from SciQLopPlots import SciQLopPlot, SciQLopPlottableInterface


def ordered_plots(panel) -> list:
    """Real ``SciQLopPlot`` widgets in the order ``panel.plots()`` reports —
    ``findChildren`` alone returns Qt insertion order which doesn't match the
    panel's logical layout after templates / re-orderings.
    """
    try:
        ptrs = list(panel.plots())
    except Exception:
        return list(panel.findChildren(SciQLopPlot))
    by_name = {p.objectName(): p for p in panel.findChildren(SciQLopPlot)}
    return [by_name[ptr.objectName()] for ptr in ptrs if ptr.objectName() in by_name]


def plot_graphs(plot) -> list:
    """Every plottable in ``plot``: line graphs *and* colormaps. Colormaps are
    not ``SciQLopGraphInterface`` — both derive from
    ``SciQLopPlottableInterface`` — so filtering on the graph class silently
    drops spectrograms.
    """
    return list(plot.findChildren(SciQLopPlottableInterface))
