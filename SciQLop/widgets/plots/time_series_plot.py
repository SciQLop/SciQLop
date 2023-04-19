from typing import List
from abc import abstractmethod

from PySide6.QtCore import QMimeData, Qt, QMargins, Signal
from PySide6.QtGui import QColorConstants, QColor, QMouseEvent
from PySide6.QtWidgets import QVBoxLayout, QFrame
from SciQLopPlots import SciQLopPlot, QCustomPlot, QCP, QCPAxisTickerDateTime, QCPLegend, QCPAbstractLegendItem, \
    QCPMarginGroup, \
    QCPColorScale, SciQLopGraph, SciQLopColorMap
from seaborn import color_palette

from SciQLop.backend.models import products
from SciQLop.backend.pipelines_model.auto_register import auto_register
from SciQLop.backend.pipelines_model.data_provider import DataProvider
from SciQLop.backend.pipelines_model.data_provider import providers
from SciQLop.backend.pipelines_model.graph import Graph
from SciQLop.backend.products_model.product_node import ProductNode
from SciQLop.backend.pipelines_model.base import PipelineModelItem
from SciQLop.backend.pipelines_model.base import model as pipelines_model
from .colormap_graph import ColorMapGraph
from .line_graph import LineGraph
from ..drag_and_drop import DropHandler, DropHelper
from ...backend import Product
from ...backend import TimeRange
from ...backend.enums import ParameterType, DataOrder
from ...backend.unique_names import make_simple_incr_name
from ...mime import decode_mime
from ...mime.types import PRODUCT_LIST_MIME_TYPE, TIME_RANGE_MIME_TYPE


def _to_qcolor(r: float, g: float, b: float):
    return QColor(int(r * 255), int(g * 255), int(b * 255))


def _configure_plot(plot: SciQLopPlot):
    plot.setPlottingHint(QCP.phFastPolylines, True)
    plot.setInteractions(
        QCP.iRangeDrag | QCP.iRangeZoom | QCP.iSelectPlottables | QCP.iSelectAxes | QCP.iSelectLegend | QCP.iSelectItems)
    plot.legend.setVisible(True)
    plot.legend.setSelectableParts(QCPLegend.SelectablePart.spItems)
    date_ticker = QCPAxisTickerDateTime()
    date_ticker.setDateTimeFormat("yyyy/MM/dd \nhh:mm:ss")
    date_ticker.setDateTimeSpec(Qt.UTC)
    plot.xAxis.setTicker(date_ticker)
    plot.plotLayout().setMargins(QMargins(0, 0, 0, 0))
    plot.plotLayout().setRowSpacing(0)
    for rect in plot.axisRects():
        rect.setMargins(QMargins(0, 0, 0, 0))

    plot.setContentsMargins(0, 0, 0, 0)
    layout = plot.layout()
    if layout:
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)
    plot.setAutoAddPlottableToLegend(False)


class MetaTimeSeriesPlot(type(QFrame), type(PipelineModelItem)):
    pass


@auto_register
class TimeSeriesPlot(QFrame, PipelineModelItem, metaclass=MetaTimeSeriesPlot):
    time_range_changed = Signal(TimeRange)
    _time_range: TimeRange = TimeRange(0., 0.)

    def __init__(self, parent=None):
        QFrame.__init__(self, parent=parent)
        self.setObjectName(make_simple_incr_name(base="Plot"))
        self._plot = SciQLopPlot(self)
        self.setLayout(QVBoxLayout())
        self.layout().addWidget(self._plot)
        self.setMinimumHeight(300)
        self._drop_helper = DropHelper(widget=self,
                                       handlers=[
                                           DropHandler(mime_type=PRODUCT_LIST_MIME_TYPE,
                                                       callback=self._plot_from_mime_data),
                                           DropHandler(mime_type=TIME_RANGE_MIME_TYPE,
                                                       callback=self._set_time_range)])

        self._palette = color_palette()
        self._palette_index = 0
        _configure_plot(self._plot)
        self.setContentsMargins(0, 0, 0, 0)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.xAxis.rangeChanged.connect(lambda range: self.time_range_changed.emit(TimeRange(range.lower, range.upper)))
        self._plot.selectionChangedByUser.connect(self._update_selection)
        self._plot.legendDoubleClick.connect(self._hide_graph)
        self._parent_node = None

    def _hide_graph(self, legend: QCPLegend, item: QCPAbstractLegendItem, event: QMouseEvent):
        item.plottable().setVisible(not item.plottable().visible())
        if item.plottable().visible():
            item.setTextColor(QColorConstants.Black)
            item.setSelectedTextColor(QColorConstants.Black)
        else:
            item.setTextColor(QColorConstants.Gray)
            item.setSelectedTextColor(QColorConstants.Gray)
        self.replot(QCustomPlot.rpQueuedReplot)

    def _update_selection(self):
        for i in range(self._plot.graphCount()):
            graph = self._plot.graph(i)
            item = self._plot.legend.itemWithPlottable(graph)
            if item.selected() or graph.selected():
                item.setSelected(True)
                graph.setSelected(True)

    def set_margin_group(self, margin_group: QCPMarginGroup):
        self._plot.axisRect(0).setMarginGroup(QCP.msLeft, margin_group)

    @property
    def plot_instance(self):
        return self._plot

    @property
    def xAxis(self):
        return self._plot.xAxis

    @property
    def xAxis2(self):
        return self._plot.xAxis2

    @property
    def yAxis(self):
        return self._plot.yAxis

    @property
    def yAxis2(self):
        return self._plot.yAxis2

    def replot(self, refresh_priority=QCustomPlot.rpQueuedReplot):
        return self._plot.replot(refresh_priority)

    def addSciQLopGraph(self, x_axis, y_axis, data_order, labels=None):
        if labels is not None:
            return SciQLopGraph(self._plot, x_axis, y_axis, labels, data_order)
        else:
            return SciQLopGraph(self._plot, x_axis, y_axis, data_order)

    def addSciQLopColorMap(self, x_axis, y_axis, label, with_color_scale=True):
        colormap = self._plot.addSciQLopColorMap(x_axis, y_axis, label)
        colormap.colorMap().setLayer(self._plot.layer("background"))
        if with_color_scale:
            color_scale = QCPColorScale(self._plot)
            self._plot.plotLayout().addElement(0, 1, color_scale)
            return color_scale, colormap
        else:
            return colormap

    def graph_at(self, index):
        return self._plot.graphAt(index)

    def generate_colors(self, count: int) -> List[QColor]:
        index = self._palette_index
        self._palette_index += count
        return [
            _to_qcolor(*self._palette[(index + i) % len(self._palette)]) for i in range(count)
        ]

    def _plot_from_mime_data(self, mime_data: QMimeData) -> bool:
        products: List[Product] = decode_mime(mime_data)
        for product in products:
            self.plot(product)
        return True

    def _set_time_range(self, mime_data: QMimeData) -> bool:
        self.time_range = decode_mime(mime_data, [TIME_RANGE_MIME_TYPE])
        return True

    @property
    def time_range(self) -> TimeRange:
        return TimeRange.from_qcprange(self.xAxis.range())

    @time_range.setter
    def time_range(self, time_range: TimeRange):
        if self._time_range != time_range:
            self.xAxis.setRange(time_range.start, time_range.stop)
            self.replot(QCustomPlot.rpQueuedReplot)

    def plot(self, product: Product or str):
        if type(product) is str:
            product = products.product(product)
        if product:
            if product.parameter_type in (ParameterType.VECTOR, ParameterType.MULTICOMPONENT, ParameterType.SCALAR):
                self._add_multi_line_graph(providers[product.provider], product,
                                           components=product.metadata.get('components') or [
                                               product.name])
            elif product.parameter_type == ParameterType.SPECTROGRAM and not self.has_colormap:
                self._add_colormap_graph(providers[product.provider], product)

    def _register_new_graph(self, graph):
        self.time_range_changed.connect(graph.xRangeChanged)

    def _add_multi_line_graph(self, provider: DataProvider, product: ProductNode, components: List[str]):
        graph = LineGraph(parent=self, sciqlop_graph=self.addSciQLopGraph(self.xAxis, self.yAxis,
                                                                          SciQLopGraph.DataOrder.xFirst if provider.data_order == DataOrder.X_FIRST else SciQLopGraph.DataOrder.yFirst),
                          provider=provider, product=product)
        self._register_new_graph(graph)

    def _add_colormap_graph(self, provider: DataProvider, product: ProductNode):
        graph = ColorMapGraph(parent=self, provider=provider, product=product)
        self._register_new_graph(graph)

    def remove_graph(self, graph):
        with pipelines_model.model_update_ctx():
            if isinstance(graph, SciQLopGraph) or isinstance(graph, SciQLopColorMap):
                for g in self._graphs:
                    if g.graph is graph:
                        graph = g
            graph.deleteLater()

    def select(self):
        self.setStyleSheet("border: 3px dashed blue;")

    def unselect(self):
        self.setStyleSheet("")

    @property
    def has_colormap(self):
        return len(list(filter(lambda c: isinstance(c, ColorMapGraph), self.children_nodes))) > 0

    def __eq__(self, other: 'PipelineModelItem') -> bool:
        return self is other

    @property
    def icon(self) -> str:
        return ""

    @property
    def name(self) -> str:
        return self.objectName()

    @name.setter
    def name(self, new_name: str):
        with pipelines_model.model_update_ctx():
            self.setObjectName(new_name)

    @property
    def parent_node(self) -> 'PipelineModelItem':
        return self._parent_node

    @parent_node.setter
    def parent_node(self, parent: 'PipelineModelItem'):
        with pipelines_model.model_update_ctx():
            if self._parent_node is not None:
                self._parent_node.remove_children_node(self)
            self._parent_node = parent
            if parent is not None:
                parent.add_children_node(self)

    @property
    def children_nodes(self) -> List['PipelineModelItem']:
        return list(filter(lambda n: isinstance(n, Graph), self.children()))

    def remove_children_node(self, node: 'PipelineModelItem'):
        self.remove_graph(node)

    def add_children_node(self, node: 'PipelineModelItem'):
        pass

    def delete_node(self):
        self.close()
