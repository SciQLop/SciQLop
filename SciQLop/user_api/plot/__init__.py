"""Plotting API. This module provides the public API for plotting data and managing plot panels.
"""
from .enums import ScaleType, PlotType
from .protocol import Plot, Plottable

from SciQLop.backend.sciqlop_logging import getLogger as _getLogger
from ._plots import XYPlot, TimeSeriesPlot, ProjectionPlot, TimeRange
from ._panel import PlotPanel, create_plot_panel, plot_panel
from ._graphic_primitives import Ellipse, Text, CurvedLine

log = _getLogger(__name__)

__all__ = ['ScaleType', 'PlotType', 'Plot', 'Plottable', 'XYPlot', 'TimeSeriesPlot', 'ProjectionPlot', 'PlotPanel',
           'create_plot_panel', 'plot_panel', 'TimeRange', 'Ellipse']
