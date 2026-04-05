# SciQLop/user_api/virtual_products/magic.py
"""%%vp cell magic — define and register virtual products from notebook cells."""
import ast
import inspect
import time as _time
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from IPython.core.magic import needs_local_scope

from SciQLop.user_api.virtual_products.registry import (
    MutableCallback, VPRegistry, RegistryEntry,
    _registry, _invoke_on_main_thread, _infer_multicomponent_labels,
    register_virtual_product as _register_virtual_product,
)

# Re-export for backward compatibility (tests import these from magic.py)
__all__ = [
    'vp_magic', '_vp_magic_impl', '_registry',
    'MutableCallback', 'VPRegistry', '_extract_function',
    '_infer_type_from_data', '_infer_multicomponent_labels',
    '_find_existing_debug_dock',
]


def _find_existing_debug_dock(mw):
    """Re-export from debug module."""
    from SciQLop.user_api.virtual_products.debug import _find_existing_debug_dock as _impl
    return _impl(mw)


def _parse_args(line: str):
    import argparse
    import shlex
    parser = argparse.ArgumentParser(prog="%%vp", add_help=False)
    parser.add_argument("--path", type=str, default=None)
    parser.add_argument("--debug", action="store_true", default=False)
    parser.add_argument("--start", type=str, default=None)
    parser.add_argument("--stop", type=str, default=None)
    return parser.parse_args(shlex.split(line))


def _extract_function(cell: str, user_ns: dict) -> callable:
    """Execute the cell to define the function, return the first top-level def."""
    exec(cell, user_ns)
    tree = ast.parse(cell)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            return user_ns[node.name]
    raise ValueError("No function definition found in cell")


def _resolve_time_range(args, func):
    """Resolve debug/inference time range from flags, defaults, view, or fallback."""
    from SciQLop.user_api.magics.completions import _parse_time as _parse_time_arg

    if args.start is not None and args.stop is not None:
        return _parse_time_arg(args.start), _parse_time_arg(args.stop)

    sig = inspect.signature(func)
    params = list(sig.parameters.values())
    if len(params) >= 2 and params[0].default != inspect.Parameter.empty and params[1].default != inspect.Parameter.empty:
        start, stop = params[0].default, params[1].default
        if isinstance(start, datetime):
            return start.timestamp(), stop.timestamp()
        if isinstance(start, np.datetime64):
            return start.astype("datetime64[ns]").astype(np.int64) / 1e9, stop.astype("datetime64[ns]").astype(np.int64) / 1e9
        return float(start), float(stop)

    try:
        def _get_panel_time_range():
            from SciQLop.user_api.gui import get_main_window
            mw = get_main_window()
            panels = mw.plot_panels()
            if panels:
                panel = mw.plot_panel(panels[0])
                if panel is not None:
                    tr = panel.time_range
                    return tr.start(), tr.stop()
            return None
        result = _invoke_on_main_thread(_get_panel_time_range)
        if result is not None:
            return result
    except Exception:
        pass

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


def _inject_type_names(user_ns: dict):
    """Make VP type names available in the user namespace for annotations."""
    from SciQLop.user_api.virtual_products.types import Scalar, Vector, MultiComponent, Spectrogram
    user_ns.setdefault("Scalar", Scalar)
    user_ns.setdefault("Vector", Vector)
    user_ns.setdefault("MultiComponent", MultiComponent)
    user_ns.setdefault("Spectrogram", Spectrogram)


@needs_local_scope
def vp_magic(line: str, cell: str, local_ns=None):
    """%%vp cell magic — define a virtual product from a function in the cell."""
    from SciQLop.user_api.virtual_products.types import extract_vp_type_info, VPTypeInfo

    user_ns = local_ns if local_ns is not None else {}
    _inject_type_names(user_ns)

    args = _parse_args(line)
    func = _extract_function(cell, user_ns)
    func_name = func.__name__

    try:
        return_ann = func.__annotations__.get("return")
        type_info = extract_vp_type_info(return_ann)
    except Exception:
        type_info = None

    # Evaluate callback when type must be inferred or debug is requested
    cached_data = None
    eval_error = None
    eval_elapsed = 0.0
    needs_eval = type_info is None or args.debug

    if needs_eval:
        start, stop = _resolve_time_range(args, func)
        t0 = _time.monotonic()
        try:
            cached_data = func(start, stop)
        except Exception as e:
            eval_error = e
            cached_data = None
            if not args.debug:
                _get_log().error(f"Cannot evaluate {func_name}: {e}")
                return
        eval_elapsed = _time.monotonic() - t0

    # Infer type from data if annotation was missing
    if eval_error is None and type_info is None:
        type_info = _infer_type_from_data(cached_data)
        _get_log().info(f"Inferred type: {type_info.product_type} — add return annotation to make explicit")

    # Fallback type for debug panel when eval failed
    if type_info is None:
        type_info = VPTypeInfo(product_type="scalar", labels=None)

    # Register (or hot-reload) the virtual product
    is_new = func_name not in _registry._entries
    entry = _registry.register(func_name, func, type_info.product_type, type_info.labels)

    if is_new or entry.signature_changed:
        _register_virtual_product(func_name, entry.wrapper, type_info.product_type,
                                  type_info.labels, args.path, cached_data=cached_data)

    if args.debug:
        from SciQLop.user_api.virtual_products.debug import handle_debug
        if not needs_eval:
            start, stop = _resolve_time_range(args, func)
        handle_debug(args, func, func_name, entry, type_info,
                     start, stop,
                     cached_data=cached_data, eval_error=eval_error,
                     eval_elapsed=eval_elapsed)

    return func, args, type_info


def _vp_magic_impl(line: str, cell: str, local_ns=None, **kwargs):
    """Backward-compatible entry point used by integration tests."""
    return vp_magic(line, cell, local_ns=local_ns)
