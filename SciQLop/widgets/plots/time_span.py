from typing import List

from PySide6.QtCore import QObject, Signal
from SciQLopPlots import SciQLopVerticalSpan, QCPRange

from .time_sync_panel import TimeSyncPanel
from ...backend import TimeRange


class TimeSpan(QObject):
    _spans: List[SciQLopVerticalSpan] = []
    range_changed = Signal(TimeRange)

    def __init__(self, time_range: TimeRange, plot_panel: TimeSyncPanel, parent=None, visible=True, read_only=False):
        QObject.__init__(self, parent)
        self._spans = []
        self._time_range = time_range
        self._plot_panel = plot_panel
        self._visible = visible
        self.read_only = read_only
        self._plot_panel.plot_list_changed.connect(self.update_spans)

    def update_spans(self):
        if self._visible:
            self._spans = []
            for plot in self._plot_panel.plots:
                span = SciQLopVerticalSpan(plot.plot_instance, QCPRange(self._time_range.start, self._time_range.stop))
                self._spans.append(span)
                span.set_read_only(self.read_only)
        else:
            self._spans = []

    def show(self):
        self._visible = True
        self.update_spans()

    def hide(self):
        self._visible = False
        self.update_spans()

    @property
    def read_only(self):
        return self._read_only

    @read_only.setter
    def read_only(self, read_only):
        self._read_only = read_only
        for s in self._spans:
            s.set_read_only(read_only)

    @property
    def time_range(self):
        return self._time_range
