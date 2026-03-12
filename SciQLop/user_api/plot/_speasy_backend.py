from __future__ import annotations
import numpy as np
from speasy.core import datetime64_to_epoch
from SciQLop.user_api.plot._panel import PlotPanel, create_plot_panel
from SciQLop.user_api.plot._plots import TimeSeriesPlot
from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)

_current_panel: PlotPanel | None = None


def _get_or_create_panel() -> PlotPanel:
    global _current_panel
    if _current_panel is None or _current_panel._impl is None:
        _current_panel = create_plot_panel()
    return _current_panel


def _ensure_epoch_seconds(x):
    """Convert datetime64 arrays to epoch seconds (float64), pass through numeric arrays."""
    if hasattr(x, 'dtype') and np.issubdtype(x.dtype, np.datetime64):
        return datetime64_to_epoch(x)
    return x


def _plot_into(ax, x, y, z=None):
    """Dispatch plot call based on ax type.

    Returns (TimeSeriesPlot | ProjectionPlot, Graph | ColorMap).
    """
    global _current_panel
    x = _ensure_epoch_seconds(x)
    if ax is None:
        panel = _get_or_create_panel()
        return panel.plot_data(x, y, z) if z is not None else panel.plot_data(x, y)
    if isinstance(ax, PlotPanel):
        _current_panel = ax
        return ax.plot_data(x, y, z) if z is not None else ax.plot_data(x, y)
    if isinstance(ax, TimeSeriesPlot):
        args = (x, y, z) if z is not None else (x, y)
        graph = ax.plot(*args)
        return ax, graph
    raise TypeError(f"ax must be None, PlotPanel, or TimeSeriesPlot, got {type(ax).__name__}")


class SciQLopBackend:
    def line(self, x, y, ax=None, labels=None, units=None,
             xaxis_label=None, yaxis_label=None, *args, **kwargs):
        return _plot_into(ax, x, y)

    def colormap(self, x, y, z, ax=None, logy=True, logz=True,
                 xaxis_label=None, yaxis_label=None, yaxis_units=None,
                 zaxis_label=None, zaxis_units=None, cmap=None,
                 vmin=None, vmax=None, *args, **kwargs):
        return _plot_into(ax, x, y, z)

    def __call__(self, *args, **kwargs):
        pass
