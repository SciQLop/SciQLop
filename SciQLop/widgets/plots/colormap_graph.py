from ...backend.graph import Graph
from ...backend.enums import GraphType
from SciQLopPlots import SciQLopGraph, QCustomPlot, QCPColorScale, QCPAxis, QCPColorMap, QCPColorGradient, \
    QCPAxisTickerLog, QCPRange
from PySide6.QtGui import QColor
import numpy as np
from speasy.products import SpeasyVariable
from ...backend.resampling.spectro_regrid import regrid


class ColorMapGraph(Graph):
    def __init__(self, parent: QCustomPlot, data_order):
        Graph.__init__(self, parent=parent, graph_type=GraphType.ColorMap, data_order=data_order)
        parent.yAxis2.setScaleType(QCPAxis.stLogarithmic)
        parent.yAxis2.setTicker(QCPAxisTickerLog())
        parent.yAxis2.setVisible(True)
        self._graph = parent.addSciQLopColorMap(parent.xAxis, parent.yAxis2, "ColorMap")
        self._graph.colorMap().setLayer(parent.layer("background"))
        self._last_value = None
        self.colorScale = QCPColorScale(parent)
        self.colorScale.setDataScaleType(QCPAxis.stLogarithmic)
        self.colorScale.axis().setTicker(QCPAxisTickerLog())
        self.colorScale.setType(QCPAxis.atRight)
        self._graph.colorMap().setColorScale(self.colorScale)
        self._graph.colorMap().setInterpolate(False)
        parent.plotLayout().addElement(0, 1, self.colorScale)
        self._graph.colorMap().setDataScaleType(QCPAxis.stLogarithmic)
        self.colorScale.setType(QCPAxis.atRight)

        self.scale = QCPColorGradient(QCPColorGradient.gpJet)
        self.scale.setNanHandling(QCPColorGradient.nhTransparent)
        self._graph.colorMap().setGradient(self.scale)

    def plot(self, v: SpeasyVariable):
        self._last_value = v
        x, y, z = regrid(v)
        self._graph.colorMap().setDataRange(QCPRange(np.nanmin(z[np.nonzero(z)]), np.nanmax(z)))
        if self._graph.colorMap().name() != v.name:
            self._graph.colorMap().setName(v.name)
        self._graph.setData(x, y, z)
        self._graph.colorMap().rescaleValueAxis()
