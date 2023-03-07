import numpy as np
from PySide6.QtCore import QMetaObject, Qt, Slot
from PySide6.QtGui import QPen
from SciQLopPlots import SciQLopGraph
from speasy.products import SpeasyVariable

from SciQLop.backend.pipelines_model.data_provider import DataProvider
from SciQLop.backend.pipelines_model.graph import Graph
from SciQLop.backend.products_model.product_node import ProductNode
from ...backend.enums import DataOrder
from ...backend.enums import GraphType


class LineGraph(Graph):
    def __init__(self, parent, provider: DataProvider, product: ProductNode):
        Graph.__init__(self, parent=parent, graph_type=GraphType.MultiLines, provider=provider, product=product)
        self._graph = None
        self._last_value = None

    @Slot()
    def _create_graph(self):
        if self._last_value is not None:
            if self._graph is None:
                self._graph = self.parent_plot.addSciQLopGraph(self.parent_plot.xAxis, self.parent_plot.yAxis,
                                                               self._last_value.columns,
                                                               SciQLopGraph.DataOrder.xFirst if self.data_order == DataOrder.X_FIRST else SciQLopGraph.DataOrder.yFirst)

                for color, index in zip(self.parent_plot.generate_colors(len(self._last_value.columns)),
                                        range(len(self._last_value.columns))):
                    self.graphAt(index).setPen(QPen(color))
                    self.graphAt(index).addToLegend()
            self.plot(self._last_value)

    def plot(self, v: SpeasyVariable):
        self._last_value = v
        if self._graph is None:
            QMetaObject.invokeMethod(self, "_create_graph", Qt.QueuedConnection)
        else:
            t = v.time.astype(np.timedelta64) / np.timedelta64(1, 's')
            if v.values.dtype != np.float64:
                self._graph.setData(t, v.values.astype(np.float64))
            else:
                self._graph.setData(t, v.values)

    def graphAt(self, index: int):
        return self._graph.graphAt(index)

    def delete(self):
        super().delete()
