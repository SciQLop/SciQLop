"""Plotting API. This module provides the public API for plotting data and managing plot panels.
"""

from enum import Enum
from typing import Optional, Union
from ..gui import get_main_window as _get_main_window
from SciQLop.backend import TimeRange

PlotType = Enum('PlotType', ['TimeSeries', 'Projection'])
ScaleType = Enum('ScaleType', ['Linear', 'Logarithmic'])


class Graph:
    def __init__(self, impl):
        self._impl = impl


class TimeSeriesPlot:
    def __init__(self, impl):
        self._impl = impl

    def set_y_range(self, min: float, max: float):
        pass

    def set_y_scale_type(self, scale: ScaleType):
        pass


class ProjectionPlot:
    def __init__(self, impl):
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

    def plot(self, product, plot_index=-1, plot_type=PlotType.TimeSeries, colors=None) -> Optional[
        Union[TimeSeriesPlot, ProjectionPlot]]:
        if plot_type == PlotType.TimeSeries:
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
