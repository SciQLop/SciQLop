from typing import List
import SciQLopPlots
from PySide6.QtCore import QMimeData
from PySide6.QtGui import QColorConstants, QColor

from .drag_and_drop import DropHandler, DropHelper
from ..backend.products_model import Product, ParameterType
from ..backend.plot_pipeline import PlotPipeline
from ..backend.data_provider import DataProvider
from ..backend.data_provider import providers
from ..backend import TimeRange
from ..mime import decode_mime
from ..mime.types import PRODUCT_LIST_MIME_TYPE, TIME_RANGE_MIME_TYPE
from seaborn import color_palette


def _to_qcolor(r: float, g: float, b: float):
    return QColor(int(r * 255), int(g * 255), int(b * 255))


class Plot(SciQLopPlots.PlotWidget):
    def __init__(self, parent=None):
        SciQLopPlots.PlotWidget.__init__(self, parent)
        self.setMinimumHeight(300)
        self._drop_helper = DropHelper(widget=self,
                                       handlers=[
                                           DropHandler(mime_type=PRODUCT_LIST_MIME_TYPE,
                                                       callback=self._plot),
                                           DropHandler(mime_type=TIME_RANGE_MIME_TYPE,
                                                       callback=self._set_time_range)])
        self._pipeline: List[PlotPipeline] = []
        self._palette = color_palette()
        self._palette_index = 0

    def _generate_colors(self, count: int) -> List[QColor]:
        index = self._palette_index
        self._palette_index += count
        return [
            _to_qcolor(*self._palette[(index + i) % len(self._palette)]) for i in range(count)
        ]

    def _plot(self, mime_data: QMimeData) -> bool:
        products: List[Product] = decode_mime(mime_data)
        for product in products:
            self.plot(product)
        return True

    def _set_time_range(self, mime_data: QMimeData) -> bool:
        self.set_time_range(decode_mime(mime_data, [TIME_RANGE_MIME_TYPE]))
        return True

    def set_time_range(self, time_range: TimeRange):
        self.setXRange(time_range.to_sciqlopplots_range())

    def plot(self, product: Product):
        if product.parameter_type in (ParameterType.VECTOR, ParameterType.MULTICOMPONENT):
            self.add_multi_line_graph(providers[product.provider], product.uid,
                                      line_count=int(product.metadata['components']))
        elif product.parameter_type == ParameterType.SCALAR:
            self.add_line_graph(providers[product.provider], product.uid)

    def add_line_graph(self, provider: DataProvider, product: str):
        graph = self.addLineGraph(self._generate_colors(1)[0])
        pipeline = PlotPipeline(graph=graph, provider=provider, product=product, time_range=self.xRange())
        self._pipeline.append(pipeline)

    def add_multi_line_graph(self, provider: DataProvider, product: str, line_count: int):
        graph = self.addMultiLineGraph(self._generate_colors(line_count))
        pipeline = PlotPipeline(graph=graph, provider=provider, product=product, time_range=self.xRange())
        self._pipeline.append(pipeline)
