"""Share a panel as a speasy-proxy ``/plot?config=…`` URL, and rebuild a
panel from such a URL.

Schema v1 of the proxy's interactive plot page (see speasy_proxy
``docs/plans/2026-03-08-multi-plot-design.md``): a base64url-encoded JSON
config with the time range and one entry per subplot listing its products.
Only Speasy-backed graphs are shareable — the proxy can't evaluate virtual
products, functions or static data, so those graphs are left out.
"""
from __future__ import annotations

import base64
import binascii
import json
import math
import re
from datetime import datetime, timezone
from typing import Iterable, Optional
from urllib.parse import parse_qs, urlsplit

from SciQLopPlots import ProductsModel, PlotType

from SciQLop.components import sciqlop_logging
from SciQLop.core import TimeRange
from SciQLop.core.graph_context import context_of, graph_name
from SciQLop.components.plotting.ui.graph_context_snippets import ordered_plots, plot_graphs

log = sciqlop_logging.getLogger(__name__)


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
    graphs = plot_graphs(plot)
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


# --- proxy URL → panel -------------------------------------------------------

def proxy_plot_config_from_text(text: str) -> Optional[dict]:
    """Decode a pasted proxy plot URL (or a bare ``config=…``) into a config
    dict, or None when the text isn't one."""
    encoded = _config_param(text.strip())
    if not encoded:
        return None
    try:
        padded = encoded + "=" * (-len(encoded) % 4)
        config = json.loads(base64.urlsafe_b64decode(padded))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return None
    return config if _is_plot_config(config) else None


def _config_param(text: str) -> Optional[str]:
    if text.startswith("config="):
        return text[len("config="):]
    if not re.match(r"^[a-z][a-z0-9+.-]*://", text, re.IGNORECASE):
        return None
    values = parse_qs(urlsplit(text).query).get("config")
    return values[0] if values else None


def _is_plot_config(config) -> bool:
    if not isinstance(config, dict) or not isinstance(config.get("plots"), list):
        return False
    time_range = config.get("time_range")
    if not isinstance(time_range, dict) or not (time_range.get("start") and time_range.get("stop")):
        return False
    return any(isinstance(p, dict) and p.get("products") for p in config["plots"])


def speasy_product_paths(speasy_ids: Iterable[str], root=None) -> dict[str, list[str]]:
    """Map each speasy id (``provider/uid``) to its product-tree path, in one
    walk of the Speasy subtree. Ids not in the tree are absent from the result.

    simplify: linear walk of the whole Speasy tree (~85k nodes, ~0.15 s);
    index speasy_id → node in the provider if this ever runs on a hot path.
    """
    wanted = set(speasy_ids)
    root = root if root is not None else ProductsModel.node(["speasy"])
    found: dict[str, list[str]] = {}
    stack = [root] if root is not None else []
    while stack and len(found) < len(wanted):
        node = stack.pop()
        speasy_id = node.metadata("speasy_id")
        if speasy_id in wanted:
            found[speasy_id] = list(node.path())
        stack.extend(node.children_nodes())
    return found


def apply_proxy_config(panel, config: dict) -> list[str]:
    """Rebuild ``config`` in ``panel``: set the time range, then one subplot
    per entry with its products. Returns the speasy ids that could not be
    plotted (unknown product or provider failure)."""
    panel.time_range = TimeRange(config["time_range"]["start"], config["time_range"]["stop"])
    ids = [p["path"] for entry in config["plots"] for p in entry.get("products", []) if p.get("path")]
    paths = speasy_product_paths(ids)
    skipped: list[str] = []
    for entry in config["plots"]:
        skipped.extend(_apply_subplot(panel, entry, paths))
    if skipped:
        log.warning("proxy config: products not plotted: %s", ", ".join(skipped))
    return skipped


def _apply_subplot(panel, entry: dict, paths: dict[str, list[str]]) -> list[str]:
    skipped: list[str] = []
    index: Optional[int] = None
    for product in entry.get("products", []):
        speasy_id = product.get("path")
        path = paths.get(speasy_id)
        result = _plot_product_on(panel, path, index) if path else None
        if result is None:
            skipped.append(speasy_id)
            continue
        if index is None:
            index = len(panel.plots()) - 1
    if index is not None:
        _apply_axis_scales(ordered_plots(panel)[index], entry)
    return skipped


def _plot_product_on(panel, path: list[str], index: Optional[int]):
    try:
        if index is None:
            return _plot_product(panel, path, plot_type=PlotType.TimeSeries)
        return _plot_product(panel, path, index=index)
    except Exception:
        log.warning("proxy config: plotting %s failed", path, exc_info=True)
        return None


def _plot_product(panel, path: list[str], **kwargs):
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product
    return plot_product(panel, path, **kwargs)


def _apply_axis_scales(plot, entry: dict) -> None:
    y_log = (entry.get("y_axis") or {}).get("log")
    if y_log is not None:
        plot.y_axis().set_log(bool(y_log))
    if entry.get("log_z") is not None:
        plot.z_axis().set_log(bool(entry["log_z"]))
