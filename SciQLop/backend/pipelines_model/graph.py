import numpy as np
from PySide6.QtCore import QObject, Signal, Slot
from speasy.products import SpeasyVariable
from abc import ABC, abstractmethod, ABCMeta
from typing import List, Protocol, runtime_checkable, Optional, Any, Dict

from SciQLop.backend import TimeRange
from SciQLop.backend.enums import GraphType, graph_type_repr
from SciQLop.backend.pipelines_model.data_provider import DataProvider
from SciQLop.backend.pipelines_model.data_pipeline import DataPipeline
from SciQLop.backend import sciqlop_logging
from SciQLop.backend.products_model.product_node import ProductNode
from SciQLop.inspector.inspector import register_inspector, Inspector
from SciQLop.inspector.node import Node

log = sciqlop_logging.getLogger(__name__)


class Graph(QObject):
    time_range_changed = Signal(TimeRange)
    _graph = None
    please_delete_me = Signal(object)

    def __init__(self, parent, graph_type: GraphType, provider: DataProvider,
                 product: ProductNode):
        QObject.__init__(self, parent=parent)
        self.setObjectName(graph_type_repr(graph_type))
        self.pipeline = DataPipeline(parent=self, provider=provider, product=product, time_range=parent.time_range)
        self.pipeline.please_delete_me.connect(self.delete)
        self.time_range_changed.connect(self.pipeline.get_data)
        self._graph_type = graph_type
        self._data_order = provider.data_order
        self._product = product

    @property
    def data_order(self):
        return self._data_order

    @property
    def graph(self):
        return self._graph

    @graph.setter
    def graph(self, graph):
        if self._graph:
            raise ValueError("Graph object already set")
        self._graph = graph
        if hasattr(self._graph, "destroyed"):
            self._graph.destroyed.connect(self._graph_destroyed)
        if hasattr(self._graph, "please_delete_me"):
            self._graph.please_delete_me.connect(lambda x: x.deleteLater())

    @property
    def parent_plot(self):
        return self.parent()

    @property
    def graph_type(self) -> GraphType:
        return self._graph_type

    def plot(self, data: SpeasyVariable):
        pass

    def plot_xy(self, x: np.ndarray, y: np.ndarray):
        pass

    @Slot()
    def _close_pipeline(self):
        if self.pipeline:
            self.time_range_changed.disconnect()
            self.pipeline.please_delete_me.disconnect()
            self.pipeline.deleteLater()
            self.pipeline = None

    def _close_graph(self):
        if self._graph:
            # self._graph.destroyed.disconnect()
            if hasattr(self._graph, "deleteLater"):
                self._graph.deleteLater()
        self._graph = None

    @Slot()
    def _graph_destroyed(self):
        self._graph = None
        self.please_delete_me.emit(self)

    def close(self):
        self._close_pipeline()
        self._close_graph()
        self.setParent(None)

    @property
    def icon(self) -> str:
        return ""

    @property
    def name(self) -> str:
        return self.objectName()

    @name.setter
    def name(self, new_name: str):
        self.setObjectName(new_name)

    def delete(self):
        self.close()
        self.deleteLater()

    def __del__(self):
        log.debug(f"Dtor {self.__class__.__name__}: {id(self):08x}")


@register_inspector(Graph)
class GraphInspector(Inspector):
    @staticmethod
    def build_node(obj: Graph, parent: Optional[Node] = None, children: Optional[List[Node]] = None) -> Optional[Node]:
        return Node(name=obj.name, bound_object=obj, icon=obj.icon, children=children, parent=parent)

    @staticmethod
    def list_children(obj: Graph) -> List[Any]:
        return [obj.pipeline]

    @staticmethod
    def child(obj: Graph, name: str) -> Optional[Any]:
        if name == obj.pipeline.name:
            return obj.pipeline
        return None
