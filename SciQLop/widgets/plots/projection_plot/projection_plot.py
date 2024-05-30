from typing import List, Optional, Any

from SciQLop.backend.models import products
from PySide6.QtCore import QMimeData, Qt, QMargins, Signal, Slot
from PySide6.QtGui import QColorConstants, QColor, QMouseEvent
from PySide6.QtWidgets import QHBoxLayout, QFrame, QWidget, QLabel
from SciQLopPlots import SciQLopPlot, QCustomPlot, QCP, QCPAxisTickerDateTime, QCPAxis, QCPLegend, \
    QCPAbstractLegendItem, \
    QCPMarginGroup, \
    QCPColorScale, SciQLopCurve, SciQLopGraph
from seaborn import color_palette
from SciQLop.backend.pipelines_model.data_provider import DataProvider, providers
from SciQLop.backend.pipelines_model.graph import Graph
from SciQLop.backend.enums import ParameterType, DataOrder
from SciQLop.backend.property import SciQLopProperty
from SciQLop.backend import TimeRange, Product
from SciQLop.widgets.drag_and_drop import DropHandler, DropHelper
from SciQLop.mime import decode_mime
from SciQLop.mime.types import PRODUCT_LIST_MIME_TYPE, TIME_RANGE_MIME_TYPE
from .trajectory_graph import TrajectoryGraph, ModelGraph
from SciQLop.inspector.inspector import register_inspector, Inspector
from SciQLop.inspector.node import Node
from SciQLop.widgets.plots.abstract_plot import Plot, MetaPlot


def _to_qcolor(r: float, g: float, b: float):
    return QColor(int(r * 255), int(g * 255), int(b * 255))


def _configure_plot(plot: SciQLopPlot):
    plot.setPlottingHint(QCP.phFastPolylines, True)
    plot.setInteractions(
        QCP.iRangeDrag | QCP.iRangeZoom | QCP.iSelectPlottables | QCP.iSelectAxes | QCP.iSelectLegend | QCP.iSelectItems)
    plot.legend.setVisible(True)
    plot.legend.setSelectableParts(QCPLegend.SelectablePart.spItems)
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


class ProjectionPlot(QFrame, Plot, metaclass=MetaPlot):
    time_range_changed = Signal(TimeRange)
    graph_list_changed = Signal()

    def __init__(self, parent: Optional[QWidget] = None, count: int = 3):
        super().__init__(parent)
        self.setLayout(QHBoxLayout())
        self._plots: List[SciQLopPlot] = []
        self._count = count
        self.setMinimumHeight(80)
        self._drop_helper = DropHelper(widget=self,
                                       handlers=[
                                           DropHandler(mime_type=PRODUCT_LIST_MIME_TYPE,
                                                       callback=self._plot_from_mime_data),
                                           DropHandler(mime_type=TIME_RANGE_MIME_TYPE,
                                                       callback=self._set_time_range)])

        self._palette = color_palette()
        self._palette_index = 0
        for i in range(count):
            plot = SciQLopPlot()
            _configure_plot(plot)
            self._plots.append(plot)
            self.layout().addWidget(plot)

        self._time_range = TimeRange(0., 0.)

    def _plot_from_mime_data(self, mime_data: QMimeData) -> bool:
        products: List[Product] = decode_mime(mime_data)
        for product in products:
            self.plot(product)
        return True

    def _set_time_range(self, mime_data: QMimeData) -> bool:
        self.time_range = decode_mime(mime_data, [TIME_RANGE_MIME_TYPE])
        return True

    def plot(self, product: Product or str):
        if type(product) is str:
            product = products.product(product)
        if product:
            if product.parameter_type is ParameterType.VECTOR:
                self._add_trajectory_graph(providers[product.provider], product,
                                           components=product.metadata.get('components') or [
                                               product.name])
            self.graph_list_changed.emit()

    def plot_model(self, product: Product or str, label: Optional[str] = None):
        if type(product) is str:
            product = products.product(product)
        if product:
            if product.parameter_type is ParameterType.VECTOR:
                self._add_model_graph(providers[product.provider], product,
                                      components=product.metadata.get('components') or [
                                          product.name], label=label)
            self.graph_list_changed.emit()

    def _add_trajectory_graph(self, provider: DataProvider, product: Product, components: List[str]):
        sqp_graphs = [
            SciQLopCurve(plot, plot.xAxis, plot.yAxis,
                         SciQLopGraph.DataOrder.xFirst if provider.data_order == DataOrder.X_FIRST else SciQLopGraph.DataOrder.yFirst)
            for plot in self._plots
        ]
        graph = TrajectoryGraph(parent=self,
                                sciqlop_graphs=sqp_graphs,
                                provider=provider, product=product)
        self.time_range_changed.connect(graph.time_range_changed)

    def _add_model_graph(self, provider: DataProvider, product: Product, components: List[str],
                         label: Optional[str] = None):
        sqp_graphs = [
            SciQLopCurve(plot, plot.xAxis, plot.yAxis,
                         SciQLopGraph.DataOrder.xFirst if provider.data_order == DataOrder.X_FIRST else SciQLopGraph.DataOrder.yFirst)
            for plot in self._plots
        ]
        graph = ModelGraph(parent=self,
                           sciqlop_graphs=sqp_graphs,
                           provider=provider, product=product, label=label)
        self.time_range_changed.connect(graph.time_range_changed)

    @SciQLopProperty(TimeRange)
    def time_range(self) -> TimeRange:
        return self._time_range

    @time_range.setter
    def time_range(self, time_range: TimeRange):
        self._time_range = time_range
        self.time_range_changed.emit(time_range)

    def replot(self, refresh_priority=QCustomPlot.rpQueuedReplot):
        for p in self._plots:
            p.replot(refresh_priority)

    @Slot(TimeRange)
    def set_time_range(self, time_range: TimeRange):
        self.time_range = time_range

    @SciQLopProperty(str)
    def icon(self) -> str:
        return ""

    @SciQLopProperty(str)
    def name(self) -> str:
        return self.objectName()

    @name.setter
    def name(self, new_name: str):
        self.setObjectName(new_name)

    def generate_colors(self, count: int) -> List[QColor]:
        index = self._palette_index
        self._palette_index += count
        return [
            _to_qcolor(*self._palette[(index + i) % len(self._palette)]) for i in range(count)
        ]

    @property
    def graphs(self) -> List[Graph]:
        return list(filter(lambda n: isinstance(n, Graph), self.children()))


@register_inspector(ProjectionPlot)
class ProjectionPlotInspector(Inspector):

    @staticmethod
    def build_node(obj: Any, parent: Optional[Node] = None, children: Optional[List[Node]] = None) -> Optional[Node]:
        assert isinstance(obj, ProjectionPlot)
        node = Node(name=obj.name, bound_object=obj, icon=obj.icon, children=children, parent=parent)
        obj.graph_list_changed.connect(node.changed)
        return node

    @staticmethod
    def list_children(obj: Any) -> List[Any]:
        return obj.graphs

    @staticmethod
    def child(obj: Any, name: str) -> Optional[Any]:
        return next(filter(lambda p: p.name == name, obj.graphs), None)
