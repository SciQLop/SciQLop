import sys
from datetime import datetime
from gc import callbacks
from typing import Optional, List, Any, Union

import numpy as np
from PySide6.QtCore import QMimeData, Signal, QMargins
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QScrollArea
from SciQLopPlots import SciQLopMultiPlotPanel, PlotDragNDropCallback, SciQLopPlotInterface, ProductsModel, SciQLopPlot, \
    ParameterType, GraphType, SciQLopNDProjectionPlot

from SciQLop.backend.icons import register_icon
from ...backend import TimeRange
from ...backend import listify
from ...backend import sciqlop_logging
from ...backend.pipelines_model.data_provider import providers, DataProvider
from ...backend.property import SciQLopProperty
from ...mime import decode_mime
from ...mime.types import PRODUCT_LIST_MIME_TYPE, TIME_RANGE_MIME_TYPE
from .palette import Palette, make_color_list

log = sciqlop_logging.getLogger(__name__)

register_icon("QCP", QIcon("://icons/QCP.png"))


class _plot_product_callback:
    def __init__(self, provider: DataProvider, node):
        self.provider = provider
        self.node = node

    def __call__(self, start, stop):
        try:
            return self.provider._get_data(self.node, start, stop)
        except Exception as e:
            log.error(f"Error getting data for {self.node}: {e}")
            return []


def _y_is_descending(y):
    if len(y.shape) == 1 and len(y) > 1:
        return np.nanargmin(y) > np.nanargmax(y)
    elif len(y.shape) == 2 and y.shape[0] > 1:
        return np.nanargmin(y[0, :]) > np.nanargmax(y[0, :])
    else:
        return None


class _specgram_callback:
    def __init__(self, provider: DataProvider, node):
        self.provider = provider
        self.node = node
        self._y_is_descending_ = None

    def _y_is_descending(self, y):
        if self._y_is_descending_ is None:
            self._y_is_descending_ = _y_is_descending(y)
            log.debug(f"y_is_descending: {self._y_is_descending_}")
        return self._y_is_descending_

    def __call__(self, start, stop):
        try:
            x, y, z = self.provider._get_data(self.node, start, stop)
            if self._y_is_descending(y):
                if len(y.shape) == 1:
                    y = y[::-1].copy()
                else:
                    y = y[:, ::-1].copy()
                z = z[:, ::-1].copy()
            return x, y, z
        except Exception as e:
            log.error(f"Error getting data for {self.node}: {e}")
            return []


def plot_product(p: Union[SciQLopPlot, SciQLopMultiPlotPanel, SciQLopNDProjectionPlot], product: List[str], **kwargs):
    if isinstance(product, list):
        node = ProductsModel.node(product)
        if node is not None:
            provider = providers.get(node.provider())
            log.debug(f"Provider: {provider}")
            if provider is not None:
                log.debug(f"Parameter type: {node.parameter_type()}")
                if node.parameter_type() in (ParameterType.Scalar, ParameterType.Vector, ParameterType.Multicomponents):
                    callback = _plot_product_callback(provider, node)
                    labels = listify(provider.labels(node))
                    log.debug(f"Building plot for {node.name()} with labels: {labels}, kwargs: {kwargs}")
                    r = p.plot(callback, labels=labels, **kwargs)
                    if hasattr(r, '__iter__'):
                        r[1].set_name(node.name())
                    else:
                        r.set_name(node.name())
                    return r
                elif node.parameter_type() == ParameterType.Spectrogram:
                    callback = _specgram_callback(provider, node)
                    log.debug(f"Building spectrogram plot for {node.name()} with kwargs: {kwargs}")
                    return p.plot(callback, name=node.name(), graph_type=GraphType.ColorMap, y_log_scale=True,
                                  z_log_scale=True, **kwargs)
    log.debug(f"Product not found: {product}")
    return None


def plot_static_data(p: Union[SciQLopPlot, SciQLopMultiPlotPanel, SciQLopNDProjectionPlot], x, y, z=None, **kwargs):
    if z is not None:
        return p.plot(x, y, z, **kwargs)
    else:
        return p.plot(x, y, **kwargs)


def plot_function(p: Union[SciQLopPlot, SciQLopMultiPlotPanel, SciQLopNDProjectionPlot], f, **kwargs):
    return p.plot(f, **kwargs)


class ProductDnDCallback(PlotDragNDropCallback):
    def __init__(self, parent):
        super().__init__(PRODUCT_LIST_MIME_TYPE, True, parent)

    def call(self, plot, mime_data: QMimeData):
        log.debug(f"ProductDnDCallback: {mime_data}")
        for product in decode_mime(mime_data):
            log.debug(f"ProductDnDCallback: {product}")
            node = ProductsModel.node(product)
            if node is not None:
                log.debug(f"ProductDnDCallback: {node}")
                plot_product(plot, product)


class TimeRangeDnDCallback(PlotDragNDropCallback):
    def __init__(self, parent):
        super().__init__(TIME_RANGE_MIME_TYPE, False, parent)

    def call(self, plot, mime_data: QMimeData):
        time_range = decode_mime(mime_data)
        plot.time_axis().set_range(time_range)


class TimeSyncPanel(SciQLopMultiPlotPanel):

    def __init__(self, name: str, parent=None, time_range: Optional[TimeRange] = None):
        super().__init__(parent, synchronize_x=False, synchronize_time=True)
        self.setObjectName(name)
        self.setWindowTitle(name)
        self._parent_node = None
        self._product_plot_callback = ProductDnDCallback(self)
        self._time_range_plot_callback = TimeRangeDnDCallback(self)
        self.add_accepted_mime_type(self._product_plot_callback)
        self.add_accepted_mime_type(self._time_range_plot_callback)
        self.set_color_palette(make_color_list(Palette()))
        if time_range is not None:
            self.time_range = time_range

    @SciQLopProperty(TimeRange)
    def time_range(self) -> TimeRange:
        return self.time_axis_range()

    @time_range.setter
    def time_range(self, time_range: TimeRange):
        self.set_time_axis_range(time_range)

    def __repr__(self):
        return f"TimeSyncPanel: {self.name}"

    @SciQLopProperty(str)
    def icon(self) -> str:
        return "QCP"
