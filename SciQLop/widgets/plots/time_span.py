from PySide6.QtCore import QObject
from PySide6.QtGui import QPen, QBrush, QColor, Qt
from SciQLopPlots import QCPItemRect, QCPItemStraightLine, QCustomPlot, QCPItemPosition, QCPItemAnchor, \
    SciQLopVerticalSpan, QCPRange

from SciQLop.backend.models import pipelines
from SciQLop.backend.pipelines_model.base.pipeline_node import QObjectPipelineModelItem, QObjectPipelineModelItemMeta
from .time_series_plot import TimeSeriesPlot


# class _TimeSpanBorder(QObject):
#     _line: QCPItemStraightLine
#
#     def __init__(self, parent: QCustomPlot = None):
#         super(_TimeSpanBorder, self).__init__(parent=parent)
#         self._line = QCPItemStraightLine(parent)
#         self._line.point1.setTypeX(QCPItemPosition.ptAbsolute)
#         self._line.point1.setTypeY(QCPItemPosition.ptAbsolute)
#         self._line.point2.setTypeX(QCPItemPosition.ptAbsolute)
#         self._line.point2.setTypeY(QCPItemPosition.ptAbsolute)
#         self._line.setPen(QPen(QBrush(QColor(0, 255, 255, 255), Qt.SolidPattern), 3))
#         self._line.setLayer("overlay")
#
#     def set_anchor(self, top_anchor: QCPItemAnchor, botom_anchor: QCPItemAnchor):
#         self._line.point1.setParentAnchor(top_anchor)
#         self._line.point2.setParentAnchor(botom_anchor)
#
#
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
