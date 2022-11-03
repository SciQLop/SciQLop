from datetime import datetime
from .products_model import ProductsModel as _ProductsModel
from SciQLopPlots import axis

products = _ProductsModel()


class TimeRange:
    __slots__ = ["_start", "_stop"]

    def __init__(self, start: datetime, stop: datetime):
        self._start = start
        self._stop = stop

    @property
    def start(self):
        return self._start

    @property
    def stop(self):
        return self._stop

    def to_sciqlopplots_range(self):
        return axis.range(self.start.timestamp(), self.stop.timestamp())
