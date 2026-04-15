"""Snapshot SciQLop state into JSON-serializable dicts for agent tool calls.

Uses the public user API (`SciQLop.user_api.gui.get_main_window`,
`SciQLop.user_api.plot.plot_panel`) instead of walking dock widgets, so we
don't depend on private class names or dock-manager wrapping details.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from SciQLop.user_api.gui import get_main_window
from SciQLop.user_api.plot import plot_panel as _plot_panel_by_name, PlotPanel


def _safe(call, default=None):
    try:
        return call()
    except Exception:
        return default


def _panel_names() -> List[str]:
    mw = _safe(get_main_window)
    if mw is None:
        return []
    return list(_safe(mw.plot_panels, []) or [])


def _panel(name: str) -> Optional[PlotPanel]:
    return _safe(lambda: _plot_panel_by_name(name))


def _time_range_dict(panel: PlotPanel) -> Dict[str, float] | None:
    tr = _safe(lambda: panel.time_range)
    if tr is None:
        return None
    start = _safe(tr.start)
    stop = _safe(tr.stop)
    if start is None or stop is None:
        return None
    return {"start": float(start), "stop": float(stop)}


def _panel_products(panel: PlotPanel) -> List[str]:
    products: List[str] = []
    for plot in _safe(lambda: panel.plots, []) or []:
        impl = getattr(plot, "_impl", None)
        if impl is None:
            continue
        for graph in _safe(lambda: impl.plottables(), []) or []:
            path = _safe(lambda g=graph: g.property("sqp_product_path"))
            if path:
                products.append(path)
    return products


def _panel_snapshot(panel: PlotPanel, name: str) -> Dict[str, Any]:
    return {
        "name": name,
        "time_range": _time_range_dict(panel),
        "products": _panel_products(panel),
    }


def _active_panel_name(main_window) -> Optional[str]:
    dock_manager = getattr(main_window, "dock_manager", None)
    if dock_manager is None:
        return None
    focused = _safe(dock_manager.focusedDockWidget)
    if focused is not None:
        name = _safe(focused.windowTitle, "") or ""
        if name in _panel_names():
            return name
    names = _panel_names()
    return names[0] if names else None


def main_window_snapshot(_main_window) -> Dict[str, Any]:
    mw = _safe(get_main_window)
    names = _panel_names()
    return {
        "window_title": _safe(lambda: mw.windowTitle(), "") if mw else "",
        "panel_count": len(names),
        "panel_names": names,
        "active_panel": active_panel_snapshot(_main_window),
    }


def list_panels(_main_window) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for name in _panel_names():
        p = _panel(name)
        if p is None:
            continue
        out.append({"name": name, "time_range": _time_range_dict(p)})
    return out


def active_panel_snapshot(main_window) -> Dict[str, Any] | None:
    name = _active_panel_name(main_window)
    if name is None:
        return None
    p = _panel(name)
    if p is None:
        return None
    return _panel_snapshot(p, name)


def _active_panel(main_window) -> Optional[PlotPanel]:
    name = _active_panel_name(main_window)
    if name is None:
        return None
    return _panel(name)
