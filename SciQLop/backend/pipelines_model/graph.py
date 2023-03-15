from typing import Optional

from PySide6.QtCore import QObject, Signal
from speasy.products import SpeasyVariable

from SciQLop.backend import TimeRange
from SciQLop.backend.enums import GraphType, graph_type_repr
from SciQLop.backend.pipelines_model.base.pipeline_model_item import PipelineModelItem
from SciQLop.backend.pipelines_model.data_provider import DataProvider
from .data_pipeline import DataPipeline
from ..products_model.product_node import ProductNode


class Graph(QObject, PipelineModelItem):
    xRangeChanged = Signal(TimeRange)
    _pipeline: Optional[DataPipeline] = None
    _graph = None

    def __init__(self, parent, graph_type: GraphType, provider: DataProvider,
                 product: ProductNode):
        QObject.__init__(self, parent=parent)
        PipelineModelItem.__init__(self, graph_type_repr(graph_type), parent)
        self._pipeline = DataPipeline(parent=self, provider=provider, product=product, time_range=parent.time_range)
        self.xRangeChanged.connect(self._pipeline.get_data)
        self._graph_type = graph_type
        self._parent_plot = parent
        self._data_order = provider.data_order
        self._product = product

    @property
    def data_order(self):
        return self._data_order

    @property
    def graph(self):
        return self._graph

    @property
    def parent_plot(self):
        return self._parent_plot

    @property
    def graph_type(self) -> GraphType:
        return self._graph_type

    def plot(self, data: SpeasyVariable):
        pass

    def delete(self):
        super().delete()
        if self._pipeline is not None:
            del self._pipeline
        if self._graph is not None:
            del self._graph
        self._parent_plot.replot()
