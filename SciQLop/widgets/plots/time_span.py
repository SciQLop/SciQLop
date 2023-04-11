from SciQLopPlots import SciQLopVerticalSpan, QCPRange

from SciQLop.backend.models import pipelines
from SciQLop.backend.pipelines_model.base.pipeline_node import QObjectPipelineModelItem, QObjectPipelineModelItemMeta
from .time_series_plot import TimeSeriesPlot


class TimeSpan(SciQLopVerticalSpan, QObjectPipelineModelItem, metaclass=QObjectPipelineModelItemMeta):

    def __init__(self, time_range: QCPRange, parent: TimeSeriesPlot = None):
        SciQLopVerticalSpan.__init__(self, parent.plot_instance, time_range)
        with pipelines.model_update_ctx():
            QObjectPipelineModelItem.__init__(self, "TimeSpan")

    def delete_node(self):
        self.parent_node.plot_instance.removeItem(self._rectangle)
        self.parent_node.plot_instance.removeItem(self._left_border._line)
        self.parent_node.plot_instance.removeItem(self._right_border._line)
        self.parent_node.replot()
        QObjectPipelineModelItem.delete_node(self)
