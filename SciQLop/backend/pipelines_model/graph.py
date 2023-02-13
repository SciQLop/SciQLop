from PySide6.QtCore import QObject, Signal
from SciQLop.backend import TimeRange
from SciQLop.backend.enums import GraphType, DataOrder
from speasy.products import SpeasyVariable


class Graph(QObject):
    xRangeChanged = Signal(TimeRange)

    def __init__(self, parent, graph_type: GraphType, data_order: DataOrder):
        QObject.__init__(self, parent=parent)
        self._graph_type = graph_type
        self._parent_plot = parent
        self._data_order = data_order

    @property
    def data_order(self):
        return self._data_order

    @property
    def parent_plot(self):
        return self._parent_plot

    @property
    def graph_type(self) -> GraphType:
        return self._graph_type

    def plot(self, data: SpeasyVariable):
        pass
