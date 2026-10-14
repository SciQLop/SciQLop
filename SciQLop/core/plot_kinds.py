"""How products are plotted and how plots are saved: the sciqlop.plot_kinds extension point (spec §4.3, §5)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from SciQLop.components.sciqlop_logging import getLogger
from SciQLop.core.extensions import ExtensionPoint, declare

log = getLogger(__name__)

TIMESERIES, PROJECTION, TIME_PANEL = "sciqlop.timeseries", "sciqlop.scenes.projection", "sciqlop.time_panel"


def _never(plot) -> bool:
    return False


@dataclass(frozen=True)
class PlotKind:
    id: str
    label: str
    plot_product: Callable[[Any, list, dict], Any]       # (target panel or plot, product path, kwargs) -> (plot, graph)
    owns: Callable[[Any], bool] = _never                 # is this existing plot one of this kind
    to_config: Optional[Callable[[Any], dict]] = None    # what a template saves; None: not saved
    from_config: Optional[Callable[[Any, dict], Any]] = None  # (panel, config) -> the user-facing plot, or None


PLOT_KINDS = declare(ExtensionPoint("sciqlop.plot_kinds", PlotKind, what="plot kind",
                                    doc="Plots a panel can hold: how products go on them, how they are saved."))


def plugin_of(kind_id: str) -> str:
    return kind_id.split(".", 1)[0]


def plot_kind_of(plot) -> Optional[PlotKind]:
    """The kind that owns *plot*; a plot no plugin claims is a time-series plot."""
    if plot is None:
        return None
    claimed = (k for k in PLOT_KINDS.list() if k.id != TIMESERIES and k.owns(plot))
    return next(claimed, None) or PLOT_KINDS.get(TIMESERIES)


def plot_kind_for_product(product) -> Optional[PlotKind]:
    """The default plot kind of the product's kind; None for unknown products or when that plot kind's plugin
    is not loaded."""
    from SciQLopPlots import ProductsModel
    from SciQLop.core.product_kinds import product_kind_of
    if not isinstance(product, list):
        return None
    node = ProductsModel.node(product)
    kind = product_kind_of(node) if node is not None else None
    if kind is None:
        return None
    if kind.default_plot_kind not in PLOT_KINDS:
        log.warning(f"{'/'.join(product)}: plot kind {kind.default_plot_kind!r} is not available "
                    f"(plugin {plugin_of(kind.default_plot_kind)!r} not loaded)")
        return None
    return PLOT_KINDS.get(kind.default_plot_kind)
