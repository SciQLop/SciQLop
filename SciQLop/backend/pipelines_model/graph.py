from PySide6.QtCore import QObject, Signal
from speasy.products import SpeasyVariable

from SciQLop.backend import TimeRange
from SciQLop.backend.enums import GraphType, graph_type_repr
from SciQLop.backend.models import pipelines
from SciQLop.backend.pipelines_model.base.pipeline_node import QObjectPipelineModelItem, \
    QObjectPipelineModelItemMeta
from SciQLop.backend.pipelines_model.data_provider import DataProvider
from .data_pipeline import DataPipeline
from .. import logging
from ..products_model.product_node import ProductNode

log = logging.getLogger(__name__)


class Graph(QObject, QObjectPipelineModelItem, metaclass=QObjectPipelineModelItemMeta):
    xRangeChanged = Signal(TimeRange)
    _graph = None

    def __init__(self, parent, graph_type: GraphType, provider: DataProvider,
                 product: ProductNode):
        QObject.__init__(self, parent=parent)
        QObjectPipelineModelItem.__init__(self, name=graph_type_repr(graph_type))
        pipeline = DataPipeline(parent=self, provider=provider, product=product, time_range=parent.time_range)
        pipeline.destroyed.connect(self.delete_node)
        self.xRangeChanged.connect(pipeline.get_data)
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

    def delete_node(self):
        with pipelines.model_update_ctx():
            self.xRangeChanged.disconnect()
            if self._graph is not None:
                self._graph.deleteLater()
            self._parent_plot.replot()
            self.deleteLater()
