"""Plotting API. This module provides the public API for plotting data and managing plot panels.
"""

from enum import Enum
from typing import Optional, Union
from ..gui import get_main_window as _get_main_window
from ..virtual_products import VirtualProduct
from SciQLop.backend import TimeRange
from SciQLop.widgets.plots.projection_plot import ProjectionPlot as _ImplProjectionPlot
from SciQLop.widgets.plots.time_series_plot import TimeSeriesPlot as _ImplTimeSeriesPlot
from SciQLopPlots import QCPAxis as _QCPAxis
from speasy.core import AnyDateTimeType


def _is_projection_plot(impl):
    return isinstance(impl, _ImplProjectionPlot)


def _is_time_series_plot(impl):
    return isinstance(impl, _ImplTimeSeriesPlot)


class PlotType(Enum):
    TimeSeries = 0
    Projection = 1


class ScaleType(Enum):
    Linear = 0
    Logarithmic = 1


def _get_qcpaxis_scale_type(axis: _QCPAxis):
    if axis.scaleType() == _QCPAxis.stLinear:
        return ScaleType.Linear
    elif axis.scaleType() == _QCPAxis.stLogarithmic:
        return ScaleType.Logarithmic
    else:
        raise ValueError(f"Unknown scale type {axis.scale_type}")


def _set_qcpaxis_scale_type(scale_type: ScaleType, axis: _QCPAxis):
    if scale_type == ScaleType.Linear:
        axis.setScaleType(_QCPAxis.stLinear)
    elif scale_type == ScaleType.Logarithmic:
        axis.setScaleType(_QCPAxis.stLogarithmic)
    else:
        raise ValueError(f"Unknown scale type {scale_type}")


class Graph:
    def __init__(self, impl):
        self._impl = impl


class TimeSeriesPlot:
    def __init__(self, impl):
        assert _is_time_series_plot(impl)
        self._impl: Optional[_ImplTimeSeriesPlot] = impl
        self._impl.destroyed.connect(self._on_destroyed)

    def _on_destroyed(self):
        self._impl = None

    def _get_impl_or_raise(self) -> _ImplTimeSeriesPlot:
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
        self._get_impl_or_raise().yAxis.setRange(s_y_min, s_y_max)

    def set_y_scale_type(self, scale: ScaleType):
        """Set the scale type of the main y-axis.

        Args:
            scale (ScaleType): The scale type.
        """
        self.y_scale_type = scale

    @property
    def time_range(self) -> TimeRange:
        return self._get_impl_or_raise().time_range

    @time_range.setter
    def time_range(self, time_range: TimeRange):
        self._impl.time_range = time_range

    @property
    def y_scale_type(self) -> ScaleType:
        return _get_qcpaxis_scale_type(self._get_impl_or_raise().yAxis)

    @y_scale_type.setter
    def y_scale_type(self, scale_type: ScaleType):
        _set_qcpaxis_scale_type(scale_type, self._get_impl_or_raise().yAxis)
        self.replot()

    def replot(self):
        self._get_impl_or_raise().replot()


class ProjectionPlot:
    def __init__(self, impl):
        assert _is_projection_plot(impl)
        self._impl = impl

    def set_x_range(self, min: float, max: float):
        pass

    def set_y_range(self, min: float, max: float):
        pass

    def set_x_scale_type(self, scale: ScaleType):
        pass

    def set_y_scale_type(self, scale: ScaleType):
        pass


class PlotPanel:
    def __init__(self, impl):
        self._impl = impl

    def plot(self, product: Union[str, VirtualProduct], plot_index: int = -1, plot_type: PlotType = PlotType.TimeSeries,
             colors=None) -> Optional[Union[TimeSeriesPlot, ProjectionPlot]]:
        if isinstance(product, VirtualProduct):
            print(f"VirtualProduct path: {product.path}")
            self.plot(product.path, plot_index, PlotType.TimeSeries, colors)
        elif plot_type == PlotType.TimeSeries:
            self._impl.plot(product, plot_index)
            return TimeSeriesPlot(self._impl.plots[plot_index])
        else:
            self._impl.plot(product, plot_index)
            return ProjectionPlot(self._impl.plots[plot_index])

    def remove_plot(self, plot_index):
        pass

    @property
    def time_range(self) -> TimeRange:
        return self._impl.time_range

    @time_range.setter
    def time_range(self, time_range: TimeRange):
        self._impl.time_range = time_range

    @property
    def plots(self):
        def wrap_plot(p):
            if _is_time_series_plot(p):
                return TimeSeriesPlot(p)
            elif _is_projection_plot(p):
                return ProjectionPlot(p)
            else:
                return None

        return list(filter(lambda p: p is not None, map(wrap_plot, self._impl.plots)))


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
