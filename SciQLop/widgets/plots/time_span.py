from typing import List, Optional

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QColor
from SciQLopPlots import SciQLopVerticalSpan, QCPRange, MultiPlotsVerticalSpan

from .time_sync_panel import TimeSyncPanel
from ...backend import TimeRange
from ...backend.property import SciQLopProperty


def _filter_plots(plot_list: List):
    return [p.plot_instance for p in plot_list if hasattr(p, "plot_instance")]


class TimeSpan(MultiPlotsVerticalSpan):
    time_range_changed = Signal(TimeRange)

    def __init__(self, time_range: TimeRange, plot_panel: TimeSyncPanel, parent=None, visible=True, read_only=False,
                 color=None, tooltip: Optional[str] = None):
        MultiPlotsVerticalSpan.__init__(self, _filter_plots(plot_panel.plots),
                                        time_range.to_qcprange(), color or QColor(100, 100, 100, 100),
                                        read_only, visible, tooltip, parent)
        self._plot_panel = plot_panel
        self._plot_panel.plot_list_changed.connect(self.update_spans)
        self.range_changed.connect(lambda r: self.time_range_changed.emit(TimeRange.from_qcprange(r)))

    def update_spans(self):
        self.update_plot_list(_filter_plots(self._plot_panel.plots))

    @property
    def time_range(self) -> TimeRange:
        return TimeRange.from_qcprange(self.range)

    @time_range.setter
    def time_range(self, new_range: TimeRange):
        new_range = new_range.to_qcprange()
        if self.range != new_range:
            self.range = new_range
