from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout

from SciQLop.components.plotting.ui.time_range_bar import TimeRangeBar
from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
from SciQLop.core import TimeRange


class PanelContainer(QWidget):

    def __init__(self, panel: TimeSyncPanel, parent=None):
        super().__init__(parent)
        self.panel = panel
        self.time_range_bar = TimeRangeBar(self)
        panel._time_range_bar = self.time_range_bar
        self._current_limit = self.time_range_bar.max_range_seconds

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(panel, 1)
        layout.addWidget(self.time_range_bar, 0)

        self.setWindowTitle(panel.windowTitle())
        self.setObjectName(panel.objectName())

        self._clamp_initial_range(panel.time_range)
        panel.time_range_changed.connect(self._on_panel_range_changed)
        self.time_range_bar.range_changed.connect(self._on_bar_range_changed)
        self.time_range_bar.limit_changed.connect(self._on_limit_changed)
        panel.plot_added.connect(self._apply_limit_to_plot)

        self._apply_limit_to_all_plots()
        QTimer.singleShot(300, self.time_range_bar.pulse)

    def _clamp_initial_range(self, tr: TimeRange):
        limit = self._current_limit
        if limit > 0 and (tr.stop() - tr.start()) > limit:
            tr = TimeRange(tr.start(), tr.start() + limit)
        self.time_range_bar.set_range(tr)
        self.panel.set_time_axis_range(tr)

    def _on_panel_range_changed(self, tr: TimeRange):
        self.time_range_bar.set_range(tr)

    def _on_bar_range_changed(self, tr: TimeRange):
        self.panel.set_time_axis_range(tr)

    def _apply_limit_to_plot(self, plot):
        axis = plot.time_axis()
        if axis is None:
            return
        axis.set_max_range_size(self._current_limit)
        axis.range_clamped.connect(lambda _req, _clamped: self.time_range_bar.pulse_limit())

    def _apply_limit_to_all_plots(self):
        for plot in self.panel.plots():
            self._apply_limit_to_plot(plot)

    def _on_limit_changed(self, max_seconds: float):
        self._current_limit = max_seconds
        self._apply_limit_to_all_plots()
