from PySide6.QtCore import QObject, QTimer, Signal


def panel_created(main_window, context):
    return main_window.panel_added


def dock_visible(dock_name):
    def _completion(main_window, context):
        dw = main_window.dock_manager.findDockWidget(dock_name)
        if dw is None:
            return None
        return dw.visibilityChanged, (lambda visible: visible)
    return _completion


def _is_real_plot(plot) -> bool:
    # SciQLopPlots inserts a temporary "PlaceHolder" plot while a drag hovers the panel.
    return plot is not None and plot.objectName() != "PlaceHolder"


class _PlotListSettled(QObject):
    """Emits `ready(plot)` once the panel holds a real plot and its plot
    list has stopped changing for _SETTLE_MS. A drag-and-drop keeps
    churning the list (placeholder waves, a re-created plot) for a while
    after the first real plot shows up, so reacting to that first
    sighting fired too early. A panel that already has a plot is ready."""

    ready = Signal(object)

    _SETTLE_MS = 600

    def __init__(self, panel, parent=None):
        super().__init__(parent)
        self._panel = panel
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._on_settled)
        panel.plot_list_changed.connect(self._on_plot_list_changed)
        if any(_is_real_plot(p) for p in panel.plots()):
            QTimer.singleShot(0, self._on_settled)

    def _on_plot_list_changed(self, plots) -> None:
        if any(_is_real_plot(p) for p in plots):
            self._timer.start(self._SETTLE_MS)
        else:
            self._timer.stop()

    def _on_settled(self) -> None:
        real_plots = [p for p in self._panel.plots() if _is_real_plot(p)]
        if real_plots:
            self.ready.emit(real_plots[-1])


def plot_settled_in(context_key):
    def _completion(main_window, context):
        panel = context.get(context_key)
        if panel is None:
            return None
        return _PlotListSettled(panel, parent=panel).ready
    return _completion
