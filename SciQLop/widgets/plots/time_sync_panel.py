import sys
from datetime import datetime
from gc import callbacks
from typing import Optional, List, Any, Union

import numpy as np
from pycrdt import Doc, Map, MapEvent
from PySide6.QtCore import QMimeData, Signal, QMargins
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QScrollArea
from SciQLopPlots import SciQLopMultiPlotPanel, PlotDragNDropCallback, SciQLopPlotInterface, ProductsModel, SciQLopPlot, \
    ParameterType, GraphType, SciQLopNDProjectionPlot, SciQLopPlotRange as TimeRange, PlotType

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


def plot_product(p: Union[SciQLopPlot, SciQLopMultiPlotPanel, SciQLopNDProjectionPlot], product: List[str], shared_panels=None, panel_name=None, **kwargs):
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
                    if shared_panels is not None:
                        try:
                            with shared_panels.doc.transaction(origin="local"):
                                shared_plots = shared_panels[panel_name]
                                shared_plot = shared_plots[p.name]
                                shared_plot["product"] = product
                        except Exception:
                            pass
                    return r
                elif node.parameter_type() == ParameterType.Spectrogram:
                    callback = _specgram_callback(provider, node)
                    log.debug(f"Building spectrogram plot for {node.name()} with kwargs: {kwargs}")
                    return p.plot(callback, name=node.name(), graph_type=GraphType.ColorMap, y_log_scale=True,
                                  z_log_scale=True, **kwargs)
    log.debug(f"Product not found: {product}")
    return None


class ProductDnDCallback(PlotDragNDropCallback):
    def __init__(self, parent):
        super().__init__(PRODUCT_LIST_MIME_TYPE, True, parent)
        self._parent = parent

    def call(self, plot, mime_data: QMimeData):
        log.debug(f"ProductDnDCallback: {mime_data}")
        for product in decode_mime(mime_data):
            log.debug(f"ProductDnDCallback: {product}")
            node = ProductsModel.node(product)
            if node is not None:
                log.debug(f"ProductDnDCallback: {node}")
                plot_product(plot, product, self._parent._shared_panels, self._parent._name)


class TimeRangeDnDCallback(PlotDragNDropCallback):
    def __init__(self, parent):
        super().__init__(TIME_RANGE_MIME_TYPE, False, parent)

    def call(self, plot, mime_data: QMimeData):
        time_range = decode_mime(mime_data)
        plot.time_axis().set_range(time_range)


class TimeSyncPanel(SciQLopMultiPlotPanel):

    def __init__(self, name: str, parent=None, time_range: Optional[TimeRange] = None, shared_panels = None):
        super().__init__(parent, synchronize_x=False, synchronize_time=True)
        self._name = name
        self.setObjectName(name)
        self.setWindowTitle(name)
        self._parent_node = None
        self._product_plot_callback = ProductDnDCallback(self)
        self._time_range_plot_callback = TimeRangeDnDCallback(self)
        self.add_accepted_mime_type(self._product_plot_callback)
        self.add_accepted_mime_type(self._time_range_plot_callback)
        self.set_color_palette(make_color_list(Palette()))
        self._shared_panels = shared_panels
        self._shared_panels.observe_deep(self._shared_panels_changed)
        self.time_range_changed.connect(self._time_range_changed)
        self.plot_added.connect(self._plot_added)
        if time_range is not None:
            self.time_range = time_range

    def _shared_panels_changed(self, events, txn):
        if txn.origin == "local":
            return

        for event in events:
            if not event.path:
                for key1, value1 in event.keys.items():
                    if key1 == self._name:
                        # that's us
                        if value1["action"] == "add":
                            plots = value1["newValue"]
                            for key2, value2 in plots.items():
                                if key2 in ("time_range_start", "time_range_stop"):
                                    time_range_start = plots["time_range_start"]
                                    time_range_stop = plots["time_range_stop"]
                                    self.time_range = TimeRange(time_range_start, time_range_stop)
                                else:
                                    product = value2["product"]
                                    plot_product(self, product, index=0, plot_type=PlotType.TimeSeries)

            elif len(event.path) == 1:
                # an event in a panel, like a new plot
                panel_name = event.path[0]
                if panel_name == self._name:
                    # that's us
                    for key, value in event.keys.items():
                        if key in ("time_range_start", "time_range_stop"):
                            time_range_start = event.target["time_range_start"]
                            time_range_stop = event.target["time_range_stop"]
                            self.time_range = TimeRange(time_range_start, time_range_stop)
                        else:
                            plot = value["newValue"]
                            plot.observe(self._shared_plot_changed)
            elif len(event.path) == 2:
                panel_name = event.path[0]
                if panel_name == self._name:
                    # that's us
                    plot_name = event.path[1]
                    for key, value in event.keys.items():
                        if key == "product":
                            if value["action"] == "add":
                                product = value["newValue"]
                                plot_product(self, product, index=0, plot_type=PlotType.TimeSeries)

    def _plot_added(self, new_plot):
        if new_plot.name != "PlaceHolder":
            try:
                with self._shared_panels.doc.transaction(origin="local"):
                    shared_plots = self._shared_panels[self._name]
                    shared_plot = Map({"name": new_plot.name})
                    shared_plots[new_plot.name] = shared_plot
            except Exception:
                pass

    def _time_range_changed(self, new_time_range):
        # if we are at the origin of a change, break the recursion
        try:
            with self._shared_panels.doc.transaction(origin="local"):
                shared_plots = self._shared_panels[self._name]
                shared_plots["time_range_start"] = new_time_range.start()
                shared_plots["time_range_stop"] = new_time_range.stop()
        except Exception:
            pass

    def _shared_plot_changed(self, event: MapEvent) -> None:
        time_range_start = event.target.get("time_range_start")
        time_range_stop = event.target.get("time_range_stop")
        if time_range_start is not None and time_range_stop is not None:
            self.time_range = TimeRange(time_range_start, time_range_stop)

    @SciQLopProperty(TimeRange)
    def time_range(self) -> TimeRange:
        return self.time_axis_range()

    @time_range.setter
    def time_range(self, time_range: TimeRange):
        # if we are at the origin of a change, break the recursion
        try:
            with self._shared_panels.doc.transaction(origin="local"):
                shared_plots = self._shared_panels[self._name]
                shared_plots["time_range_start"] = time_range.start()
                shared_plots["time_range_stop"] = time_range.stop()
        except Exception:
            pass
        self.set_time_axis_range(time_range)

    def __repr__(self):
        return f"TimeSyncPanel: {self.name}"

    @SciQLopProperty(str)
    def icon(self) -> str:
        return "QCP"
