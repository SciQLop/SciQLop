from expression import Nothing, Option, Some
from .enums import PlotType, Orientation
from .protocol import Plottable
from typing import Optional, Tuple, Union, List
from ..gui import get_main_window as _get_main_window
from .._annotations import experimental_api, unstable_api
from PySide6.QtCore import Qt as _Qt
from SciQLop.backend import TimeRange
from SciQLop.backend.sciqlop_logging import getLogger as _getLogger
from SciQLopPlots import PlotType as _PlotType, GraphType as _GraphType, SciQLopMultiPlotPanel as _SciQLopMultiPlotPanel
from SciQLop.widgets.plots.time_sync_panel import (TimeSyncPanel as _ImplTimeSyncPanel, plot_product as _plot_product,
                                                   plot_static_data as _plot_static_data,
                                                   plot_function as _plot_function)
from ._plots import to_product_path, ProjectionPlot, TimeSeriesPlot, XYPlot, to_plottable, is_time_series_plot, \
    is_projection_plot, is_xy_plot, to_plot, AnyProductType, is_product

__all__ = ['PlotPanel', 'plot_panel', 'create_plot_panel']

log = _getLogger(__name__)


def _to_sqp_plot_type(plot_type: PlotType) -> _PlotType:
    if plot_type == PlotType.TimeSeries:
        return _PlotType.TimeSeries
    elif plot_type == PlotType.Projection:
        return _PlotType.Projections
    elif plot_type == PlotType.XY:
        return _PlotType.BasicXY
    else:
        raise ValueError(f"Unknown plot type {plot_type}")


def _to_sqp_orientation(orientation: Orientation) -> _Qt.Orientation:
    if orientation == Orientation.Horizontal:
        return _Qt.Orientation.Horizontal
    elif orientation == Orientation.Vertical:
        return _Qt.Orientation.Vertical
    else:
        raise ValueError(f"Unknown orientation {orientation}")


def _maybe_product(*args, **kwargs) -> Option[List[str]]:
    if len(args) == 1 and is_product(args[0]):
        return Some(to_product_path(args[0]))
    if "product" in kwargs and is_product(kwargs["product"]):
        return Some(to_product_path(kwargs["product"]))
    return Nothing


def _maybe_callable(*args, **kwargs) -> Option[callable]:
    if len(args) == 1 and callable(args[0]):
        return Some(args[0])
    if "callback" in kwargs and callable(kwargs["callback"]):
        return Some(kwargs["callback"])
    return Nothing


class PlotPanel:
    def __init__(self, impl: _ImplTimeSyncPanel):
        self._impl: _ImplTimeSyncPanel = impl
        self._impl.destroyed.connect(self._on_destroyed)

    def _on_destroyed(self):
        self._impl = None

    def _get_impl_or_raise(self) -> _ImplTimeSyncPanel:
        if self._impl is None:
            raise ValueError("The plot panel does not exist anymore.")
        return self._impl

    @experimental_api()
    def add_sub_panel(self, orientation: Orientation = Orientation.Horizontal) -> "PlotPanel":
        _panel = _SciQLopMultiPlotPanel(self._impl, synchronize_x=False,
                                        synchronize_time=True, orientation=_to_sqp_orientation(orientation))
        return PlotPanel(_panel)

    def plot_product(self, product: AnyProductType, plot_index=-1, **kwargs) -> Tuple[
        ProjectionPlot | TimeSeriesPlot, Plottable]:
        kwargs["plot_type"] = _to_sqp_plot_type(kwargs.get("plot_type", PlotType.TimeSeries))
        if kwargs["plot_type"] != _PlotType.TimeSeries:
            kwargs["graph_type"] = _GraphType.ParametricCurve
        _p, _g = _plot_product(self._get_impl_or_raise(), to_product_path(product), index=plot_index, **kwargs)
        return to_plot(_p), to_plottable(_g)

    def plot_data(self, x, y, z=None, plot_index=-1, **kwargs) -> Tuple[ProjectionPlot | TimeSeriesPlot, Plottable]:
        kwargs["plot_type"] = _to_sqp_plot_type(kwargs.get("plot_type", PlotType.TimeSeries))
        if kwargs["plot_type"] != _PlotType.TimeSeries:
            kwargs["graph_type"] = _GraphType.ParametricCurve
        _p, _g = _plot_static_data(self._get_impl_or_raise(), x, y, z, index=plot_index, **kwargs)
        return to_plot(_p), to_plottable(_g)

    def plot_function(self, f, plot_index=-1, **kwargs) -> Tuple[ProjectionPlot | TimeSeriesPlot, Plottable]:
        kwargs["plot_type"] = _to_sqp_plot_type(kwargs.get("plot_type", PlotType.TimeSeries))
        if kwargs["plot_type"] != _PlotType.TimeSeries:
            kwargs["graph_type"] = _GraphType.ParametricCurve
        _p, _g = _plot_function(self._get_impl_or_raise(), f, index=plot_index, **kwargs)
        return to_plot(_p), to_plottable(_g)

    def plot(self, *args, plot_index=-1, **kwargs) -> Tuple[ProjectionPlot | TimeSeriesPlot, Plottable] | None:
        if len(args) <= 1:  # product or callable
            r = _maybe_product(*args, **kwargs).map(lambda p: self.plot_product(p, plot_index, **kwargs)).or_else(
                _maybe_callable(*args, **kwargs).map(lambda f: self.plot_function(f, plot_index, **kwargs)))
            if r is Nothing:
                log.error("No product found in the arguments")
                return None
            return r.value
        elif len(args) >= 2:  # likely static data plot (x, y, [z], [plot_type])
            return self.plot_data(*args, **kwargs)
        return None

    def remove_plot(self, plot_index):
        pass

    @property
    def time_range(self) -> TimeRange:
        return self._get_impl_or_raise().time_axis_range()

    @time_range.setter
    def time_range(self, time_range: TimeRange):
        self._get_impl_or_raise().set_time_axis_range(time_range)

    @property
    def plots(self):
        def wrap_plot(p):
            if is_time_series_plot(p):
                return TimeSeriesPlot(p)
            elif is_projection_plot(p):
                return ProjectionPlot(p)
            elif is_xy_plot(p):
                return XYPlot(p)
            else:
                return None

        return list(filter(lambda p: p is not None, map(wrap_plot, self._impl.plots())))

    def _repr_pretty_(self, p, cycle):
        if cycle:
            p.text("PlotPanel(...)")
        else:
            with p.group(4, "PlotPanel(", ")"):
                p.breakable()
                p.pretty(self.time_range)
                p.breakable()
                for i, plot in enumerate(self.plots):
                    if i > 0:
                        p.text(",")
                        p.breakable()
                    p.pretty(plot)


def plot_panel(name: str) -> Optional[PlotPanel]:
    """Get a plot panel by name.

    Args:
        name (str): The name of the plot panel.

    Returns:
        Optional[PlotPanel]: The plot panel if found, otherwise None.
    """
    p = _get_main_window().plot_panel(name)
    if p is not None:
        return PlotPanel(p)
    return None


def create_plot_panel() -> PlotPanel:
    """Create a new plot panel.

    Returns:
        PlotPanel: The newly created plot panel.
    """
    return PlotPanel(_get_main_window().new_plot_panel())
