"""Whether two sides' graphs can share a plot or be subtracted; pure, takes already-resolved hints."""
from __future__ import annotations

from typing import Optional

from SciQLop.core.plot_hints import PlotHints

# simplify: plot_remote ignores time offsets and the Difference view fetches in-process; apply the offset where
# plot_remote builds its request, and fetch through the worker, to support remote products.
REMOTE_REFUSAL = "remote products are not supported in the Difference view"
REMOTE_SHIFT_REFUSAL = "remote products cannot be shifted in time yet"


def _value_unit(hints: Optional[PlotHints], colormap: bool) -> Optional[str]:
    if hints is None:
        return None
    return (hints.z if colormap else hints.y).unit


def _units_differ(a: Optional[PlotHints], b: Optional[PlotHints], colormap: bool) -> Optional[str]:
    ua, ub = _value_unit(a, colormap), _value_unit(b, colormap)
    if ua and ub and ua != ub:
        return f"different units: {ua} vs {ub}"
    return None


def _components_differ(a: Optional[PlotHints], b: Optional[PlotHints]) -> Optional[str]:
    ca, cb = (h.component_labels if h is not None else None for h in (a, b))
    if ca and cb and list(ca) != list(cb):
        return f"different components: {'/'.join(ca)} vs {'/'.join(cb)}"
    return None


def compatible(a: Optional[PlotHints], b: Optional[PlotHints], colormap: bool) -> Optional[str]:
    """None when comparable; otherwise why not. What one side does not know is allowed."""
    return _units_differ(a, b, colormap) or _components_differ(a, b)


def is_remote(path: str) -> bool:
    from SciQLop.components.plotting.backend.remote.registry import remote_registry
    from SciQLop.components.plotting.panel_template import resolve_product_path
    return remote_registry().is_remote(resolve_product_path(path))
