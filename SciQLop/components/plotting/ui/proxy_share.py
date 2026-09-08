"""Share a panel as a speasy-proxy ``/plot?config=…`` URL.

Schema v1 of the proxy's interactive plot page (see speasy_proxy
``docs/plans/2026-03-08-multi-plot-design.md``): a base64url-encoded JSON
config with the time range and one entry per subplot listing its products.
Only Speasy-backed graphs are shareable — the proxy can't evaluate virtual
products, functions or static data, so those graphs are left out.
"""
from __future__ import annotations

import base64
import json
import math
from datetime import datetime, timezone
from typing import Optional

from SciQLopPlots import SciQLopGraphInterface

from SciQLop.core.graph_context import context_of, graph_name
from SciQLop.components.plotting.ui.graph_context_snippets import ordered_plots


def proxy_plot_url(panel, base_url: str) -> Optional[str]:
    config = proxy_plot_config(panel)
    if config is None:
        return None
    return f"{base_url.rstrip('/')}/plot?config={_base64url(config)}"


def proxy_plot_config(panel) -> Optional[dict]:
    time_range = _iso_range(panel)
    plots = [cfg for cfg in map(_plot_config, ordered_plots(panel)) if cfg]
    if time_range is None or not plots:
        return None
    return {"version": 1, "time_range": time_range, "plots": plots}


def _plot_config(plot) -> Optional[dict]:
    graphs = plot.findChildren(SciQLopGraphInterface)
    products = [p for p in map(_product, graphs) if p]
    if not products:
        return None
    config = {"products": products, "y_axis": {"log": bool(plot.y_axis().log())}}
    if any(_is_colormap(g) for g in graphs):
        config["log_z"] = bool(plot.z_axis().log())
    return config


def _product(graph) -> Optional[dict]:
    ctx = context_of(graph)
    if ctx is None or ctx.kind != "speasy" or not ctx.speasy_id:
        return None
    product = {"path": ctx.speasy_id, "label": graph_name(graph)}
    if ctx.knobs:
        product["product_inputs"] = dict(ctx.knobs)
    return product


def _is_colormap(graph) -> bool:
    ctx = context_of(graph)
    return ctx is not None and "ColorMap" in ctx.graph_type


def _iso_range(panel) -> Optional[dict]:
    """``{"start", "stop"}`` as ISO-8601 Z strings, or None while the panel
    has no finite range yet (fresh panel before its first plot)."""
    r = panel.time_axis_range()
    start, stop = float(r.start()), float(r.stop())
    if not (math.isfinite(start) and math.isfinite(stop)):
        return None
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    return {"start": datetime.fromtimestamp(start, tz=timezone.utc).strftime(fmt),
            "stop": datetime.fromtimestamp(stop, tz=timezone.utc).strftime(fmt)}


def _base64url(config: dict) -> str:
    raw = json.dumps(config, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
