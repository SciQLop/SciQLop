from typing import List, Type, Any
from typing import Protocol, runtime_checkable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QScrollArea, QVBoxLayout

from ...backend import sciqlop_logging
from ...backend.property import SciQLopProperty

log = sciqlop_logging.getLogger(__name__)


@runtime_checkable
class PlotPanel(Protocol):

    @property
    def graphs(self) -> List[Any]:
        ...

    @property
    def has_colormap(self) -> bool:
        ...


class MetaPlotPanel(type(QScrollArea), type(PlotPanel)):
    pass


class PanelContainer(QWidget):
    plot_list_changed = Signal()

    def __init__(self, plot_type: Type, parent=None, shared_x_axis=False):
        QWidget.__init__(self, parent=parent)
        self._plot_type = plot_type
        self._shared_x_axis = shared_x_axis
        self.setLayout(QVBoxLayout(self))
        self.setContentsMargins(0, 0, 0, 0)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)

    def indexOf(self, widget: QWidget):
        return self.layout().indexOf(widget)

    def _ensure_shared_x_axis(self):
        plots = self.plots
        if len(plots):
            for p in plots[:-1]:
                p: PlotPanel = p
                if hasattr(p, "hide_x_axis"):
                    p.hide_x_axis()
            if hasattr(plots[-1], "show_x_axis"):
                plots[-1].show_x_axis()

    def add_widget(self, widget: QWidget, index: int):
        self.layout().insertWidget(index, widget)
        if isinstance(widget, self._plot_type):
            widget.destroyed.connect(self.plot_list_changed)
            if self._shared_x_axis:
                self._ensure_shared_x_axis()
            self.plot_list_changed.emit()

    def count(self) -> int:
        return self.layout().count()

    def remove_plot(self, plot: QWidget):
        self.layout().removeWidget(plot)

    @SciQLopProperty(list)
    def plots(self) -> List[PlotPanel]:
        return list(filter(lambda w: isinstance(w, self._plot_type),
                           map(lambda i: self.layout().itemAt(i).widget(), range(self.layout().count()))))

    @SciQLopProperty(bool)
    def shared_x_axis(self) -> bool:
        return self._shared_x_axis

    @shared_x_axis.setter
    def shared_x_axis(self, value: bool):
        self._shared_x_axis = value
        if value:
            self._ensure_shared_x_axis()
        else:
            for p in self.plots:
                if hasattr(p, "show_x_axis"):
                    p.show_x_axis()
