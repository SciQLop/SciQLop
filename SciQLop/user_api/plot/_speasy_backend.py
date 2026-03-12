from __future__ import annotations
from SciQLop.user_api.plot._panel import PlotPanel, create_plot_panel
from SciQLop.user_api.plot._plots import TimeSeriesPlot
from SciQLop.user_api.plot._graphs import _to_float64
from SciQLop.core import TimeRange
from SciQLop.components.sciqlop_logging import getLogger

log = getLogger(__name__)

_current_panel: PlotPanel | None = None


def _get_or_create_panel() -> PlotPanel:
    global _current_panel
    if _current_panel is None or _current_panel._impl is None:
        _current_panel = create_plot_panel()
    return _current_panel


def _set_time_range_from_data(panel: PlotPanel, x):
    x = _to_float64(x)
    if len(x) >= 2:
        panel.time_range = TimeRange(float(x.min()), float(x.max()))


def _plot_into(ax, x, y, z=None, **kwargs):
    """Dispatch plot call based on ax type.

    Returns (TimeSeriesPlot | ProjectionPlot, Graph | ColorMap).
    """
    global _current_panel
    if ax is None:
        panel = _get_or_create_panel()
        result = panel.plot_data(x, y, z, **kwargs) if z is not None else panel.plot_data(x, y, **kwargs)
        _set_time_range_from_data(panel, x)
        return result
    if isinstance(ax, PlotPanel):
        _current_panel = ax
        result = ax.plot_data(x, y, z, **kwargs) if z is not None else ax.plot_data(x, y, **kwargs)
        _set_time_range_from_data(ax, x)
        return result
    if isinstance(ax, TimeSeriesPlot):
        args = (x, y, z) if z is not None else (x, y)
        graph = ax.plot(*args, **kwargs)
        return ax, graph
    raise TypeError(f"ax must be None, PlotPanel, or TimeSeriesPlot, got {type(ax).__name__}")


class SciQLopBackend:
    def line(self, x, y, ax=None, labels=None, units=None,
             xaxis_label=None, yaxis_label=None, *args, **kwargs):
        return _plot_into(ax, x, y, labels=labels)

    def colormap(self, x, y, z, ax=None, logy=True, logz=True,
                 xaxis_label=None, yaxis_label=None, yaxis_units=None,
                 zaxis_label=None, zaxis_units=None, cmap=None,
                 vmin=None, vmax=None, *args, **kwargs):
        return _plot_into(ax, x, y, z)

    def __call__(self, *args, **kwargs):
        pass
