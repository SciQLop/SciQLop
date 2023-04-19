import numpy as np
from PySide6.QtGui import QPen
from SciQLopPlots import SciQLopGraph
from speasy.products import SpeasyVariable

from SciQLop.backend.pipelines_model.data_provider import DataProvider
from SciQLop.backend.pipelines_model.graph import Graph
from SciQLop.backend.products_model.product_node import ProductNode
from ...backend import logging
from ...backend.enums import GraphType

log = logging.getLogger(__name__)


class LineGraph(Graph):
    def __init__(self, parent, sciqlop_graph: SciQLopGraph, provider: DataProvider, product: ProductNode):
        Graph.__init__(self, parent=parent, graph_type=GraphType.MultiLines, provider=provider, product=product)
        self.graph = sciqlop_graph
        self.pipeline.plot.connect(self.plot)
        self.pipeline.get_data(parent.time_range)

    def _configure_graph(self, labels):
        self.graph.create_graphs(labels)
        for color, index in zip(self.parent().generate_colors(len(labels)), range(len(labels))):
            self.graphAt(index).setPen(QPen(color))
            self.graphAt(index).addToLegend()

    def plot(self, v: SpeasyVariable):
        if self.graph:
            if self.graph.line_count() < len(v.columns):
                self._configure_graph(v.columns)
            t = v.time.astype(np.timedelta64) / np.timedelta64(1, 's')
            if v.values.dtype != np.float64:
                self.graph.setData(t, v.values.astype(np.float64))
            else:
                self.graph.setData(t, v.values)

    def graphAt(self, index: int):
        return self.graph.graphAt(index)

    def close(self):
        super().close()

    def __del__(self):
        log.info(f"Dtor {self.__class__.__name__}: {id(self):08x}")
