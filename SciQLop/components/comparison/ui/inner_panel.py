"""The base panel of a comparison, rebuilt read-only from its snapshot."""
from __future__ import annotations

from typing import Optional

from SciQLop.components.comparison.backend.model import Comparison, GraphSpec, template_at_range
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
