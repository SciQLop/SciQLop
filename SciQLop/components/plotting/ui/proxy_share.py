"""Speasy proxy ``/plot?config=…`` URLs, both ways, mapped through the shared
``PanelTemplate`` model.

Schema v1 of the proxy's interactive plot page (see speasy_proxy
``docs/plans/2026-03-08-multi-plot-design.md``): a base64url-encoded JSON
config with the time range and one entry per subplot listing its products.
Only Speasy-backed products are shareable — the proxy can't evaluate virtual
products, functions or static data, so those are left out.
"""
from __future__ import annotations

import base64
import binascii
import json
import re
from datetime import datetime
from typing import Iterable, Optional
from urllib.parse import parse_qs, urlsplit

from SciQLopPlots import ProductsModel

from SciQLop.components import sciqlop_logging
from SciQLop.components.plotting.panel_template import (
    AxisModel, PanelTemplate, PlotModel, ProductModel, TimeRangeModel,
)

log = sciqlop_logging.getLogger(__name__)


# --- panel → proxy URL ---------------------------------------------------------

def proxy_plot_url(panel, base_url: str) -> Optional[str]:
    config = proxy_plot_config(panel)
    if config is None:
        return None
    return f"{base_url.rstrip('/')}/plot?config={_base64url(config)}"


def proxy_plot_config(panel) -> Optional[dict]:
    return proxy_config_from_template(PanelTemplate.from_panel(panel))


def proxy_config_from_template(template: PanelTemplate) -> Optional[dict]:
    plots = [cfg for cfg in map(_plot_config, template.plots) if cfg]
    if template.time_range is None or not plots:
        return None
    time_range = {"start": _iso_z(template.time_range.start), "stop": _iso_z(template.time_range.stop)}
    return {"version": 1, "time_range": time_range, "plots": plots}


def _plot_config(plot: PlotModel) -> Optional[dict]:
    products = [_product_config(p) for p in plot.products if p.kind == "speasy" and p.speasy_id]
    if not products:
        return None
    config = {"products": products, "y_axis": {"log": plot.y_axis.log}}
    if any(p.is_colormap for p in plot.products):
        config["log_z"] = plot.z_axis.log
    return config


def _product_config(product: ProductModel) -> dict:
    config = {"path": product.speasy_id, "label": product.label}
    if product.knobs:
        config["product_inputs"] = dict(product.knobs)
    return config


def _iso_z(iso: str) -> str:
    return datetime.fromisoformat(iso).strftime("%Y-%m-%dT%H:%M:%SZ")


def _base64url(config: dict) -> str:
    raw = json.dumps(config, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


# --- proxy URL → panel ---------------------------------------------------------

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
    """Rebuild ``config`` in ``panel``. Returns the speasy ids that are not in
    the product tree (they are left out)."""
    template, skipped = template_from_proxy_config(config)
    if skipped:
        log.warning("proxy config: products not in the tree: %s", ", ".join(skipped))
    template.apply(panel)
    return skipped


def template_from_proxy_config(config: dict) -> tuple[PanelTemplate, list[str]]:
    ids = [p["path"] for entry in config["plots"] for p in entry.get("products", []) if p.get("path")]
    paths = speasy_product_paths(ids)
    plots = [plot for plot in (_plot_model(entry, paths) for entry in config["plots"]) if plot.products]
    template = PanelTemplate(
        name="Speasy proxy",
        time_range=TimeRangeModel(start=config["time_range"]["start"], stop=config["time_range"]["stop"]),
        plots=plots,
    )
    return template, [i for i in ids if i not in paths]


def _plot_model(entry: dict, paths: dict[str, list[str]]) -> PlotModel:
    products = [_product_model(p, paths[p["path"]]) for p in entry.get("products", [])
                if p.get("path") in paths]
    return PlotModel(
        products=products,
        y_axis=AxisModel(log=bool((entry.get("y_axis") or {}).get("log", False))),
        z_axis=AxisModel(log=bool(entry.get("log_z", False))),
    )


def _product_model(product: dict, path: list[str]) -> ProductModel:
    return ProductModel(path="//".join(path), label=product.get("label") or product["path"],
                        kind="speasy", speasy_id=product["path"],
                        knobs=dict(product.get("product_inputs") or {}))
