from PySide6.QtCore import QObject, Signal, Slot
from speasy.products import SpeasyVariable
from abc import ABC, abstractmethod, ABCMeta
from typing import List, Protocol, runtime_checkable

from SciQLop.backend import TimeRange
from SciQLop.backend.enums import GraphType, graph_type_repr
from SciQLop.backend.pipelines_model.auto_register import auto_register
from SciQLop.backend.pipelines_model.base.pipeline_node import PipelineModelItem, MetaPipelineModelItem
from SciQLop.backend.models import pipelines
from SciQLop.backend.pipelines_model.data_provider import DataProvider
from .data_pipeline import DataPipeline
from .. import logging
from ..products_model.product_node import ProductNode

log = logging.getLogger(__name__)


@auto_register
class Graph(QObject, PipelineModelItem, metaclass=MetaPipelineModelItem):
    xRangeChanged = Signal(TimeRange)
    _graph = None
    please_delete_me = Signal(object)

    def __init__(self, parent, graph_type: GraphType, provider: DataProvider,
                 product: ProductNode):
        QObject.__init__(self, parent=parent)
        self.setObjectName(graph_type_repr(graph_type))
        self.pipeline = DataPipeline(parent=self, provider=provider, product=product, time_range=parent.time_range)
        self.pipeline.please_delete_me.connect(self._close_pipeline)
        # pipeline.destroyed.connect(self.delete_node)
        self.xRangeChanged.connect(self.pipeline.get_data)
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
        self._graph.destroyed.connect(self._graph_destroyed)

    @property
    def parent_plot(self):
        return self.parent()

    @property
    def graph_type(self) -> GraphType:
        return self._graph_type

    def plot(self, data: SpeasyVariable):
        pass

    @Slot()
    def _close_pipeline(self):
        if self.pipeline:
            self.xRangeChanged.disconnect()
            self.pipeline.please_delete_me.disconnect()
            self.pipeline.close()
            self.pipeline = None

    def _close_graph(self):
        if self._graph:
            self._graph.destroyed.disconnect()
            self._graph.deleteLater()
        self._graph = None

    @Slot()
    def _graph_destroyed(self):
        self._graph = None
        self.please_delete_me.emit(self)

    def close(self):
        with pipelines.model_update_ctx():
            self._close_pipeline()
            self._close_graph()
            self.setParent(None)

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
        with pipelines.model_update_ctx():
            self.setObjectName(new_name)

    @property
    def parent_node(self) -> 'PipelineModelItem':
        return self.parent()

    @parent_node.setter
    def parent_node(self, parent: 'PipelineModelItem'):
        raise ValueError("Can't reset Graph parent!")

    @property
    def children_nodes(self) -> List['PipelineModelItem']:
        return [self.pipeline]

    def remove_children_node(self, node: 'PipelineModelItem'):
        raise RuntimeError("This method should not be called")

    def add_children_node(self, node: 'PipelineModelItem'):
        pass

    def select(self):
        pass

    def unselect(self):
        pass

    def delete_node(self):
        self.close()
