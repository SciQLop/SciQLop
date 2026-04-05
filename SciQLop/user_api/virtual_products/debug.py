# SciQLop/user_api/virtual_products/debug.py
"""Debug panel creation and overlay management for %%vp --debug."""
import traceback
from typing import Optional

from SciQLop.user_api.virtual_products.registry import RegistryEntry, _invoke_on_main_thread
from SciQLop.user_api.virtual_products.validation import validate_with_data, Diagnostic


def handle_debug(args, func, func_name: str, entry: RegistryEntry, type_info,
                 start: float, stop: float,
                 cached_data=None, eval_error=None, eval_elapsed: float = 0.0):
    """Open/reuse a scratch pad panel and run callback with validation."""
    result = None
    if eval_error is None:
        result = validate_with_data(cached_data, type_info.product_type, type_info.labels)

    def _do_debug_ui():
        from SciQLop.components.plotting.ui.diagnostic_overlay import DiagnosticOverlay

        panel = entry.panel
        if panel is None or not _panel_is_alive(panel):
            panel = _create_debug_panel(func_name, start, stop)
            entry.panel = panel

        overlay = getattr(panel, '_vp_overlay', None)
        if overlay is None:
            overlay = DiagnosticOverlay(panel)
            panel._vp_overlay = overlay

        from SciQLop.core import TimeRange
        _plot_on_debug_panel(panel, func_name)
        panel.time_range = TimeRange(start, stop)

        if eval_error is not None:
            tb = "".join(traceback.format_exception(eval_error))
            overlay.show_diagnostics([Diagnostic("error", tb)])
            return

        if result.data is not None and not any(d.level == "error" for d in result.diagnostics):
            _auto_scale_plots(panel)
            if result.diagnostics:
                overlay.show_diagnostics(result.diagnostics)
            else:
                n_pts, shape, dtype = _extract_data_info(result.data)
                overlay.show_success(n_pts, shape, dtype, eval_elapsed)
        else:
            overlay.show_diagnostics(result.diagnostics)

        def _on_data_fetched(data, elapsed):
            if data is None:
                return
            n_pts, shape, dtype = _extract_data_info(data)
            overlay.show_success(n_pts, shape, dtype, elapsed)

        entry.wrapper.after_call = _on_data_fetched

    _invoke_on_main_thread(_do_debug_ui)


def _plot_on_debug_panel(panel, func_name: str):
    """Clear and re-plot the virtual product on the debug panel."""
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product
    from SciQLopPlots import PlotType
    panel.clear()
    path = func_name.split('/')
    plot_product(panel, path, plot_type=PlotType.TimeSeries)


def _auto_scale_plots(panel):
    for plot in panel.plots():
        plot.rescale_axes()


def _extract_data_info(data):
    """Extract (n_points, shape, dtype) from callback return data."""
    from speasy.products import SpeasyVariable
    if isinstance(data, SpeasyVariable):
        values = data.values
        return len(values), values.shape, str(values.dtype)
    if isinstance(data, (tuple, list)) and len(data) >= 2:
        y = data[1]
        if hasattr(y, 'shape'):
            return len(y), y.shape, str(y.dtype)
    return 0, '?', '?'


def _panel_is_alive(panel) -> bool:
    try:
        panel.objectName()
        return True
    except RuntimeError:
        return False


def _find_existing_debug_dock(mw):
    """Find an existing VP Debug dock widget to stack below."""
    import PySide6QtAds as QtAds
    for doc in mw.dock_manager.dockWidgetsMap().values():
        if doc.windowTitle().startswith("VP Debug:") and not doc.isClosed():
            return doc
    return None


def _create_debug_panel(func_name: str, start: float, stop: float):
    from SciQLop.user_api.gui import get_main_window
    from SciQLop.core import TimeRange
    from SciQLop.core.ui.mainwindow import auto_name
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    import PySide6QtAds as QtAds

    panel_name = f"VP Debug: {func_name}"
    mw = get_main_window()

    panel = TimeSyncPanel(parent=None, name=auto_name(base="Panel", name=panel_name),
                          time_range=TimeRange(start, stop))

    doc = QtAds.CDockWidget(panel.windowTitle())
    doc.setWidget(panel)
    doc.setMinimumSizeHintMode(QtAds.CDockWidget.MinimumSizeHintFromContent)
    doc.setFeature(QtAds.CDockWidget.DockWidgetDeleteOnClose, True)

    existing_debug = _find_existing_debug_dock(mw)
    if existing_debug is not None:
        area = existing_debug.dockAreaWidget()
        mw.dock_manager.addDockWidget(QtAds.DockWidgetArea.BottomDockWidgetArea, doc, area)
        splitter = area.parentSplitter()
        if splitter and splitter.count() >= 2:
            equal = splitter.height() // splitter.count()
            splitter.setSizes([equal] * splitter.count())
    else:
        mw.dock_manager.addDockWidget(QtAds.DockWidgetArea.RightDockWidgetArea, doc)

    root = mw.dock_manager.rootSplitter()
    if root and root.count() >= 2:
        total = root.width()
        sizes = [int(total * 0.6)] + [int(total * 0.4 / (root.count() - 1))] * (root.count() - 1)
        root.setSizes(sizes)

    mw.panel_added.emit(panel)
    mw._notify_panels_list_changed()
    panel.destroyed.connect(mw._notify_panels_list_changed)

    return panel
