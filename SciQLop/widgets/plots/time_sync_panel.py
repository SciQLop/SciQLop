from datetime import datetime
from typing import Optional, List

from PySide6.QtCore import QMimeData, Signal
from PySide6.QtWidgets import QWidget, QScrollArea, QVBoxLayout
from SciQLopPlots import QCPMarginGroup

from SciQLop.backend.pipelines_model.base.pipeline_model_item import QWidgetPipelineModelItem, \
    QWidgetPipelineModelItemMeta
from .plot import TimeSeriesPlot
from ..drag_and_drop import DropHandler, DropHelper, PlaceHolderManager
from ...backend import Product
from ...backend import TimeRange
from ...backend import listify
from ...backend.models import pipelines
from ...mime import decode_mime
from ...mime.types import PRODUCT_LIST_MIME_TYPE


class _TimeSyncPanelContainer(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)
        self._margin_group = QCPMarginGroup(None)
        self.setLayout(QVBoxLayout(self))
        self.setContentsMargins(0, 0, 0, 0)
        self.layout().setContentsMargins(0, 0, 0, 0)

    def indexOf(self, widget: QWidget):
        return self.layout().indexOf(widget)

    def add_widget(self, widget: QWidget, index: int):
        self.layout().insertWidget(index, widget)
        if isinstance(widget, TimeSeriesPlot):
            widget.set_margin_group(self._margin_group)

    def count(self) -> int:
        return self.layout().count()

    @property
    def plots(self) -> List[TimeSeriesPlot]:
        return list(filter(lambda w: isinstance(w, TimeSeriesPlot),
                           map(lambda i: self.layout().itemAt(i).widget(), range(self.layout().count()))))


class TimeSyncPanel(QScrollArea, QWidgetPipelineModelItem, metaclass=QWidgetPipelineModelItemMeta):
    time_range_changed = Signal(TimeRange)
    _time_range: TimeRange = TimeRange(0., 0.)
    delete_me = Signal()

    def __init__(self, name: str, parent=None, time_range: Optional[TimeRange] = None):
        QScrollArea.__init__(self, parent)
        QWidgetPipelineModelItem.__init__(self, name)
        pipelines.add_add_panel(self)
        self.setContentsMargins(0, 0, 0, 0)
        self._name = name
        self._plot_container = _TimeSyncPanelContainer(self)
        self.setWidget(self._plot_container)
        self.setWidgetResizable(True)
        self.time_range = time_range or TimeRange(datetime.utcnow().timestamp(), datetime.utcnow().timestamp())
        self._drop_helper = DropHelper(widget=self,
                                       handlers=[
                                           DropHandler(mime_type=PRODUCT_LIST_MIME_TYPE,
                                                       callback=self._plot_mime)])
        self._place_holder_manager = PlaceHolderManager(self,
                                                        handlers=[DropHandler(mime_type=PRODUCT_LIST_MIME_TYPE,
                                                                              callback=self._insert_plots)])

    @property
    def parent_node(self: QWidget) -> 'PipelineModelItem':
        return pipelines.root_node

    @parent_node.setter
    def parent_node(self, parent):
        pass

    @property
    def time_range(self) -> TimeRange:
        return self._time_range

    @time_range.setter
    def time_range(self, time_range: TimeRange):
        if self._time_range != time_range:
            self._time_range = time_range
            for p in self._plot_container.plots:
                p.time_range = time_range
            self.time_range_changed.emit(time_range)

    def __repr__(self):
        return f"TimeSyncPanel: {self._name}"

    @property
    def place_holder_manager(self):
        return self._place_holder_manager

    def indexOf(self, widget: QWidget):
        return self._plot_container.indexOf(widget)

    def index_of(self, child):
        return self._plot_container.indexOf(child)

    def child_at(self, row: int):
        if 0 <= row < len(self._plot_container.plots):
            return self._plot_container.plots[row]
        return None

    @property
    def children_nodes(self) -> List[TimeSeriesPlot]:
        return self._plot_container.plots

    def _insert_plots(self, mime_data: QMimeData, placeholder: QWidget) -> bool:
        assert mime_data.hasFormat(PRODUCT_LIST_MIME_TYPE)
        products = decode_mime(mime_data, preferred_formats=[PRODUCT_LIST_MIME_TYPE])
        self.plot(products, self.indexOf(placeholder))
        return True

    def _plot_mime(self, mime_data: QMimeData, index=None) -> bool:
        assert mime_data.hasFormat(PRODUCT_LIST_MIME_TYPE)
        products = decode_mime(mime_data, preferred_formats=[PRODUCT_LIST_MIME_TYPE])
        self.plot(products, -1)
        return True

    def _plot(self, product: Product or str, index: int) -> bool:
        if product is not None:
            p = TimeSeriesPlot(self)
            p.time_range_changed.connect(lambda time_range: TimeSyncPanel.time_range.fset(self, time_range))
            p.time_range = self.time_range
            self._plot_container.add_widget(p, index)
            p.plot(product)
            p.parent_place_holder_manager = self._place_holder_manager
            return True
        return False

    def plot(self, products: List[Product or str] or Product or str, index: Optional[int] = None):
        products = listify(products)
        indexes = [-1] * len(products) if index is None else range(index, index + len(products))
        list(map(lambda p_i: self._plot(*p_i), zip(products, indexes)))

    def insertWidget(self, index: int, widget: QWidget or TimeSeriesPlot):
        self._plot_container.add_widget(widget, index)

    def count(self) -> int:
        return self._plot_container.count()

    def __getitem__(self, index: int) -> TimeSeriesPlot:
        plots = filter(lambda w: isinstance(w, TimeSeriesPlot), self._plot_container.plots)
        return list(plots)[index]

    def select(self):
        self.setStyleSheet("border: 3px dashed blue")

    def unselect(self):
        self.setStyleSheet("")

    def delete_node(self):
        with pipelines.model_update_ctx():
            self.parent_node.remove_child(self)
            children = self.children_nodes
            for child in children:
                child.delete_node()
            super(TimeSyncPanel, self).delete_node()
