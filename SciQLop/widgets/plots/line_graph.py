from ...backend.graph import Graph
from ...backend.enums import GraphType
from ...backend.enums import DataOrder
from SciQLopPlots import SciQLopGraph
from PySide6.QtCore import QMetaObject, Qt, Slot
import numpy as np
from speasy.products import SpeasyVariable
from PySide6.QtGui import QPen


class LineGraph(Graph):
    def __init__(self, parent, data_order):
        Graph.__init__(self, parent=parent, graph_type=GraphType.MultiLines, data_order=data_order)
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
