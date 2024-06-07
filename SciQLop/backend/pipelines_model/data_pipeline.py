from copy import deepcopy
from datetime import datetime
from typing import Optional, Callable, List, Any, Dict, Protocol, runtime_checkable
from abc import ABC, abstractmethod, ABCMeta

from PySide6.QtCore import QObject, QThread, QWaitCondition, QMutex, Signal, QTimer
from speasy.products import SpeasyVariable

from SciQLop.backend import TimeRange
from SciQLop.backend.pipelines_model.data_provider import DataProvider
from SciQLop.backend.products_model.product_node import ProductNode
from .. import sciqlop_logging
from ...inspector.inspector import register_inspector, Inspector
from ...inspector.node import Node

log = sciqlop_logging.getLogger(__name__)


class _DataPipelineWorker(QObject):
    plot = Signal(object)
    _get_data_sig = Signal()
    _last_data: Optional[SpeasyVariable] = None

    def __init__(self, provider: DataProvider, product: ProductNode,
                 time_range: TimeRange):
        QObject.__init__(self)
        self.range_mutex = QMutex()
        self._deferred_get_data_timer = QTimer()
        self._deferred_get_data_timer.setSingleShot(True)
        self._deferred_get_data_timer.timeout.connect(self._get_data)
        self.next_range: Optional[TimeRange] = time_range
        self.current_range: Optional[TimeRange] = None
        self.product = product
        self.provider = provider
        self._get_data_sig.connect(self._get_data)
        self._data_order = provider.data_order

    def _get_data(self):
        try:
            self.range_mutex.lock()
            next_range = deepcopy(self.next_range)
            self.range_mutex.unlock()
            if next_range != self.current_range:
                if self.provider.cacheable and self._last_data is not None and self.current_range.contains(next_range):
                    self.plot.emit(self._last_data[next_range.start: next_range.stop])
                else:
                    self._last_data = self.provider.get_data(self.product, datetime.utcfromtimestamp(next_range.start),
                                                             datetime.utcfromtimestamp(next_range.stop))
                    self.current_range = next_range
                    if self._last_data is not None:
                        self.plot.emit(self._last_data)
        except Exception as e:
            print(e)

    def get_data(self, new_range: TimeRange):
        self.range_mutex.lock()
        self.next_range = new_range
        self.range_mutex.unlock()
        self._deferred_get_data_timer.start(100)

    def __del__(self):
        log.debug(f"Dtor {self.__class__.__name__}: {id(self):08x}")


class DataPipeline(QObject):
    please_delete_me = Signal(object)
    plot = Signal(object)

    def __init__(self, parent: QObject, provider: DataProvider, product: ProductNode, time_range: TimeRange):
        QObject.__init__(self, parent)
        self._worker_thread = QThread(self)
        self._worker_thread.setObjectName("DataPipelineWorkerThread")
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
            self._worker_thread.finished.connect(self._worker_thread.deleteLater)
            self._worker_thread.quit()
            self._worker_thread.wait()
            self._worker_thread = None

    def __del__(self):
        log.debug(f"Dtor {self.__class__.__name__}: {id(self):08x}")
        self.close()

    def get_data(self, new_range: TimeRange):
        if self._worker_thread:
            self._worker.get_data(new_range)

    @property
    def icon(self) -> str:
        return ""

    @property
    def name(self) -> str:
        return self.objectName()

    @name.setter
    def name(self, new_name: str):
        self.setObjectName(new_name)

    def delete(self):
        self.please_delete_me.emit(self)


@register_inspector(DataPipeline)
class DataPipelineInspector(Inspector):
    @staticmethod
    def build_node(obj: Any, parent: Optional[Node] = None, children: Optional[List[Node]] = None) -> Optional[Node]:
        return Node(name=obj.name, bound_object=obj, icon=obj.icon, children=children, parent=parent)

    @staticmethod
    def list_children(obj: Any) -> List[Any]:
        return []

    @staticmethod
    def child(obj: Any, name: str) -> Optional[Any]:
        return None
