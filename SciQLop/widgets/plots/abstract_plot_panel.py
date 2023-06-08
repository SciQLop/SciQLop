from typing import List, Type
from typing import Protocol, runtime_checkable

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QScrollArea, QVBoxLayout, QSplitter

from SciQLop.backend.pipelines_model.base import PipelineModelItem
from ...backend import logging

log = logging.getLogger(__name__)


@runtime_checkable
class PlotPanel(PipelineModelItem, Protocol):
    pass


class MetaPlotPanel(type(QScrollArea), type(PlotPanel)):
    pass


class PanelContainer(QSplitter):
    plot_list_changed = Signal()

    def __init__(self, plot_type: Type, parent=None):
        QSplitter.__init__(self, orientation=Qt.Vertical, parent=parent)
        self._plot_type = plot_type
        self.setContentsMargins(0, 0, 0, 0)
        self.setMinimumHeight(100)

    def indexOf(self, widget: QWidget):
        return QSplitter.indexOf(self, widget)

    def add_widget(self, widget: QWidget, index: int):
        self.insertWidget(index, widget)
        if isinstance(widget, self._plot_type):
            widget.destroyed.connect(self.plot_list_changed)
            self.plot_list_changed.emit()
        self.setMinimumHeight(self.count() * 100)

    def count(self) -> int:
        return QSplitter.count(self)

    def remove_plot(self, plot: QWidget):
        self.layout().removeWidget(plot)
        self.setMinimumHeight(self.count() * 100)

    def plot(self, index) -> PlotPanel:
        return self.widget(index)

    @property
    def plots(self) -> List[PlotPanel]:
        return list(filter(lambda w: isinstance(w, self._plot_type),
                           map(lambda i: self.plot(i), range(self.count()))))
