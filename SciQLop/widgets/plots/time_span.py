from typing import List, Optional

from PySide6.QtCore import QObject, Signal, Slot
from PySide6.QtGui import QColor
from SciQLopPlots import SciQLopVerticalSpan, QCPRange

from .time_sync_panel import TimeSyncPanel
from ...backend import TimeRange
from ...backend.property import SciQLopProperty


class TimeSpan(QObject):
    _spans: List[SciQLopVerticalSpan] = []
    range_changed = Signal(TimeRange)
    selection_changed = Signal(bool)

    def __init__(self, time_range: TimeRange, plot_panel: TimeSyncPanel, parent=None, visible=True, read_only=False,
                 color=None, tooltip: Optional[str] = None):
        QObject.__init__(self, parent)
        self._spans = []
        self._tooltip = tooltip
        self._selected = False
        self._time_range = time_range
        self._plot_panel = plot_panel
        self._visible = visible
        self.read_only = read_only
        self._plot_panel.plot_list_changed.connect(self.update_spans)
        self._color = color or QColor(100, 100, 100, 100)
        self.update_spans()

    def update_spans(self):
        self._spans = []
        for plot in self._plot_panel.plots:
            span = SciQLopVerticalSpan(plot.plot_instance, QCPRange(self._time_range.start, self._time_range.stop))
            if self._tooltip is not None:
                span.set_tool_tip(self._tooltip)
            span.range_changed.connect(self.set_range)
            span.selectionChanged.connect(self.change_selection)
            self._spans.append(span)
            span.set_read_only(self.read_only)
            span.set_color(self._color)
            span.set_visible(self._visible)

    @Slot()
    def change_selection(self, selected: bool):
        if self._selected != selected:
            self._selected = selected
            for s in self._spans:
                s.set_selected(selected)
            self._plot_panel.replot()
            self.selection_changed.emit(selected)

    @Slot()
    def set_color(self, new_color: QColor):
        self.color = new_color

    @Slot()
    def set_range(self, new_range: QCPRange):
        new_range_tr = TimeRange.from_qcprange(new_range)
        if self._time_range != new_range_tr:
            for s in self._spans:
                s.set_range(new_range)
            self._time_range = new_range_tr
            self.range_changed.emit(new_range_tr)

    def show(self):
        list(map(lambda s: s.set_visible(True), self._spans))

    def hide(self):
        list(map(lambda s: s.set_visible(False), self._spans))

    @SciQLopProperty(bool)
    def read_only(self):
        return self._read_only

    @read_only.setter
    def read_only(self, read_only: bool):
        self._read_only = read_only
        for s in self._spans:
            s.set_read_only(read_only)

    @SciQLopProperty(TimeRange)
    def time_range(self) -> TimeRange:
        return self._time_range

    @SciQLopProperty(QColor)
    def color(self) -> QColor:
        return self._color

    @color.setter
    def color(self, new_color):
        self._color = new_color
        for s in self._spans:
            s.set_color(new_color)

    @SciQLopProperty(bool)
    def selected(self) -> bool:
        return self._selected

    @SciQLopProperty(str)
    def tooltip(self) -> Optional[str]:
        return self._tooltip

    @tooltip.setter
    def tooltip(self, new_tooltip: str):
        self._tooltip = new_tooltip
        for s in self._spans:
            s.set_tool_tip(new_tooltip)
