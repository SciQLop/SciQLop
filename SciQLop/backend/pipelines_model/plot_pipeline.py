from PySide6.QtCore import QObject, QThread, QWaitCondition, QMutex
from SciQLop.backend.pipelines_model.data_provider import DataProvider
from SciQLop.backend import TimeRange
from SciQLop.backend.pipelines_model.graph import Graph
from datetime import datetime
from typing import Optional
from speasy.products import SpeasyVariable


class _PlotPipeline_worker(QThread):

    def __init__(self, graph: Graph, provider: DataProvider, product: str, time_range: TimeRange):
        QThread.__init__(self)
        self.setTerminationEnabled(True)
        self.wait_condition = QWaitCondition()
        self.next_range: Optional[TimeRange] = time_range
        self.current_range: Optional[TimeRange] = None
        self.provider = provider
        self.product = product
        self.graph = graph
        self.moveToThread(self)
        self.start()
        self._data_order = provider.data_order

    def get_data(self, new_range: TimeRange) -> Optional[SpeasyVariable]:
        return self.provider.get_data(self.product, datetime.utcfromtimestamp(new_range.start),
                                      datetime.utcfromtimestamp(new_range.stop))

    def get_data_task(self, new_range: TimeRange):
        data = self.get_data(new_range)
        if data is not None:
            self.graph.plot(data)
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
    def __init__(self, graph, provider: DataProvider, product: str, time_range: TimeRange):
        QThread.__init__(self)
        self.setTerminationEnabled(True)
        self.moveToThread(self)
        self.wait_condition = QWaitCondition()
        self.next_range: Optional[TimeRange] = time_range
        self.current_range: Optional[TimeRange] = None
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
    def __init__(self, graph: Graph, provider: DataProvider, product: str, time_range: TimeRange):
        QObject.__init__(self, graph)
        self._worker = _PlotPipeline_worker(graph, provider, product, time_range)
        graph.xRangeChanged.connect(self.get_data)

    def __del__(self):
        self._worker.requestInterruption()
        self._worker.wait_condition.wakeAll()
        if not self._worker.wait(1000):
            self._worker.quit()
            self._worker.wait()

    def get_data(self, new_range: TimeRange):
        self._worker.next_range = new_range
        self._worker.wait_condition.wakeOne()
