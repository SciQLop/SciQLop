"""Core contributions of the plotting component: the time-series plot kind (and, from Task 2, the core drop rules)."""
from SciQLop.core.plot_kinds import PLOT_KINDS, TIMESERIES, PlotKind


def _plot_timeseries(target, product, kwargs):
    from SciQLop.components.plotting.ui.coverage_notice import offer_jump_to_data
    from SciQLop.components.plotting.ui.time_sync_panel import _owning_time_sync_panel, _plot_product
    r = _plot_product(target, product, **kwargs)
    panel = _owning_time_sync_panel(target) if r is not None else None
    if panel is not None:
        offer_jump_to_data(panel, product)
    return r


PLOT_KINDS.contribute(PlotKind(TIMESERIES, "Time series", plot_product=_plot_timeseries), owner="sciqlop")
