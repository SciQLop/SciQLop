from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout

from SciQLop.components.plotting.ui.catalog_chrome import CatalogChrome
from SciQLop.components.plotting.ui.crosshair_toggle import CrosshairToggle
from SciQLop.components.plotting.ui.plot_shortcuts import install_plot_shortcuts
from SciQLop.components.plotting.ui.time_range_bar import TimeRangeBar
from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
from SciQLop.components.shortcuts import add_shortcut
from SciQLop.core import TimeRange
from SciQLop.core.ui import Metrics


class PanelContainer(QWidget):

    def __init__(self, panel: TimeSyncPanel, parent=None):
        super().__init__(parent)
        self.panel = panel

        self.crosshair_toggle = CrosshairToggle(self)
        self.time_range_bar = TimeRangeBar(self)
        self.catalog_chrome = CatalogChrome(self)

        panel._time_range_bar = self.time_range_bar
        panel._catalog_chrome = self.catalog_chrome
        panel.catalog_manager.attach_chrome(self.catalog_chrome)
        panel._crosshair_toggle = self.crosshair_toggle

        self.chrome_row = self._build_chrome_row()
        self._current_limit = self.time_range_bar.max_range_seconds
        self._bar_sync_timer = self._make_bar_sync_timer()
        self._pending_bar_range = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(panel, 1)
        layout.addWidget(self.chrome_row, 0)

        self.setWindowTitle(panel.windowTitle())
        self.setObjectName(panel.objectName())

        self._clamp_initial_range(panel.time_range)
        self._wire_signals()
        self._install_shortcuts()
        self._apply_limit_to_all_plots()
        QTimer.singleShot(300, self.time_range_bar.pulse)

    def _build_chrome_row(self) -> QWidget:
        row = QWidget(self)
        row.setMaximumHeight(Metrics.ex(2.5))
        layout = QHBoxLayout(row)
        layout.setContentsMargins(2, 0, 2, 0)
        layout.setSpacing(2)

        layout.addStretch(1)
        layout.addWidget(self.time_range_bar)
        layout.addSpacing(Metrics.em(1))
        layout.addWidget(self.crosshair_toggle)
        layout.addSpacing(Metrics.em(1))
        layout.addWidget(self.catalog_chrome)
        layout.addStretch(1)
        return row

    def _wire_signals(self):
        self.panel.time_range_changed.connect(self._on_panel_range_changed)
        self.time_range_bar.range_changed.connect(self._on_bar_range_changed)
        self.time_range_bar.limit_changed.connect(self._on_limit_changed)
        self.crosshair_toggle.toggled.connect(self._on_crosshair_toggled)
        self.panel.plot_added.connect(self._apply_limit_to_plot)
        self.panel.plot_added.connect(self._apply_crosshair_to_plot)
        self.panel.plot_added.connect(install_plot_shortcuts)

    def _install_shortcuts(self):
        slots = {
            "panel.toggle_crosshair": self.crosshair_toggle.toggle,
            "panel.cycle_catalog_mode": self.catalog_chrome.cycle_mode,
            "panel.autoscale_all": self.panel._autoscale_all_plots,
            "panel.equalize_heights": self.panel._equalize_plot_heights,
            "panel.organize": self.panel.organize_plots,
            "panel.deselect_all": self.panel.deselect_all,
        }
        self.shortcuts = {sid: add_shortcut(self, sid, slot) for sid, slot in slots.items()}
        for plot in self.panel.plots():
            install_plot_shortcuts(plot)

    def _clamp_initial_range(self, tr: TimeRange):
        limit = self._current_limit
        if limit > 0 and (tr.stop() - tr.start()) > limit:
            tr = TimeRange(tr.start(), tr.start() + limit)
        self.time_range_bar.set_range(tr)
        self.panel.set_time_axis_range(tr)

    def _make_bar_sync_timer(self) -> QTimer:
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.setInterval(100)
        timer.timeout.connect(self._sync_bar_to_pending_range)
        return timer

    def _on_panel_range_changed(self, tr: TimeRange):
        # Leading-edge throttle: a drag emits at 60 Hz and every bar repaint
        # uploads the whole window backing store (GH #143).
        self._pending_bar_range = tr
        if not self._bar_sync_timer.isActive():
            self._sync_bar_to_pending_range()

    def _sync_bar_to_pending_range(self):
        if self._pending_bar_range is None:
            return
        self.time_range_bar.set_range(self._pending_bar_range)
        self._pending_bar_range = None
        self._bar_sync_timer.start()

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

    def _apply_crosshair_to_plot(self, plot):
        if hasattr(plot, "set_crosshair_enabled"):
            plot.set_crosshair_enabled(self.crosshair_toggle.isChecked())

    def _on_crosshair_toggled(self, enabled: bool):
        for plot in self.panel.plots():
            if hasattr(plot, "set_crosshair_enabled"):
                plot.set_crosshair_enabled(enabled)
