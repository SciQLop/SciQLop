"""Apply percentile-based robust-autoscale defaults from PlotBackendSettings
to freshly-created SciQLopPlot instances.

SciQLopPlots 0.25.0 exposes ``set_autoscale_percentile_low/high`` on
``SciQLopPlotAxis`` (y, y2) and on ``SciQLopColorMapBase`` (every colormap /
histogram2d plottable). Defaults shipped in C++ are 0/100 (plain min/max);
SciQLop overlays its own defaults so a fresh panel gets robust z-axis
autoscale on colormaps without the user touching anything.

Settings are read once at plot-creation time and cached on the plot, so
later-added colormaps get the same percentiles without re-reading YAML."""

from typing import NamedTuple
from SciQLopPlots import SciQLopColorMapBase
from SciQLop.components.settings.backend.plot_backend_settings import (
    PlotBackendSettings,
)


class _Percentiles(NamedTuple):
    graph_low: float
    graph_high: float
    colormap_low: float
    colormap_high: float

    @classmethod
    def snapshot(cls) -> "_Percentiles":
        s = PlotBackendSettings()
        return cls(
            graph_low=s.graph_autoscale_percentile_low,
            graph_high=s.graph_autoscale_percentile_high,
            colormap_low=s.colormap_autoscale_percentile_low,
            colormap_high=s.colormap_autoscale_percentile_high,
        )


def _apply_to_axis(plot, getter: str, low: float, high: float) -> None:
    axis_fn = getattr(plot, getter, None)
    if axis_fn is None:
        return
    axis = axis_fn()
    if axis is None or not hasattr(axis, "set_autoscale_percentile_low"):
        return
    axis.set_autoscale_percentile_low(low)
    axis.set_autoscale_percentile_high(high)


def _apply_to_colormaps(plot, low: float, high: float) -> None:
    plottables_fn = getattr(plot, "plottables", None)
    if plottables_fn is None:
        return
    for p in plottables_fn():
        if isinstance(p, SciQLopColorMapBase):
            p.set_autoscale_percentile_low(low)
            p.set_autoscale_percentile_high(high)


def apply_defaults_to_plot(plot) -> None:
    """Apply axis (graph) + any-existing-colormap percentiles to ``plot``,
    and subscribe to ``graph_list_changed`` so later-added colormaps inherit
    the same values."""
    snap = _Percentiles.snapshot()
    plot._sciqlop_percentile_snapshot = snap
    _apply_to_axis(plot, "y_axis", snap.graph_low, snap.graph_high)
    _apply_to_axis(plot, "y2_axis", snap.graph_low, snap.graph_high)
    _apply_to_colormaps(plot, snap.colormap_low, snap.colormap_high)
    signal = getattr(plot, "graph_list_changed", None)
    if signal is None:
        return
    signal.connect(lambda: _on_graph_list_changed(plot))


def _on_graph_list_changed(plot) -> None:
    snap = getattr(plot, "_sciqlop_percentile_snapshot", None)
    if snap is None:
        return
    _apply_to_colormaps(plot, snap.colormap_low, snap.colormap_high)
