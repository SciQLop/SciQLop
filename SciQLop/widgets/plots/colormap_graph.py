import numpy as np
from SciQLopPlots import QCPAxis, QCPColorGradient, \
    QCPAxisTickerLog, QCPRange
from speasy.products import SpeasyVariable

from SciQLop.backend.pipelines_model.data_provider import DataProvider
from SciQLop.backend.pipelines_model.graph import Graph
from SciQLop.backend.products_model.product_node import ProductNode
from ...backend.enums import GraphType
from ...backend.resampling.spectro_regrid import regrid


class ColorMapGraph(Graph):
    def __init__(self, parent, provider: DataProvider, product: ProductNode):
        Graph.__init__(self, parent=parent, graph_type=GraphType.ColorMap, provider=provider, product=product)
        parent.yAxis2.setScaleType(QCPAxis.stLogarithmic)
        parent.yAxis2.setTicker(QCPAxisTickerLog())
        parent.yAxis2.setVisible(True)
        self.colorScale, self._graph = parent.addSciQLopColorMap(parent.xAxis, parent.yAxis2, "ColorMap",
                                                                 with_color_scale=True)

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

        self.pipeline.plot.connect(self.plot)
        self.pipeline.get_data(parent.time_range)

    def plot(self, v: SpeasyVariable):
        self._last_value = v
        x, y, z = regrid(v)
        self._graph.colorMap().setDataRange(QCPRange(np.nanmin(z[np.nonzero(z)]), np.nanmax(z)))
        if self._graph.colorMap().name() != v.name:
            self._graph.colorMap().setName(v.name)

        self._graph.setData(x, y, z)
        self._graph.colorMap().rescaleValueAxis()
