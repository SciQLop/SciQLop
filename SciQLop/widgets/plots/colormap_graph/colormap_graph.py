import numpy as np
from SciQLopPlots import QCPAxis, QCPColorGradient, \
    QCPAxisTickerLog, QCPRange, QCPColorScale, SciQLopColorMap
from speasy.products import SpeasyVariable

from SciQLop.backend.pipelines_model.data_provider import DataProvider
from SciQLop.backend.pipelines_model.graph import Graph
from SciQLop.backend.products_model.product_node import ProductNode
from SciQLop.backend.enums import GraphType
from SciQLop.backend.resampling.spectro_regrid import regrid
from PySide6.QtCore import QObject, Signal, QThread, Qt, QMutex, Slot
from shiboken6 import isValid


class PythonResampler(QObject):
    plot_sig = Signal(object, object, object)
    _plot_sig = Signal(object)

    def __init__(self, parent=None):
        super(PythonResampler, self).__init__(parent=parent)
        self.data_mutex = QMutex()
        self._plot_sig.connect(self._plot, Qt.ConnectionType.QueuedConnection)
        self._v = None

    def _plot(self, v: SpeasyVariable):
        latest = False
        self.data_mutex.lock()
        latest = self._v is v
        self.data_mutex.unlock()
        if latest:
            self.plot_sig.emit(*regrid(v))

    def plot(self, v: SpeasyVariable):
        self.data_mutex.lock()
        self._v = v
        self.data_mutex.unlock()
        self._plot_sig.emit(v)


class ColorMapGraph(Graph):

    def __init__(self, parent, y_axis: QCPAxis, colormap: SciQLopColorMap, color_scale: QCPColorScale,
                 provider: DataProvider, product: ProductNode):
        Graph.__init__(self, parent=parent, graph_type=GraphType.ColorMap, provider=provider, product=product)
        y_axis.setScaleType(QCPAxis.stLogarithmic)
        y_axis.setTicker(QCPAxisTickerLog())
        y_axis.setVisible(True)
        self.colorScale: QCPColorScale = color_scale
        self._graph: SciQLopColorMap = colormap

        self._last_value = None
        self.colorScale.setDataScaleType(QCPAxis.stLogarithmic)
        self.colorScale.axis().setTicker(QCPAxisTickerLog())
        self.colorScale.setType(QCPAxis.atRight)
        self._graph.colorMap().setColorScale(self.colorScale)
        self._graph.colorMap().setInterpolate(False)
        self._graph.colorMap().setDataScaleType(QCPAxis.stLogarithmic)
        self.colorScale.setType(QCPAxis.atRight)

        self.scale = QCPColorGradient(QCPColorGradient.gpJet)
        self.scale.setNanHandling(QCPColorGradient.nhTransparent)
        self._graph.colorMap().setGradient(self.scale)
        self._graph.colorMap().addToLegend()

        self._resampler = PythonResampler()
        self._resampler_thread = QThread()
        self._resampler.moveToThread(self._resampler_thread)
        self._resampler.plot_sig.connect(self._plot, Qt.ConnectionType.QueuedConnection)
        self.pipeline.plot.connect(self.plot)
        self._resampler_thread.start()
        self.pipeline.get_data(parent.time_range)
        # hack to get plot refresh TODO: investigate this
        self.pipeline.get_data(parent.time_range)

    def set_gradient(self, gradient: QCPColorGradient):
        self.scale = gradient
        self.scale.setNanHandling(QCPColorGradient.nhTransparent)
        self._graph.colorMap().setGradient(self.scale)
        self.replot()

    def plot(self, v: SpeasyVariable):
        if self._graph.colorMap().name() != v.name:
            self._graph.colorMap().setName(v.name)
        self._resampler.plot(v)

    def _plot(self, x, y, z):
        self._graph.colorMap().setDataRange(QCPRange(np.nanmin(z[np.nonzero(z)]), np.nanmax(z)))
        self._graph.setData(x, y, z)
        self._graph.colorMap().rescaleValueAxis()

    def hide_color_scale(self):
        self.scale.hide()

    def show_color_scale(self):
        self.scale.show()

    @Slot()
    def replot(self):
        self.parent().replot()

    def __del__(self):
        if isValid(self._resampler_thread):
            self._resampler_thread.finished.connect(self._resampler_thread.deleteLater)
            self._resampler.plot_sig.disconnect()
            self._resampler_thread.quit()
            self._resampler_thread.wait()
