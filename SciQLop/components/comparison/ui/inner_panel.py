"""The base panel of a comparison, rebuilt read-only from its snapshot."""
from __future__ import annotations

from typing import Optional

from SciQLop.components.comparison.backend.model import Comparison, GraphSpec, Side, template_at_range
from SciQLop.components.plotting.panel_introspection import ordered_panel_plots
from SciQLop.components.plotting.panel_template import resolve_product_path
from SciQLop.core.plot_hints import PlotHints


def build_inner_panel(comparison: Comparison, time_range: Optional[tuple[float, float]], parent):
    """The panel and, index-aligned with the base plots, the plot each one became (None: nothing restored)."""
    from SciQLop.components.plotting.ui.time_sync_panel import TimeSyncPanel
    from SciQLop.core import TimeRange
    template = template_at_range(comparison.template(), time_range)
    panel = TimeSyncPanel(name=template.name, parent=parent,
                          time_range=TimeRange(*time_range) if time_range is not None else None,
                          read_only=True)
    return panel, template.apply(panel)


def side_letter(index: int) -> str:
    """A, B, C… as sides are named in the legends and in "A − B"."""
    return chr(ord("A") + index) if index < 26 else str(index + 1)


def mark_alignment(panel, sides: list[Side]) -> list:
    """A dotted line on every plot where the events line up: side A's anchor, onto which each variant is shifted.
    Python owns plot items, so the caller keeps the returned lines for as long as they should show."""
    t0 = sides[0].t0
    return [] if t0 is None else [_alignment_line(plot, t0) for plot in ordered_panel_plots(panel)]


def _alignment_line(plot, t0: float):
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPalette
    from SciQLopPlots import SciQLopVerticalLine
    line = SciQLopVerticalLine(plot, t0, False)
    line.set_line_style(Qt.PenStyle.DotLine)
    line.set_color(plot.palette().color(QPalette.ColorRole.WindowText))
    line.set_tool_tip("the events line up here")
    return line


def name_base_graphs(graphs: dict, keys, side: Side) -> None:
    from SciQLop.core.graph_context import graph_name
    for key in keys:
        if key in graphs:
            graphs[key].set_name(f"{graph_name(graphs[key])} — A: {side.label}")


def resolve_hints(spec: GraphSpec) -> Optional[PlotHints]:
    """Main thread only: the provider's hints for the spec's product, None when it is not in the tree."""
    return hints_for_path(spec.path)


def provider_and_node(path: str) -> tuple:
    """Main thread only: (provider, node) of a products-tree path; each None when unknown."""
    from SciQLopPlots import ProductsModel
    from SciQLop.components.plotting.backend.data_provider import providers
    node = ProductsModel.node(resolve_product_path(path)) if path else None
    return (providers.get(node.provider()) if node is not None else None), node


def hints_for_path(path: str) -> Optional[PlotHints]:
    from SciQLop.components.plotting.ui.time_sync_panel import _safe_plot_hints
    provider, node = provider_and_node(path)
    if provider is None:
        return None
    hints = _safe_plot_hints(provider, node)
    return hints if hints.component_labels else hints.model_copy(
        update={"component_labels": product_labels(provider, node)})


def product_labels(provider, node) -> list[str] | None:
    try:
        labels = [label for label in (provider.labels(node) or []) if label]
    except Exception:
        return None
    return labels or None
