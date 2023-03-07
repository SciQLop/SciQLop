from typing import List

from PySide6.QtCore import QMimeData, Qt, QMargins, Signal
from PySide6.QtGui import QColorConstants, QColor, QMouseEvent
from PySide6.QtWidgets import QVBoxLayout, QFrame
from SciQLopPlots import QCustomPlot, QCP, QCPAxisTickerDateTime, QCPLegend, QCPAbstractLegendItem, QCPMarginGroup, \
    QCPColorScale
from seaborn import color_palette

from SciQLop.backend.models import products
from SciQLop.backend.pipelines_model.data_provider import DataProvider
from SciQLop.backend.pipelines_model.data_provider import providers
from SciQLop.backend.pipelines_model.plot import Plot as _Plot
from SciQLop.backend.products_model.product_node import ProductNode
from .colormap_graph import ColorMapGraph
from .line_graph import LineGraph
from ..drag_and_drop import DropHandler, DropHelper
from ...backend import Product
from ...backend import TimeRange
from ...backend.enums import ParameterType
from ...mime import decode_mime
from ...mime.types import PRODUCT_LIST_MIME_TYPE, TIME_RANGE_MIME_TYPE


def _to_qcolor(r: float, g: float, b: float):
    return QColor(int(r * 255), int(g * 255), int(b * 255))


def _configure_plot(plot: QCustomPlot):
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


class TimeSeriesPlot(QFrame, _Plot):
    time_range_changed = Signal(TimeRange)
    _time_range: TimeRange = TimeRange(0., 0.)

    def __init__(self, parent=None):
        super(TimeSeriesPlot, self).__init__(parent)
        _Plot.__init__(self, f"Plot", parent)
        self._plot = QCustomPlot(self)
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

    def addSciQLopGraph(self, x_axis, y_axis, labels, data_order):
        return self._plot.addSciQLopGraph(x_axis, y_axis, labels, data_order)

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
        return TimeRange(self.xAxis.range().lower, self.xAxis.range().upper)

    @time_range.setter
    def time_range(self, time_range: TimeRange):
        if self._time_range != time_range:
            print("Setting xAxis range")
            self.xAxis.setRange(time_range.start, time_range.stop)
            self.replot(QCustomPlot.rpQueuedReplot)

    def plot(self, product: Product or str):
        if type(product) is str:
            product = products.product(product)
        if product.parameter_type in (ParameterType.VECTOR, ParameterType.MULTICOMPONENT, ParameterType.SCALAR):
            self.add_multi_line_graph(providers[product.provider], product,
                                      components=product.metadata.get('components') or [product.name])
        elif product.parameter_type == ParameterType.SPECTROGRAM:
            self.add_colormap_graph(providers[product.provider], product)

    def add_multi_line_graph(self, provider: DataProvider, product: ProductNode, components: List[str]):
        graph = LineGraph(parent=self, provider=provider, product=product)
        self.xAxis.rangeChanged.connect(lambda r: graph.xRangeChanged.emit(TimeRange(r.lower, r.upper)))
        return graph
        # self._pipeline.append(PlotPipeline(graph=graph, provider=provider, product=product, time_range=self.time_range))

    def add_colormap_graph(self, provider: DataProvider, product: ProductNode):
        graph = ColorMapGraph(parent=self, provider=provider, product=product)
        self.xAxis.rangeChanged.connect(lambda r: graph.xRangeChanged.emit(TimeRange(r.lower, r.upper)))
        return graph
        # self._pipeline.append(PlotPipeline(graph=graph, provider=provider, product=product, time_range=self.time_range))

    def remove_graph(self, graph):
        self._plot.removeGraph(graph)

    def select(self):
        self.setStyleSheet("border: 3px dashed blue;")

    def unselect(self):
        self.setStyleSheet("")

    def delete(self):
        _Plot.delete(self)
        self.close()
        self.deleteLater()
