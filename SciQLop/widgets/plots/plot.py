from typing import List

from PySide6.QtCore import QMimeData, Qt, QMargins, Signal
from PySide6.QtGui import QColorConstants, QColor, QMouseEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QFrame

from SciQLopPlots import QCustomPlot, QCP, QCPAxisTickerDateTime, QCPLegend, QCPAbstractLegendItem
from seaborn import color_palette

from SciQLop.backend.models import products
from SciQLop.backend.pipelines_model.data_provider import DataProvider
from SciQLop.backend.pipelines_model.data_provider import providers
from SciQLop.backend.pipelines_model.plot import Plot as _Plot
from SciQLop.backend.pipelines_model.plot_pipeline import PlotPipeline
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
        self._pipeline: List[PlotPipeline] = []
        self._palette = color_palette()
        self._palette_index = 0
        _configure_plot(self._plot)
        self.setContentsMargins(0, 0, 0, 0)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.xAxis.rangeChanged.connect(lambda range: self.time_range_changed.emit(TimeRange(range.lower, range.upper)))
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

    @property
    def xAxis(self):
        return self._plot.xAxis

    @property
    def yAxis(self):
        return self._plot.yAxis

    def replot(self, refresh_priority):
        return self._plot.replot(refresh_priority)

    def addSciQLopGraph(self, x_axis, y_axis, labels, data_order):
        return self._plot.addSciQLopGraph(x_axis, y_axis, labels, data_order)

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
            self.add_multi_line_graph(providers[product.provider], product.uid,
                                      components=product.metadata.get('components') or [product.name])
        elif product.parameter_type == ParameterType.SPECTROGRAM:
            self.add_colormap_graph(providers[product.provider], product.uid)

    def add_multi_line_graph(self, provider: DataProvider, product: str, components: List[str]):
        graph = LineGraph(self, provider.data_order)
        self.xAxis.rangeChanged.connect(lambda range: graph.xRangeChanged.emit(TimeRange(range.lower, range.upper)))
        self._pipeline.append(PlotPipeline(graph=graph, provider=provider, product=product, time_range=self.time_range))

    def add_colormap_graph(self, provider: DataProvider, product: str):
        graph = ColorMapGraph(self._plot, self._plot.addColorMap(self.xAxis, self.yAxis))
        self.xAxis.rangeChanged.connect(lambda range: graph.xRangeChanged.emit(TimeRange(range.lower, range.upper)))
        self._pipeline.append(PlotPipeline(graph=graph, provider=provider, product=product, time_range=self.time_range))

    def select(self):
        self.setStyleSheet("border: 3px dashed blue;")

    def unselect(self):
        self.setStyleSheet("")

    def delete(self):
        _Plot.delete(self)
        self.close()
        self.deleteLater()
