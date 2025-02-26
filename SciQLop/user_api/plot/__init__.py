"""Plotting API. This module provides the public API for plotting data and managing plot panels.
"""

from enum import Enum
from typing import Optional, Union, List
from ..gui import get_main_window as _get_main_window
from ..virtual_products import VirtualProduct
from SciQLop.backend import TimeRange
from SciQLop.backend.sciqlop_logging import getLogger as _getLogger
from SciQLopPlots import SciQLopPlot as _SciQLopPlot
from SciQLopPlots import SciQLopTimeSeriesPlot as _SciQLopTimeSeriesPlot
from SciQLopPlots import SciQLopPlotAxis as _SciQLopPlotAxis
from SciQLopPlots import SciQLopNDProjectionPlot as _SciQLopNDProjectionPlot
from SciQLopPlots import PlotType as _PlotType, GraphType as _GraphType
from SciQLop.widgets.plots.time_sync_panel import TimeSyncPanel as _ImplTimeSyncPanel, plot_product as _plot_product

# from SciQLopPlots import QCPAxis as _QCPAxis, QCPAxisTickerLog as _QCPAxisTickerLog, QCPAxisTicker as _QCPAxisTicker
from speasy.core import AnyDateTimeType

log = _getLogger(__name__)


def _is_meta_object_instance(obj, meta_type: str):
    if hasattr(obj, "metaObject"):
        return obj.metaObject().className() == meta_type
    return False


def _is_projection_plot(impl):
    return isinstance(impl, _SciQLopNDProjectionPlot) or _is_meta_object_instance(impl, "SciQLopNDProjectionPlot")


def _is_time_series_plot(impl):
    return isinstance(impl, _SciQLopTimeSeriesPlot) or _is_meta_object_instance(impl, "SciQLopTimeSeriesPlot")


def _split_path(path: str) -> List[str]:
    if '//' in path:
        return path.split('//')
    return path.split('/')


class PlotType(Enum):
    TimeSeries = 0
    Projection = 1


class ScaleType(Enum):
    Linear = 0
    Logarithmic = 1


def _get_axis_scale_type(axis: _SciQLopPlotAxis):
    return ScaleType.Logarithmic if axis.log() else ScaleType.Linear


def _set_axis_scale_type(scale_type: ScaleType, axis: _SciQLopPlotAxis):
    if scale_type == ScaleType.Linear:
        axis.set_log(False)
    elif scale_type == ScaleType.Logarithmic:
        axis.set_log(True)
    else:
        raise ValueError(f"Unknown scale type {scale_type}")


def _to_product_path(product: Union[str, VirtualProduct, List[str]]) -> List[str]:
    if isinstance(product, VirtualProduct):
        return _split_path(product.path)
    elif isinstance(product, str):
        return _split_path(product)
    return product


class Graph:
    def __init__(self, impl):
        self._impl = impl


class TimeSeriesPlot:
    def __init__(self, impl):
        assert _is_time_series_plot(impl)
        self._impl: Optional[_SciQLopTimeSeriesPlot] = impl
        self._impl.destroyed.connect(self._on_destroyed)

    def _on_destroyed(self):
        self._impl = None

    def plot(self, product: Union[str, VirtualProduct], colors=None):
        product = _to_product_path(product)
        _plot_product(self._get_impl_or_raise(), product)

    def _get_impl_or_raise(self) -> _SciQLopTimeSeriesPlot:
        if self._impl is None:
            raise ValueError("The plot does not exist anymore.")
        return self._impl

    def set_x_range(self, xmin: AnyDateTimeType, xmax: AnyDateTimeType):
        """Set the x-axis range of the plot.
        This method accepts any type of datetime object, Python datetime object, or timestamp or string.

        Args:
            xmin (AnyDateTimeType): The minimum value of the x-axis range.
            xmax (AnyDateTimeType): The maximum value of the x-axis range.

        Note:
            Setting the x-axis range will adjust the time range of the plot panel in which the plot is displayed and
            thus affect all plots in the panel.

            While this is discouraged, it is possible to set xmin>xmax, in which case it will automatically swap the values.
        """
        self.time_range = TimeRange(xmin, xmax)

    def set_y_range(self, ymin: float, ymax: float):
        """Set the main y-axis range of the plot.

        Args:
            ymin (float): The minimum value of the y-axis range.
            ymax (float): The maximum value of the y-axis range.

        Note:
            Setting the y-axis range will only affect the plot in which it is called. It will not affect other plots in the same plot panel.
            While this is discouraged, it is possible to set ymin>ymax, in which case it will automatically swap the values.
        """
        s_y_min = min(ymin, ymax)
        s_y_max = max(ymin, ymax)
        self._get_impl_or_raise().y_axis().set_range(s_y_min, s_y_max)

    def set_y_scale_type(self, scale: ScaleType):
        """Set the scale type of the main y-axis.

        Args:
            scale (ScaleType): The scale type.
        """
        self.y_scale_type = scale

    @property
    def time_range(self) -> TimeRange:
        return self._get_impl_or_raise().time_axis().range()

    @time_range.setter
    def time_range(self, time_range: TimeRange):
        self._impl.set_time_range(time_range)

    @property
    def y_scale_type(self) -> ScaleType:
        return _get_axis_scale_type(self._get_impl_or_raise().y_axis())

    @y_scale_type.setter
    def y_scale_type(self, scale_type: ScaleType):
        _set_axis_scale_type(scale_type, self._get_impl_or_raise().y_axis())
        self.replot()

    def replot(self):
        self._get_impl_or_raise().replot()


class ProjectionPlot:
    def __init__(self, impl):
        assert _is_projection_plot(impl)
        self._impl = impl

    def _get_impl_or_raise(self) -> _SciQLopNDProjectionPlot:
        if self._impl is None:
            raise ValueError("The plot does not exist anymore.")
        return self._impl

    def set_x_range(self, min: float, max: float):
        pass

    def set_y_range(self, min: float, max: float):
        pass

    def set_x_scale_type(self, scale: ScaleType):
        pass

    def set_y_scale_type(self, scale: ScaleType):
        pass

    def plot(self, product: Union[str, VirtualProduct], colors=None):
        product = _to_product_path(product)
        return _plot_product(self._get_impl_or_raise(), product, graph_type=_GraphType.ParametricCurve)


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

    def plot(self, product: Union[str, VirtualProduct, List[str]], plot_index: int = -1,
             plot_type: PlotType = PlotType.TimeSeries,
             colors=None) -> Optional[Union[TimeSeriesPlot, ProjectionPlot]]:
        product = _to_product_path(product)
        if plot_type == PlotType.TimeSeries:
            log.debug(f"Plotting time series {product}")
            p, g = _plot_product(self._get_impl_or_raise(), product, index=plot_index, plot_type=_PlotType.TimeSeries)
            return TimeSeriesPlot(p)
        elif plot_type == PlotType.Projection:
            log.debug(f"Plotting projection {product}")
            p, g = _plot_product(self._get_impl_or_raise(), product, index=plot_index, plot_type=_PlotType.Projections,
                                 graph_type=_GraphType.ParametricCurve)
            return ProjectionPlot(p)

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
            if _is_time_series_plot(p):
                return TimeSeriesPlot(p)
            elif _is_projection_plot(p):
                return ProjectionPlot(p)
            else:
                return None

        return list(filter(lambda p: p is not None, map(wrap_plot, self._impl.plots())))


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
