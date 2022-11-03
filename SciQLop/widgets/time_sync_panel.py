from typing import Optional, List
from PySide6.QtCore import QMimeData
from PySide6.QtWidgets import QWidget

import SciQLopPlots

from ..mime import decode_mime
from ..mime.types import PRODUCT_LIST_MIME_TYPE
from .drag_and_drop import DropHandler, DropHelper, PlaceHolderManager
from ..backend.products_model import Product
from .plot import Plot
from ..backend import TimeRange


class TimeSyncPanel(SciQLopPlots.SyncPanel):
    def __init__(self, name: str, parent=None, time_range: Optional[TimeRange] = None):
        SciQLopPlots.SyncPanel.__init__(self, parent)
        self._name = name
        self._drop_helper = DropHelper(widget=self,
                                       handlers=[
                                           DropHandler(mime_type=PRODUCT_LIST_MIME_TYPE,
                                                       callback=self._plot)])
        self._place_holder_manager = PlaceHolderManager(self,
                                                        handlers=[DropHandler(mime_type=PRODUCT_LIST_MIME_TYPE,
                                                                              callback=self._insert_plots)])
        if time_range is not None:
            self.setXRange(time_range.to_sciqlopplots_range())

    @property
    def name(self) -> str:
        return self._name

    def __repr__(self):
        return f"TimeSyncPanel: {self._name}"

    @property
    def place_holder_manager(self):
        return self._place_holder_manager

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
            p = Plot(self)
            self.addPlot(p, -1 if index is None else index)
            p.plot(product)
            p.parent_place_holder_manager = self._place_holder_manager
            if index is not None:
                index += 1

    def insertWidget(self, index: int, widget: QWidget or Plot):
        if isinstance(widget, Plot):
            self.addPlot(widget, index)
        else:
            self.widget().layout().insertWidget(index, widget)
