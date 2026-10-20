"""sciqlop_compare and sciqlop_set_comparison_view: the agent face of SciQLop.user_api.comparison."""
from __future__ import annotations

from SciQLop.components.agents.tools.contributed import AgentTool

_COMPARE_SCHEMA = {
    "type": "object",
    "properties": {
        "panel": {"type": "string", "description": "Name of the base plot panel."},
        "over": {"type": "string", "description": "What changes: 'time', 'product' or 'settings'."},
        "variants": {"type": "array", "description": (
            "What to compare with. time: [start, stop] ISO date pairs; product: product paths; "
            "settings: objects of knob values.")},
        "view": {"type": "string", "description": "'overlay' (default) or 'difference'."},
        "labels": {"type": "array", "items": {"type": "string"}, "description": "One label per variant."},
        "target": {"type": "array", "items": {"type": "integer"}, "description": (
            "[plot_index, product_index] of the graph a product or settings variant changes; the first by default.")},
    },
    "required": ["panel", "over", "variants"],
}

_SET_VIEW_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "Name of the Comparison panel."},
        "view": {"type": "string", "description": "'overlay', 'difference' or a plugin's view id."},
        "options": {"type": "object", "description": (
            "View options, e.g. difference: {operation: difference|ratio|log_ratio, method: linear|nearest}.")},
    },
    "required": ["name", "view"],
}


def _views_line(comparison, sides) -> str:
    from SciQLop.components.comparison.backend.views import available_views
    return "; ".join(f"{view.id} ({reason or 'available'})" for view, reason in available_views(comparison, sides))


def describe(widget) -> str:
    from SciQLop.components.comparison.backend.dimensions import resolve_sides
    comparison = widget.comparison
    sides = resolve_sides(comparison)
    labels = ", ".join(side.label for side in sides)
    return (f"Comparison panel {widget.objectName()!r} over {comparison.dimension}: {len(sides)} sides ({labels}). "
            f"Showing {comparison.view}. Views: {_views_line(comparison, sides)}.")


def _comparison_widget(name: str):
    from SciQLop.components.comparison.ui.panel_kind import COMPARISON_PANEL
    from SciQLop.core.panel_kinds import KIND_PROPERTY
    from SciQLop.user_api.gui import get_main_window
    found = next((p for p in get_main_window().panels()
                  if p.objectName() == name and p.property(KIND_PROPERTY) == COMPARISON_PANEL), None)
    if found is None:
        raise ValueError(f"no comparison panel named {name!r}")
    return found


def _compare(payload: dict) -> str:
    from SciQLop.components.comparison.backend.dimensions import require_keys
    from SciQLop.user_api.comparison import compare
    require_keys(payload, "panel", "over", "variants")
    target = payload.get("target")
    handle = compare(payload["panel"], over=payload["over"], variants=payload["variants"],
                     view=payload.get("view", "overlay"), labels=payload.get("labels"),
                     target=tuple(target) if target else None)
    return describe(handle.panel)


def _set_view(payload: dict) -> str:
    from SciQLop.components.comparison.backend.dimensions import require_keys
    from SciQLop.components.comparison.backend.views import showing
    require_keys(payload, "name", "view")
    widget = _comparison_widget(payload["name"])
    widget.set_comparison(showing(widget.comparison, payload["view"], payload.get("options") or {}))
    return describe(widget)


COMPARISON_TOOLS = [
    AgentTool("sciqlop_compare", (
        "Open a Comparison panel: a plot panel next to variants of itself, over time (other events), "
        "product (another product in place of one graph) or settings (other knob values). "
        "Returns the panel name, its sides and which views apply, with the reason when one does not."),
        _COMPARE_SCHEMA, _compare, gated=True),
    AgentTool("sciqlop_set_comparison_view", (
        "Switch a Comparison panel between its views (overlay, difference) and set view options. "
        "Fails with the reason when the view cannot show the panel's sides."),
        _SET_VIEW_SCHEMA, _set_view, gated=True),
]
