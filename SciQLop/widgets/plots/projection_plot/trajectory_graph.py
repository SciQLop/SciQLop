import numpy as np
from typing import List, Optional
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPen
from SciQLopPlots import SciQLopGraph, QCPSelectionDecorator
from speasy.products import SpeasyVariable

from SciQLop.backend.pipelines_model.data_provider import DataProvider
from SciQLop.backend.pipelines_model.graph import Graph
from SciQLop.backend.products_model.product_node import ProductNode
from SciQLop.backend import sciqlop_logging
from SciQLop.backend.enums import GraphType

log = sciqlop_logging.getLogger(__name__)


class _MultiGraph(QObject):
    please_delete_me = Signal(object)

    def __init__(self, parent, graphs: List[SciQLopGraph]):
        super().__init__(parent)
        self._graphs = graphs
        for g in graphs:
            if hasattr(g, "destroyed"):
                g.destroyed.connect(lambda x: self.please_delete_me.emit(self))
        self.setup = False

    @property
    def graphs(self) -> List[SciQLopGraph]:
        return self._graphs


class TrajectoryGraph(Graph):
    def __init__(self, parent, sciqlop_graphs: List[SciQLopGraph], provider: DataProvider, product: ProductNode,
                 label: Optional[str] = None):
        Graph.__init__(self, parent=parent, graph_type=GraphType.MultiLines, provider=provider, product=product)
        assert len(sciqlop_graphs) == 3
        self.graph = _MultiGraph(parent, sciqlop_graphs)
        self.pipeline.plot.connect(self.plot)
        self.pipeline.get_data(parent.time_range)
        self._p_count = len(sciqlop_graphs)
        self._label = label

    def _configure_graph(self, label: str):
        color = self.parent().generate_colors(1)[0]
        if self._label is not None:
            label = self._label
        for graph in self.graph.graphs:
            graph.create_graphs([label])
            g = graph.graphAt(0)
            g.setPen(QPen(color))
            selection_decorator = g.selectionDecorator()
            selection_decorator.setPen(QPen(color, selection_decorator.pen().width()))
            g.addToLegend()
        self.graph.setup = True

    def plot(self, v: SpeasyVariable):
        if self.graph and v is not None:
            if not self.graph.setup:
                self._configure_graph(v.name)

            values = v.values
            if values.dtype != np.float64:
                values = values.astype(np.float64)
            for i, graph in enumerate(self.graph.graphs):
                x = values[:, i]
                y = values[:, (i + 1) % self._p_count]
                graph.setData(x.copy(), y.copy())

            self.graph.graphs[0].setData(values[:, 0].copy(), values[:, 1].copy())
            self.graph.graphs[1].setData(values[:, 1].copy(), values[:, 2].copy())
            self.graph.graphs[2].setData(values[:, 0].copy(), values[:, 2].copy())

    def __del__(self):
        log.debug(f"Dtor {self.__class__.__name__}: {id(self):08x}")


class ModelGraph(TrajectoryGraph):
    def __init__(self, parent, sciqlop_graphs: List[SciQLopGraph], provider: DataProvider, product: ProductNode,
                 label: Optional[str] = None):
        super().__init__(parent, sciqlop_graphs, provider, product, label=label)

    def plot(self, v: SpeasyVariable):
        if self.graph and v is not None:
            if not self.graph.setup:
                self._configure_graph(v.name)

            values = v.values
            if values.dtype != np.float64:
                values = values.astype(np.float64)
            self.graph.graphs[0].setData(values[:, 0].copy(), values[:, 1].copy())
            self.graph.graphs[1].setData(values[:, 2].copy(), values[:, 3].copy())
            self.graph.graphs[2].setData(values[:, 4].copy(), values[:, 5].copy())
