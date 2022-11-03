from PySide6.QtCore import QObject, QThread, QWaitCondition, QMutex
from SciQLopPlots import MultiLineGraph, enums, LineGraph, axis
from .data_provider import DataProvider, DataOrder
from datetime import datetime
from typing import Optional, Tuple
import numpy as np


class _PlotPipeline_worker(QThread):

    def __init__(self, graph, provider: DataProvider, product: str, time_range: axis.range):
        QThread.__init__(self)
        self.setTerminationEnabled(True)
        self.wait_condition = QWaitCondition()
        self.next_range: Optional[axis.range] = time_range
        self.current_range: Optional[axis.range] = None
        self.provider = provider
        self.product = product
        self.graph = graph
        self.moveToThread(self)
        self.start()
        if isinstance(graph, MultiLineGraph):
            self.update_plot = self.update_plot_multiline
        elif isinstance(graph, LineGraph):
            self.update_plot = self.update_plot_line
        if provider.data_order == DataOrder.ROW_MAJOR:
            self._data_order = enums.DataOrder.y_first
        else:
            self._data_order = enums.DataOrder.x_first

    def get_data(self, new_range: axis.range) -> Optional[Tuple[np.ndarray]]:
        return self.provider.get_data(self.product, datetime.utcfromtimestamp(new_range.first),
                                      datetime.utcfromtimestamp(new_range.second))

    def get_data_task(self, new_range: axis.range):
        data = self.get_data(new_range)
        if data is not None:
            self.update_plot(*data)
        self.current_range = new_range

    def update_plot_line(self, x: np.ndarray, y: np.ndarray):
        if len(x) > 0 and len(x) == len(y):
            self.graph.plot(x, y.flatten())

    def update_plot_multiline(self, x: np.ndarray, y: np.ndarray):
        if len(x) > 0 and len(x) == len(y):
            self.graph.plot(x, y.flatten(), self._data_order)

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
    def __init__(self, graph, provider: DataProvider, product: str, time_range: axis.range):
        QThread.__init__(self)
        self.setTerminationEnabled(True)
        self.moveToThread(self)
        self.wait_condition = QWaitCondition()
        self.next_range: Optional[axis.range] = time_range
        self.current_range: Optional[axis.range] = None
        self.start()
        self._worker = _PlotPipeline_worker(graph, provider, product, time_range)

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


class PlotPipeline(QObject):
    def __init__(self, graph, provider: DataProvider, product: str, time_range: axis.range):
        QObject.__init__(self, graph)
        self._worker = _PlotPipeline_worker(graph, provider, product, time_range)
        graph.xRangeChanged.connect(self.get_data)

    def __del__(self):
        self._worker.requestInterruption()
        self._worker.wait_condition.wakeAll()
        if not self._worker.wait(1000):
            self._worker.quit()
            self._worker.wait()

    def get_data(self, new_range: axis.range):
        self._worker.next_range = new_range
        self._worker.wait_condition.wakeOne()
