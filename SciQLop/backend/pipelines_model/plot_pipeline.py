from datetime import datetime
from typing import Optional, Callable

from PySide6.QtCore import QObject, QThread, QWaitCondition, QMutex
from speasy.products import SpeasyVariable

from SciQLop.backend import TimeRange
from SciQLop.backend.pipelines_model.base.pipeline_model_item import PipelineModelItem
from SciQLop.backend.pipelines_model.data_provider import DataProvider
from SciQLop.backend.products_model.product_node import ProductNode

from .base import model


class _PlotPipelineWorker(QThread):

    def __init__(self, data_callback: Callable[[SpeasyVariable], None], provider: DataProvider, product: ProductNode,
                 time_range: TimeRange):
        QThread.__init__(self)
        self.setTerminationEnabled(True)
        self.wait_condition = QWaitCondition()
        self.next_range: Optional[TimeRange] = time_range
        self.current_range: Optional[TimeRange] = None
        self.product = product
        self.provider = provider
        self.data_callback = data_callback
        self.moveToThread(self)
        self.start()
        self._data_order = provider.data_order

    def get_data(self, new_range: TimeRange) -> Optional[SpeasyVariable]:
        return self.provider.get_data(self.product, datetime.utcfromtimestamp(new_range.start),
                                      datetime.utcfromtimestamp(new_range.stop))

    def get_data_task(self, new_range: TimeRange):
        data = self.get_data(new_range)
        if data is not None:
            self.data_callback(data)
        self.current_range = new_range

    def run(self):
        mutex = QMutex()
        while not self.isInterruptionRequested():
            while self.next_range != self.current_range:
                try:
                    self.get_data_task(self.next_range)
                except Exception as e:
                    print(e)
            self.wait_condition.wait(mutex)


class _PlotPipelineController(QThread):
    def __init__(self, data_callback: Callable[[SpeasyVariable], None], product: ProductNode, time_range: TimeRange):
        QThread.__init__(self)
        self.setTerminationEnabled(True)
        self.moveToThread(self)
        self.wait_condition = QWaitCondition()
        self.next_range: Optional[TimeRange] = time_range
        self.current_range: Optional[TimeRange] = None
        self.start()
        self._worker = _PlotPipelineWorker(data_callback, product, time_range)

    def __del__(self):
        self._worker.requestInterruption()
        self._worker.wait_condition.wakeAll()
        if not self._worker.wait(1000):
            self._worker.quit()
            self._worker.wait()

    def run(self):
        mutex = QMutex()
        while not self.isInterruptionRequested():
            if self.next_range != self._worker.current_range:
                self._worker.next_range = self.next_range
                self._worker.wait_condition.wakeOne()
            self.wait_condition.wait(mutex)


class PlotPipeline(QObject, PipelineModelItem):
    def __init__(self, parent: QObject, provider: DataProvider, product: ProductNode, time_range: TimeRange):
        QObject.__init__(self, parent)
        with model.model_update_ctx():
            PipelineModelItem.__init__(self, f"{product.provider}/{product}", parent)
        self._worker = _PlotPipelineWorker(parent.plot, provider, product, time_range)
        self._product = product

    @property
    def product(self):
        return self._product

    def __del__(self):
        self._worker.requestInterruption()
        self._worker.wait_condition.wakeAll()
        if not self._worker.wait(1000):
            self._worker.quit()
            self._worker.wait()

    def get_data(self, new_range: TimeRange):
        self._worker.next_range = new_range
        self._worker.wait_condition.wakeOne()
