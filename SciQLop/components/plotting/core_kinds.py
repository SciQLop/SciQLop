"""Core contributions of the plotting component: the time-series plot kind (and, from Task 2, the core drop rules)."""
from SciQLop.core.drop_rules import DROP_RULES, DropRule
from SciQLop.core.mime.types import CATALOG_LIST_MIME_TYPE, PRODUCT_LIST_MIME_TYPE, TIME_RANGE_MIME_TYPE
from SciQLop.core.plot_kinds import PLOT_KINDS, TIMESERIES, PlotKind
from SciQLop.core.product_kinds import LAYER


def _plot_timeseries(target, product, kwargs):
    from SciQLop.components.plotting.ui.coverage_notice import offer_jump_to_data
    from SciQLop.components.plotting.ui.time_sync_panel import _owning_time_sync_panel, _plot_product
    r = _plot_product(target, product, **kwargs)
    panel = _owning_time_sync_panel(target) if r is not None else None
    if panel is not None:
        offer_jump_to_data(panel, product)
    return r


PLOT_KINDS.contribute(PlotKind(TIMESERIES, "Time series", plot_product=_plot_timeseries), owner="sciqlop")


def _plot_product_drop(plot, product, panel):
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product
    plot_product(plot, product)


def _zoom(plot, time_range, panel):
    plot.time_axis().set_range(time_range)


def _overlay_catalogs(plot, catalogs, panel):
    for cat in catalogs or []:
        panel.catalog_manager.add_catalog(cat)


def _attach_layer(plot, product, panel):
    from SciQLop.components.plotting.ui.time_sync_panel import attach_layer
    return attach_layer(plot, product, panel=panel)


for _rule in (DropRule("sciqlop.plot_product", PRODUCT_LIST_MIME_TYPE, _plot_product_drop, creates_plot=True),
              DropRule("sciqlop.layers.attach", PRODUCT_LIST_MIME_TYPE, _attach_layer, product_kind=LAYER),
              DropRule("sciqlop.time_range", TIME_RANGE_MIME_TYPE, _zoom),
              DropRule("sciqlop.catalogs.overlay", CATALOG_LIST_MIME_TYPE, _overlay_catalogs)):
    DROP_RULES.contribute(_rule, owner="sciqlop")
