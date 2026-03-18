# SciQLop/user_api/virtual_products/magic.py
import argparse
import ast
import inspect
import shlex
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import numpy as np
from IPython.core.magic import needs_local_scope


class MutableCallback:
    def __init__(self, callback: Callable):
        self.callback = callback
        self._update_metadata(callback)

    def _update_metadata(self, callback: Callable):
        """Forward signature/annotations so EasyProvider can inspect argument types."""
        import functools
        functools.update_wrapper(self, callback)

    @property
    def callback(self):
        return self._callback

    @callback.setter
    def callback(self, value):
        self._callback = value
        self._update_metadata(value)

    def __call__(self, start, stop):
        return self._callback(start, stop)


@dataclass
class RegistryEntry:
    wrapper: MutableCallback
    product_type: str
    labels: Optional[List[str]]
    signature_changed: bool = False
    panel: object = None  # will hold debug panel ref


class VPRegistry:
    def __init__(self):
        self._entries: Dict[str, RegistryEntry] = {}

    def register(self, name: str, callback: Callable,
                 product_type: str, labels: Optional[List[str]]) -> RegistryEntry:
        existing = self._entries.get(name)
        if existing and existing.product_type == product_type and existing.labels == labels:
            existing.wrapper.callback = callback
            existing.signature_changed = False
            return existing

        wrapper = MutableCallback(callback)
        entry = RegistryEntry(
            wrapper=wrapper,
            product_type=product_type,
            labels=labels,
            signature_changed=existing is not None,
        )
        self._entries[name] = entry
        return entry

    def get(self, name: str) -> Optional[RegistryEntry]:
        return self._entries.get(name)


_registry = VPRegistry()
_SENTINEL = object()


def _parse_args(line: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="%%vp", add_help=False)
    parser.add_argument("--path", type=str, default=None)
    parser.add_argument("--debug", action="store_true", default=False)
    parser.add_argument("--start", type=str, default=None)
    parser.add_argument("--stop", type=str, default=None)
    return parser.parse_args(shlex.split(line))


def _extract_function(cell: str, user_ns: dict) -> callable:
    """Execute the cell to define the function, return it."""
    exec(cell, user_ns)
    # Find the first top-level function defined in the cell
    tree = ast.parse(cell)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            return user_ns[node.name]
    raise ValueError("No function definition found in cell")


from SciQLop.user_api.magics.completions import _parse_time as _parse_time_arg


def _resolve_time_range(args, func):
    """Resolve debug/inference time range from flags, defaults, view, or fallback."""
    # 1. Explicit flags
    if args.start is not None and args.stop is not None:
        return _parse_time_arg(args.start), _parse_time_arg(args.stop)

    # 2. Function default arguments
    sig = inspect.signature(func)
    params = list(sig.parameters.values())
    if len(params) >= 2 and params[0].default != inspect.Parameter.empty and params[1].default != inspect.Parameter.empty:
        start, stop = params[0].default, params[1].default
        if isinstance(start, datetime):
            return start.timestamp(), stop.timestamp()
        if isinstance(start, np.datetime64):
            return start.astype("datetime64[ns]").astype(np.int64) / 1e9, stop.astype("datetime64[ns]").astype(np.int64) / 1e9
        return float(start), float(stop)

    # 3. Current view range from existing panels
    try:
        from SciQLop.user_api.gui import get_main_window
        mw = get_main_window()
        panels = mw.plot_panels()
        if panels:
            panel = mw.plot_panel(panels[0])
            if panel is not None:
                tr = panel.time_range
                return tr.start(), tr.stop()
    except Exception:
        pass

    # 4. Fallback: last 24 hours
    now = datetime.now(tz=timezone.utc).timestamp()
    return now - 86400, now


def _get_log():
    from SciQLop.components import sciqlop_logging
    return sciqlop_logging.getLogger(__name__)


def _infer_type_from_data(data):
    """Infer product type from callback return value shape."""
    from SciQLop.user_api.virtual_products.types import VPTypeInfo
    if isinstance(data, (tuple, list)) and len(data) >= 2:
        y = data[1]
        if isinstance(y, np.ndarray):
            if y.ndim == 1:
                return VPTypeInfo(product_type="scalar", labels=None)
            elif y.ndim == 2:
                if y.shape[1] == 3:
                    return VPTypeInfo(product_type="vector", labels=None)
                else:
                    return VPTypeInfo(product_type="multicomponent", labels=None)
    return VPTypeInfo(product_type="scalar", labels=None)


def _product_type_to_enum(product_type: str):
    from SciQLop.user_api.virtual_products import VirtualProductType
    return {
        "scalar": VirtualProductType.Scalar,
        "vector": VirtualProductType.Vector,
        "multicomponent": VirtualProductType.MultiComponent,
        "spectrogram": VirtualProductType.Spectrogram,
    }[product_type]


def _infer_multicomponent_labels(cached_data: Any) -> List[str]:
    """Infer default labels from cached evaluation data."""
    try:
        if isinstance(cached_data, (tuple, list)) and len(cached_data) >= 2:
            y = cached_data[1]
            if hasattr(y, 'shape') and y.ndim == 2:
                return [f"C{i}" for i in range(y.shape[1])]
    except Exception:
        pass
    return ["C0"]


def _register_virtual_product(name: str, wrapper: MutableCallback, product_type: str,
                               labels: Optional[List[str]], path: Optional[str],
                               cached_data: Any = None):
    """Register a virtual product using the existing create_virtual_product API."""
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType

    vp_path = path or name
    vp_type = _product_type_to_enum(product_type)

    if vp_type == VirtualProductType.Scalar:
        effective_labels = labels or [name]
    elif vp_type == VirtualProductType.Vector:
        effective_labels = labels or ["X", "Y", "Z"]
    elif vp_type == VirtualProductType.MultiComponent:
        effective_labels = labels or _infer_multicomponent_labels(cached_data)
    else:
        effective_labels = None

    if vp_type == VirtualProductType.Spectrogram:
        create_virtual_product(vp_path, wrapper, vp_type)
    else:
        create_virtual_product(vp_path, wrapper, vp_type, labels=effective_labels)


def _vp_magic_impl(line: str, cell: str, local_ns=None, cached_data=_SENTINEL,
                    eval_error=None, eval_elapsed=0.0):
    """Core %%vp logic. If cached_data is provided, skip evaluation."""
    from SciQLop.user_api.virtual_products.types import (
        Scalar, Vector, MultiComponent, Spectrogram, extract_vp_type_info,
    )

    user_ns = local_ns if local_ns is not None else {}
    user_ns.setdefault("Scalar", Scalar)
    user_ns.setdefault("Vector", Vector)
    user_ns.setdefault("MultiComponent", MultiComponent)
    user_ns.setdefault("Spectrogram", Spectrogram)

    args = _parse_args(line)
    func = _extract_function(cell, user_ns)
    func_name = func.__name__

    # Use __annotations__ directly (not get_type_hints) because Vector["Bx", "By", "Bz"]
    # is eagerly evaluated by __class_getitem__ into a _VPTypeWithLabels instance.
    try:
        return_ann = func.__annotations__.get("return")
        type_info = extract_vp_type_info(return_ann)
    except Exception:
        type_info = None

    needs_eval = type_info is None or args.debug
    if needs_eval and cached_data is _SENTINEL:
        start, stop = _resolve_time_range(args, func)
        try:
            cached_data = func(start, stop)
        except Exception as e:
            eval_error = e
            cached_data = None
            if not args.debug:
                _get_log().error(f"Cannot evaluate {func_name}: {e}")
                return
    elif not needs_eval:
        cached_data = None

    # If evaluation failed and we're not in debug mode, bail out
    if eval_error is not None and not args.debug:
        _get_log().error(f"Cannot evaluate {func_name}: {eval_error}")
        return

    if eval_error is None and type_info is None:
        type_info = _infer_type_from_data(cached_data)
        _get_log().info(f"Inferred type: {type_info.product_type} — add return annotation to make explicit")

    # In debug mode with an error, we still need a type_info for the panel
    if type_info is None:
        from SciQLop.user_api.virtual_products.types import VPTypeInfo
        type_info = VPTypeInfo(product_type="scalar", labels=None)

    is_new = func_name not in _registry._entries
    entry = _registry.register(func_name, func, type_info.product_type, type_info.labels)

    if is_new or entry.signature_changed:
        _register_virtual_product(func_name, entry.wrapper, type_info.product_type,
                                   type_info.labels, args.path, cached_data=cached_data)

    if args.debug:
        _handle_debug(args, func, func_name, entry, type_info,
                      cached_data=cached_data, eval_error=eval_error,
                      eval_elapsed=eval_elapsed)

    return func, args, type_info


def _run_in_thread_blocking(func, *args):
    """Run func(*args) in a thread, pumping Qt events until done."""
    from concurrent.futures import ThreadPoolExecutor
    from SciQLop.core.sciqlop_application import sciqlop_app

    app = sciqlop_app()
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(func, *args)
        while not future.done():
            app.processEvents()
        return future.result()


@needs_local_scope
def vp_magic(line: str, cell: str, local_ns=None):
    """%%vp cell magic — runs user function in a thread to avoid freezing the UI."""
    from SciQLop.user_api.virtual_products.types import (
        Scalar, Vector, MultiComponent, Spectrogram, extract_vp_type_info,
    )

    user_ns = local_ns if local_ns is not None else {}
    user_ns.setdefault("Scalar", Scalar)
    user_ns.setdefault("Vector", Vector)
    user_ns.setdefault("MultiComponent", MultiComponent)
    user_ns.setdefault("Spectrogram", Spectrogram)

    args = _parse_args(line)
    func = _extract_function(cell, user_ns)

    try:
        return_ann = func.__annotations__.get("return")
        type_info = extract_vp_type_info(return_ann)
    except Exception:
        type_info = None

    import time as _time

    cached_data = _SENTINEL
    eval_error = None
    eval_elapsed = 0.0
    if type_info is None or args.debug:
        start, stop = _resolve_time_range(args, func)
        t0 = _time.monotonic()
        try:
            cached_data = _run_in_thread_blocking(func, start, stop)
        except Exception as e:
            eval_error = e
            cached_data = None
            if not args.debug:
                _get_log().error(f"Cannot evaluate {func.__name__}: {e}")
                return
        eval_elapsed = _time.monotonic() - t0

    _vp_magic_impl(line, cell, local_ns, cached_data=cached_data,
                    eval_error=eval_error, eval_elapsed=eval_elapsed)


def _handle_debug(args, func, func_name, entry, type_info,
                   cached_data=None, eval_error=None, eval_elapsed=0.0):
    """Open/reuse a scratch pad panel and run callback with validation."""
    import traceback
    from SciQLop.user_api.virtual_products.validation import validate_with_data, Diagnostic
    from SciQLop.components.plotting.ui.diagnostic_overlay import DiagnosticOverlay

    start, stop = _resolve_time_range(args, func)

    # Get or create the debug panel
    panel = entry.panel
    if panel is None or not _panel_is_alive(panel):
        panel = _create_debug_panel(func_name, start, stop)
        entry.panel = panel

    # Attach overlay if not already present
    overlay = getattr(panel, '_vp_overlay', None)
    if overlay is None:
        overlay = DiagnosticOverlay(panel)
        panel._vp_overlay = overlay

    if eval_error is not None:
        tb = "".join(traceback.format_exception(eval_error))
        overlay.show_diagnostics([Diagnostic("error", tb)])
        return

    # Validate using cached data (no re-evaluation)
    result = validate_with_data(cached_data, type_info.product_type, type_info.labels)

    if result.data is not None and not any(d.level == "error" for d in result.diagnostics):
        from SciQLop.core import TimeRange
        _plot_on_debug_panel(panel, func_name)
        panel.time_range = TimeRange(start, stop)
        _auto_scale_plots(panel)
        # Show overlay after plotting so it isn't covered by new plot widgets
        if result.diagnostics:
            overlay.show_diagnostics(result.diagnostics)
        else:
            n_pts, shape, dtype = _extract_data_info(result.data)
            overlay.show_success(n_pts, shape, dtype, eval_elapsed)
    else:
        overlay.show_diagnostics(result.diagnostics)


def _plot_on_debug_panel(panel, func_name):
    """Clear and re-plot the virtual product on the debug panel.

    Always clears and re-adds to force a fresh data fetch from the callback,
    since replot() alone won't re-request data if the time range hasn't changed.
    """
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product
    from SciQLopPlots import PlotType
    panel.clear()
    path = func_name.split('/')
    plot_product(panel, path, plot_type=PlotType.TimeSeries)


def _auto_scale_plots(panel):
    """Auto-scale Y axes on all plots in the panel."""
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
        # Stack vertically below existing debug panel
        area = existing_debug.dockAreaWidget()
        mw.dock_manager.addDockWidget(QtAds.DockWidgetArea.BottomDockWidgetArea, doc, area)
        # Equalize vertical space among debug panels
        splitter = area.parentSplitter()
        if splitter and splitter.count() >= 2:
            equal = splitter.height() // splitter.count()
            splitter.setSizes([equal] * splitter.count())
    else:
        # First debug panel: add to the right
        mw.dock_manager.addDockWidget(QtAds.DockWidgetArea.RightDockWidgetArea, doc)

    # Always enforce 60/40 horizontal split
    root = mw.dock_manager.rootSplitter()
    if root and root.count() >= 2:
        total = root.width()
        sizes = [int(total * 0.6)] + [int(total * 0.4 / (root.count() - 1))] * (root.count() - 1)
        root.setSizes(sizes)

    mw.panel_added.emit(panel)
    mw._notify_panels_list_changed()
    panel.destroyed.connect(mw._notify_panels_list_changed)

    return panel
