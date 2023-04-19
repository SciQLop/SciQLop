from copy import deepcopy
from datetime import datetime
from typing import Optional, Callable, List
from abc import ABC, abstractmethod, ABCMeta

from PySide6.QtCore import QObject, QThread, QWaitCondition, QMutex, Signal
from speasy.products import SpeasyVariable

from SciQLop.backend import TimeRange
from SciQLop.backend.pipelines_model.auto_register import auto_register
from SciQLop.backend.pipelines_model.data_provider import DataProvider
from SciQLop.backend.pipelines_model.base import PipelineModelItem, MetaPipelineModelItem
from SciQLop.backend.pipelines_model.base import model as pipelines_model
from SciQLop.backend.products_model.product_node import ProductNode
from .. import logging

log = logging.getLogger(__name__)


class _DataPipelineWorker(QObject):
    plot = Signal(object)
    _get_data_sig = Signal()

    def __init__(self, provider: DataProvider, product: ProductNode,
                 time_range: TimeRange):
        QObject.__init__(self)
        self.range_mutex = QMutex()
        self.next_range: Optional[TimeRange] = time_range
        self.current_range: Optional[TimeRange] = None
        self.product = product
        self.provider = provider
        self._get_data_sig.connect(self._get_data)
        self._data_order = provider.data_order

    def _get_data(self):
        self.range_mutex.lock()
        next_range = deepcopy(self.next_range)
        self.range_mutex.unlock()
        if next_range != self.current_range:
            data = self.provider.get_data(self.product, datetime.utcfromtimestamp(next_range.start),
                                          datetime.utcfromtimestamp(next_range.stop))
            self.current_range = next_range
            if data is not None:
                self.plot.emit(data)

    def get_data(self, new_range: TimeRange):
        self.range_mutex.lock()
        self.next_range = new_range
        self.range_mutex.unlock()
        self._get_data_sig.emit()

    def __del__(self):
        log.info(f"Dtor {self.__class__.__name__}: {id(self):08x}")


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
        log.info(f"Dtor {self.__class__.__name__}: {id(self):08x}")
        self._worker.requestInterruption()
        self._worker.wait_condition.wakeOne()
        self._worker.wait(1000)

    def run(self):
        mutex = QMutex()
        while not QThread.currentThread().isInterruptionRequested():
            mutex.lock()
            self.wait_condition.wait(mutex, 500.)
            if self.next_range != self._worker.current_range:
                self._worker.next_range = self.next_range
                self._worker.wait_condition.wakeOne()
            mutex.unlock()


@auto_register
class DataPipeline(QObject, PipelineModelItem, metaclass=MetaPipelineModelItem):
    please_delete_me = Signal(object)
    plot = Signal(object)

    def __init__(self, parent: QObject, provider: DataProvider, product: ProductNode, time_range: TimeRange):
        QObject.__init__(self, parent)
        self._worker_thread = QThread(self)
        self.setObjectName(f"{product.provider}/{product.uid}")
        self._worker = _DataPipelineWorker(provider, product, time_range)
        self._worker.moveToThread(self._worker_thread)
        self._worker.plot.connect(self.plot)
        self._worker_thread.start(QThread.Priority.LowPriority)
        self._product = product

    @property
    def product(self):
        return self._product

    def close(self):
        if self._worker_thread:
            self._worker_thread.quit()
            self._worker_thread.wait()
            self._worker_thread.deleteLater()
            self._worker_thread = None

    def __del__(self):
        log.info(f"Dtor {self.__class__.__name__}: {id(self):08x}")
        self.close()

    def get_data(self, new_range: TimeRange):
        if self._worker_thread:
            self._worker.get_data(new_range)

    def __eq__(self, other: 'PipelineModelItem') -> bool:
        return self is other

    @property
    def icon(self) -> str:
        return ""

    @property
    def name(self) -> str:
        return self.objectName()

    @name.setter
    def name(self, new_name: str):
        with pipelines_model.model_update_ctx():
            self.setObjectName(new_name)

    @property
    def parent_node(self) -> 'PipelineModelItem':
        return self.parent()

    @parent_node.setter
    def parent_node(self, parent: 'PipelineModelItem'):
        raise ValueError("Can't reset DataPipeline parent!")

    @property
    def children_nodes(self) -> List['PipelineModelItem']:
        return []

    def remove_children_node(self, node: 'PipelineModelItem'):
        pass

    def add_children_node(self, node: 'PipelineModelItem'):
        pass

    def select(self):
        pass

    def unselect(self):
        pass

    def delete_node(self):
        self.close()
