from datetime import datetime, time
from typing import Optional, List
from PySide6.QtCore import QMimeData, Signal
from PySide6.QtWidgets import QWidget, QScrollArea, QVBoxLayout

from ...mime import decode_mime
from ...mime.types import PRODUCT_LIST_MIME_TYPE
from ..drag_and_drop import DropHandler, DropHelper, PlaceHolderManager
from ...backend.products_model import Product
from .plot import TimeSeriesPlot
from ...backend import TimeRange


class _TimeSyncPanelContainer(QWidget):
    def __init__(self, parent=None):
        QWidget.__init__(self, parent=parent)
        self._plots = []
        self.setLayout(QVBoxLayout(self))

    def indexOf(self, widget: QWidget):
        return self.layout().indexOf(widget)

    def add_widget(self, widget: QWidget, index: int):
        self.layout().insertWidget(index, widget)
        if isinstance(widget, TimeSeriesPlot):
            self._plots.append(widget)

    def count(self) -> int:
        return self.layout().count()

    @property
    def plots(self) -> List[TimeSeriesPlot]:
        return self._plots


class TimeSyncPanel(QScrollArea):
    time_range_changed = Signal(TimeRange)
    _time_range: TimeRange = TimeRange(0., 0.)

    def __init__(self, name: str, parent=None, time_range: Optional[TimeRange] = None):
        QScrollArea.__init__(self, parent)
        self._name = name
        self._plot_container = _TimeSyncPanelContainer(self)
        self.setWidget(self._plot_container)
        self.setWidgetResizable(True)
        self.time_range = time_range or TimeRange(datetime.utcnow().timestamp(), datetime.utcnow().timestamp())
        self._drop_helper = DropHelper(widget=self,
                                       handlers=[
                                           DropHandler(mime_type=PRODUCT_LIST_MIME_TYPE,
                                                       callback=self._plot)])
        self._place_holder_manager = PlaceHolderManager(self,
                                                        handlers=[DropHandler(mime_type=PRODUCT_LIST_MIME_TYPE,
                                                                              callback=self._insert_plots)])

    @property
    def name(self) -> str:
        return self._name

    @property
    def time_range(self) -> TimeRange:
        return self._time_range

    @time_range.setter
    def time_range(self, time_range: TimeRange):
        if self._time_range != time_range:
            self._time_range = time_range
            print(time_range)
            for p in self._plot_container.plots:
                print(p)
                p.time_range = time_range
            self.time_range_changed.emit(time_range)

    def __repr__(self):
        return f"TimeSyncPanel: {self._name}"

    @property
    def place_holder_manager(self):
        return self._place_holder_manager

    def indexOf(self, widget: QWidget):
        return self._plot_container.indexOf(widget)

    def _insert_plots(self, mime_data: QMimeData, placeholder: QWidget) -> bool:
        assert mime_data.hasFormat(PRODUCT_LIST_MIME_TYPE)
        products = decode_mime(mime_data, preferred_formats=[PRODUCT_LIST_MIME_TYPE])
        self.plot(products, self.indexOf(placeholder))
        return True

    def _plot(self, mime_data: QMimeData) -> bool:
        assert mime_data.hasFormat(PRODUCT_LIST_MIME_TYPE)
        products = decode_mime(mime_data, preferred_formats=[PRODUCT_LIST_MIME_TYPE])
        self.plot(products, -1)
        return True

    def plot(self, products: List[Product], index: Optional[int] = None):
        for product in products:
            p = TimeSeriesPlot(self)
            p.time_range_changed.connect(lambda time_range: TimeSyncPanel.time_range.fset(self, time_range))
            p.time_range = self.time_range
            self._plot_container.add_widget(p, -1 if index is None else index)
            p.plot(product)
            p.parent_place_holder_manager = self._place_holder_manager
            if index is not None:
                index += 1

    def insertWidget(self, index: int, widget: QWidget or TimeSeriesPlot):
        self._plot_container.add_widget(widget, index)

    def count(self) -> int:
        return self._plot_container.count()
