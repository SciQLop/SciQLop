from datetime import datetime
from typing import Optional, List, Any

import numpy as np
from PySide6.QtCore import QMimeData, Signal, QMargins
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QScrollArea
from SciQLopPlots import QCustomPlot, QCPMarginGroup, QCPAxisRect, QCP
from SciQLop.backend.icons import register_icon
from .abstract_plot_panel import MetaPlotPanel, PlotPanel, PanelContainer
from .abstract_plot import Plot
from .time_series_plot import TimeSeriesPlot
from ..drag_and_drop import DropHandler, DropHelper, PlaceHolderManager
from ...backend import Product
from ...backend import TimeRange
from ...backend import listify
from ...backend import sciqlop_logging
from ...backend.property import SciQLopProperty
from ...mime import decode_mime
from ...mime.types import PRODUCT_LIST_MIME_TYPE
from ...inspector.inspector import register_inspector, Inspector
from ...inspector.node import Node

log = sciqlop_logging.getLogger(__name__)


class TSPanelContainer(PanelContainer):
    def __init__(self, parent=None, shared_x_axis=False):
        PanelContainer.__init__(self, Plot, parent=parent, shared_x_axis=shared_x_axis)

    def add_widget(self, widget: QWidget, index: int):
        PanelContainer.add_widget(self, widget, index)

    def update_margins(self):
        max_left_margin = 0
        max_right_pos = 1e9
        for p in self.plots:
            if hasattr(p, 'plot_instance'):
                ar = p.plot_instance.axisRect()
                left_margin = ar.calculateAutoMargin(QCP.MarginSide.msLeft)
                if p.has_colormap:
                    cmw = p.colorBar.outerRect().width()
                    cmw += ar.calculateAutoMargin(QCP.MarginSide.msRight)
                else:
                    cmw = 0
                max_left_margin = max(max_left_margin, left_margin)
                max_right_pos = min(max_right_pos, p.width() - cmw)

        for p in self.plots:
            if hasattr(p, 'plot_instance'):
                p: TimeSeriesPlot = p

                ar = p.plot_instance.axisRect()
                new_right_margin = p.width() - max_right_pos
                if p.has_colormap:
                    new_right_margin -= p.colorBar.outerRect().width()
                else:
                    new_right_margin += p.plot_instance.plotLayout().columnSpacing()
                new_margins = QMargins(max_left_margin, ar.calculateAutoMargin(QCP.MarginSide.msTop), new_right_margin,
                                       ar.calculateAutoMargin(QCP.MarginSide.msTop))
                if ar.minimumMargins() != new_margins:
                    ar.setMinimumMargins(QMargins(max_left_margin, ar.calculateAutoMargin(QCP.MarginSide.msTop),
                                                  new_right_margin,
                                                  ar.calculateAutoMargin(QCP.MarginSide.msTop)))
                    p.replot()


register_icon("QCP", QIcon("://icons/QCP.png"))


class TimeSyncPanel(QScrollArea, PlotPanel, metaclass=MetaPlotPanel):
    time_range_changed = Signal(TimeRange)
    _time_range: TimeRange = TimeRange(0., 0.)
    plot_list_changed = Signal()
    delete_me = Signal()

    def __init__(self, name: str, parent=None, time_range: Optional[TimeRange] = None):
        QScrollArea.__init__(self, parent)
        self.setObjectName(name)
        self.setWindowTitle(name)
        self.setContentsMargins(0, 0, 0, 0)
        self._name = name
        self._plot_container = TSPanelContainer(parent=self, shared_x_axis=True)
        self.setWidget(self._plot_container)
        self.setWidgetResizable(True)
        self.time_range = time_range or TimeRange(datetime.utcnow().timestamp(), datetime.utcnow().timestamp())
        self._drop_helper = DropHelper(widget=self,
                                       handlers=[
                                           DropHandler(mime_type=PRODUCT_LIST_MIME_TYPE,
                                                       callback=self._plot_mime)])
        self._place_holder_manager = PlaceHolderManager(self,
                                                        handlers=[DropHandler(mime_type=PRODUCT_LIST_MIME_TYPE,
                                                                              callback=self._insert_plots)])

        self._plot_container.plot_list_changed.connect(self.plot_list_changed)
        self._parent_node = None
        self._share_x_axis = True

    def link_panel(self, panel: 'TimeSyncPanel'):
        panel.time_range_changed.connect(self.set_time_range)
        self.time_range_changed.connect(panel.set_time_range)

    def unlink_panel(self, panel: 'TimeSyncPanel'):
        panel.time_range_changed.disconnect(self.set_time_range)
        self.time_range_changed.disconnect(panel.set_time_range)

    def set_time_range(self, time_range: TimeRange):
        self.time_range = time_range

    @SciQLopProperty(bool)
    def share_x_axis(self) -> bool:
        return self._plot_container._shared_x_axis

    @share_x_axis.setter
    def share_x_axis(self, value: bool):
        if self._share_x_axis != value:
            self._share_x_axis = value
            self._plot_container.share_x_axis = value

    @SciQLopProperty(TimeRange)
    def time_range(self) -> TimeRange:
        return self._time_range

    @time_range.setter
    def time_range(self, time_range: TimeRange):
        if self._time_range != time_range:
            self._time_range = time_range
            for p in self.plots:
                p.time_range = time_range
            self.time_range_changed.emit(time_range)
            self._plot_container.update_margins()

    @SciQLopProperty(str)
    def name(self) -> str:
        return self.objectName()

    @name.setter
    def name(self, new_name: str):
        self.setObjectName(new_name)

    def __repr__(self):
        return f"TimeSyncPanel: {self._name}"

    @property
    def place_holder_manager(self):
        return self._place_holder_manager

    def indexOf(self, widget: QWidget):
        return self._plot_container.indexOf(widget)

    def index_of(self, child):
        return self._plot_container.indexOf(child)

    def child_at(self, row: int):
        if 0 <= row < len(self._plot_container.plots):
            return self._plot_container.plots[row]
        return None

    @property
    def plots(self) -> List[TimeSeriesPlot]:
        return self._plot_container.plots

    def _insert_plots(self, mime_data: QMimeData, placeholder: QWidget) -> bool:
        assert mime_data.hasFormat(PRODUCT_LIST_MIME_TYPE)
        products = decode_mime(mime_data, preferred_formats=[PRODUCT_LIST_MIME_TYPE])
        self.plot(products, self.indexOf(placeholder))
        return True

    def _plot_mime(self, mime_data: QMimeData, index=None) -> bool:
        assert mime_data.hasFormat(PRODUCT_LIST_MIME_TYPE)
        products = decode_mime(mime_data, preferred_formats=[PRODUCT_LIST_MIME_TYPE])
        self.plot(products, -1)
        return True

    def _plot(self, product: Product or str, index: int) -> bool:
        if product is not None:
            p = TimeSeriesPlot(parent=self)
            p.time_range_changed.connect(lambda time_range: TimeSyncPanel.time_range.fset(self, time_range))
            p.vertical_axis_range_changed.connect(lambda l, h: self._plot_container.update_margins())
            p.time_range = self.time_range
            self._plot_container.add_widget(p, index)
            p.parent_node = self
            p.plot(product)
            p.parent_place_holder_manager = self._place_holder_manager
            return True
        return False

    def plot(self, products: List[Product or str] or Product or str, index: Optional[int] = None):
        products = listify(products)
        indexes = [-1] * len(products) if index is None else range(index, index + len(products))
        list(map(lambda p_i: self._plot(*p_i), zip(products, indexes)))

    def update_margins(self):
        self._plot_container.update_margins()

    def replot(self, refresh_priority=QCustomPlot.rpQueuedReplot):
        for p in self.plots:
            p.replot(refresh_priority)

    def insertWidget(self, index: int, widget: QWidget or TimeSeriesPlot):
        self._plot_container.add_widget(widget, index)

    def count(self) -> int:
        return self._plot_container.count()

    def __getitem__(self, index: int) -> TimeSeriesPlot:
        plots = filter(lambda w: isinstance(w, TimeSeriesPlot), self._plot_container.plots)
        return list(plots)[index]

    def select(self):
        self.setStyleSheet("border: 3px dashed blue")

    def unselect(self):
        self.setStyleSheet("")

    def __del__(self):
        log.debug("deleting TimeSyncPanel")

    @SciQLopProperty(str)
    def icon(self) -> str:
        return "QCP"

    def delete(self):
        self.delete_me.emit()


@register_inspector(TimeSyncPanel)
class TimeSyncPanelInspector(Inspector):

    @staticmethod
    def build_node(obj: Any, parent: Optional[Node] = None, children: Optional[List[Node]] = None) -> Optional[Node]:
        assert isinstance(obj, TimeSyncPanel)
        node = Node(name=obj.name, bound_object=obj, icon=obj.icon, children=children, parent=parent)
        obj.plot_list_changed.connect(node.changed)
        return node

    @staticmethod
    def list_children(obj: Any) -> List[Any]:
        return obj.plots

    @staticmethod
    def child(obj: Any, name: str) -> Optional[Any]:
        return next(filter(lambda p: p.name == name, obj.plots), None)
