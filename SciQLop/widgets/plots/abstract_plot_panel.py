from typing import List, Type
from typing import Protocol, runtime_checkable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QScrollArea, QVBoxLayout

from SciQLop.backend.pipelines_model.base import PipelineModelItem
from ...backend import sciqlop_logging

log = sciqlop_logging.getLogger(__name__)


@runtime_checkable
class PlotPanel(PipelineModelItem, Protocol):
    pass


class MetaPlotPanel(type(QScrollArea), type(PlotPanel)):
    pass


class PanelContainer(QWidget):
    plot_list_changed = Signal()

    def __init__(self, plot_type: Type, parent=None):
        QWidget.__init__(self, parent=parent)
        self._plot_type = plot_type
        self.setLayout(QVBoxLayout(self))
        self.setContentsMargins(0, 0, 0, 0)
        self.layout().setContentsMargins(0, 0, 0, 0)

    def indexOf(self, widget: QWidget):
        return self.layout().indexOf(widget)

    def add_widget(self, widget: QWidget, index: int):
        self.layout().insertWidget(index, widget)
        if isinstance(widget, self._plot_type):
            widget.destroyed.connect(self.plot_list_changed)
            self.plot_list_changed.emit()

    def count(self) -> int:
        return self.layout().count()

    def remove_plot(self, plot: QWidget):
        self.layout().removeWidget(plot)

    @property
    def plots(self) -> List[PlotPanel]:
        return list(filter(lambda w: isinstance(w, self._plot_type),
                           map(lambda i: self.layout().itemAt(i).widget(), range(self.layout().count()))))
