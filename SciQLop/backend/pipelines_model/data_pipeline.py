from datetime import datetime
from typing import Optional, Callable

from PySide6.QtCore import QObject, QThread, QWaitCondition, QMutex
from speasy.products import SpeasyVariable

from SciQLop.backend import TimeRange
from SciQLop.backend.pipelines_model.base.pipeline_node import QObjectPipelineModelItem, \
    QObjectPipelineModelItemMeta
from SciQLop.backend.pipelines_model.data_provider import DataProvider
from SciQLop.backend.products_model.product_node import ProductNode
from .base import model
from .. import logging

log = logging.getLogger(__name__)


class _DataPipelineWorker(QThread):

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
        self._data_order = provider.data_order
        self.moveToThread(self)
        self.start()

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


class _DataPipelineController(QThread):
    def __init__(self, data_callback: Callable[[SpeasyVariable], None], product: ProductNode, time_range: TimeRange):
        QThread.__init__(self)
        self.setTerminationEnabled(True)
        self.wait_condition = QWaitCondition()
        self.next_range: Optional[TimeRange] = time_range
        self.current_range: Optional[TimeRange] = None
        self._worker = _DataPipelineWorker(data_callback, product, time_range)
        self.moveToThread(self)
        self.start()

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


class DataPipeline(QObject, QObjectPipelineModelItem, metaclass=QObjectPipelineModelItemMeta):
    def __init__(self, parent: QObject, provider: DataProvider, product: ProductNode, time_range: TimeRange):
        QObject.__init__(self, parent)
        with model.model_update_ctx():
            QObjectPipelineModelItem.__init__(self, name=f"{product.provider}/{product.uid}")
        self._worker = _DataPipelineWorker(parent.plot, provider, product, time_range)
        self._product = product

    @property
    def product(self):
        return self._product

    def __del__(self):
        log.info(f"Dtor {self.__class__.__name__}: {id(self):08x}")
        self._worker.requestInterruption()
        self._worker.wait_condition.wakeAll()
        if not self._worker.wait(1000):
            self._worker.quit()
            self._worker.wait()

    def get_data(self, new_range: TimeRange):
        self._worker.next_range = new_range
        self._worker.wait_condition.wakeOne()
