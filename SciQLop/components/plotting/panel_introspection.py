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
    return [plot for plot in panel.plots() if isinstance(plot, SciQLopPlot)]


def ordered_panel_plots(panel) -> list:
    """Every plot in panel order, each a concrete widget (time-series, projection or placeholder)."""
    return list(panel.plots())


def plot_graphs(plot) -> list:
    """Every plottable in ``plot``: line graphs *and* colormaps. Colormaps are
    not ``SciQLopGraphInterface`` — both derive from
    ``SciQLopPlottableInterface`` — so filtering on the graph class silently
    drops spectrograms.
    """
    return list(plot.findChildren(SciQLopPlottableInterface))
