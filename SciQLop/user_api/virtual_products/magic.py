# SciQLop/user_api/virtual_products/magic.py
import argparse
import ast
import inspect
import shlex
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional

import numpy as np


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


def _parse_time_arg(value: str) -> float:
    """Parse a time argument as either a float or an ISO 8601 date string."""
    try:
        return float(value)
    except ValueError:
        return datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp()


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


def _register_virtual_product(name: str, wrapper: MutableCallback, product_type: str,
                               labels: Optional[List[str]], path: Optional[str]):
    """Register a virtual product using the existing create_virtual_product API."""
    from SciQLop.user_api.virtual_products import create_virtual_product, VirtualProductType

    vp_path = path or name
    vp_type = _product_type_to_enum(product_type)

    if vp_type == VirtualProductType.Scalar:
        effective_labels = labels or [name]
    elif vp_type == VirtualProductType.Vector:
        effective_labels = labels or ["X", "Y", "Z"]
    elif vp_type == VirtualProductType.MultiComponent:
        if labels:
            effective_labels = labels
        else:
            # Run callback once to determine component count for default labels
            try:
                data = wrapper(0.0, 1.0)
                n = data[1].shape[1] if isinstance(data, (tuple, list)) and hasattr(data[1], 'shape') and data[1].ndim == 2 else 1
            except Exception:
                n = 1
            effective_labels = [f"C{i}" for i in range(n)]
    else:
        effective_labels = None

    if vp_type == VirtualProductType.Spectrogram:
        create_virtual_product(vp_path, wrapper, vp_type)
    else:
        create_virtual_product(vp_path, wrapper, vp_type, labels=effective_labels)


def vp_magic(line: str, cell: str, local_ns=None):
    """Implementation of the %%vp cell magic."""
    user_ns = local_ns if local_ns is not None else {}
    # Make type annotation classes available in the cell's namespace
    from SciQLop.user_api.virtual_products.types import Scalar, Vector, MultiComponent, Spectrogram
    user_ns.setdefault("Scalar", Scalar)
    user_ns.setdefault("Vector", Vector)
    user_ns.setdefault("MultiComponent", MultiComponent)
    user_ns.setdefault("Spectrogram", Spectrogram)

    args = _parse_args(line)
    func = _extract_function(cell, user_ns)
    func_name = func.__name__

    from SciQLop.user_api.virtual_products.types import extract_vp_type_info

    # Extract type info from annotation
    # Use __annotations__ directly (not get_type_hints) because Vector["Bx", "By", "Bz"]
    # is eagerly evaluated by __class_getitem__ into a _VPTypeWithLabels instance.
    # get_type_hints() would try to re-evaluate string annotations and may fail.
    try:
        return_ann = func.__annotations__.get("return")
        type_info = extract_vp_type_info(return_ann)
    except Exception:
        type_info = None

    # Inference mode if no annotation
    if type_info is None:
        start, stop = _resolve_time_range(args, func)
        try:
            data = func(start, stop)
            type_info = _infer_type_from_data(data)
            _get_log().info(f"Inferred type: {type_info.product_type} — add return annotation to make explicit")
        except Exception as e:
            _get_log().error(f"Cannot infer type for {func_name}: {e}")
            return

    # Register in the registry (check if new BEFORE registering)
    is_new = func_name not in _registry._entries
    entry = _registry.register(func_name, func, type_info.product_type, type_info.labels)

    # Register virtual product only on first creation or signature change
    if is_new or entry.signature_changed:
        _register_virtual_product(func_name, entry.wrapper, type_info.product_type,
                                   type_info.labels, args.path)

    # Debug mode handled in Task 6
    if args.debug:
        _handle_debug(args, func, func_name, entry, type_info)


def _handle_debug(args, func, func_name, entry, type_info):
    """Open/reuse a scratch pad panel and run callback with validation."""
    from SciQLop.user_api.virtual_products.validation import validate_and_call
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

    # Run validation
    result = validate_and_call(func, start, stop, type_info.product_type, type_info.labels)

    if result.data is not None and not any(d.level == "error" for d in result.diagnostics):
        # Show success + any warnings
        if result.diagnostics:
            overlay.show_diagnostics(result.diagnostics)
        else:
            n_pts, shape, dtype = _extract_data_info(result.data)
            overlay.show_success(n_pts, shape, dtype, result.elapsed)
        # Clear and re-plot to force fresh data fetch, then auto-scale
        from SciQLop.core import TimeRange
        _plot_on_debug_panel(panel, func_name)
        panel.time_range = TimeRange(start, stop)
        _auto_scale_plots(panel)
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


def _create_debug_panel(func_name: str, start: float, stop: float):
    from SciQLop.user_api.gui import get_main_window
    from SciQLop.core import TimeRange
    panel_name = f"VP Debug: {func_name}"
    mw = get_main_window()
    panel = mw.new_plot_panel(name=panel_name)
    panel.time_range = TimeRange(start, stop)
    return panel
