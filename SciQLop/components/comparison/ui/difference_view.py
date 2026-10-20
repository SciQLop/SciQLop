"""Difference view: each changed base plot with its variant overlaid, then a row relating them."""
from __future__ import annotations

import logging
import math
from collections import Counter
from typing import Callable, NamedTuple, Optional, get_args

import numpy as np

from SciQLop.components.comparison.backend.checks import REMOTE_REFUSAL, compatible, is_remote
from SciQLop.components.comparison.backend.difference import (ComparisonMismatch, Operation, colormap_relation,
                                                               line_relation, mask_fill)
from SciQLop.components.comparison.backend.model import Comparison, GraphSpec, Side, changed_keys
from SciQLop.components.comparison.ui.inner_panel import build_inner_panel, product_labels, provider_and_node
from SciQLop.components.comparison.ui.overlay_view import add_ghost, base_graphs
from SciQLop.core.graph_context import graph_name
from SciQLop.core.plot_hints import PlotHints, merge_hints

log = logging.getLogger(__name__)

default_options = {"operation": "difference", "method": "linear"}
SYMBOLS = {"difference": "A − B", "ratio": "A / B", "log_ratio": "log₁₀(A / B)"}
METHOD_LABELS = {"linear": "linear interpolation", "nearest": "nearest sample"}
COLORMAP_OPERATION = "log_ratio"  # a spectrogram spans decades: only the log ratio reads well
MIXED_REFUSAL = "cannot relate a spectrogram to a line plot"


class ResolvedSide(NamedTuple):
    """One side of a relation, resolved on the main thread so the fetch callback never touches Qt."""
    provider: object
    node: object
    knobs: dict
    time_offset: float
    fill_value: Optional[float]
    hints: Optional[PlotHints] = None
    labels: Optional[list[str]] = None


def resolve_side(spec: GraphSpec) -> Optional[ResolvedSide]:
    from SciQLop.components.plotting.ui.time_sync_panel import _safe_plot_hints
    provider, node = provider_and_node(spec.path)
    if provider is None:
        return None
    hints = _safe_plot_hints(provider, node)
    return ResolvedSide(provider, node, spec.knobs, spec.time_offset, hints.fill_value, hints,
                        product_labels(provider, node))


def _side_hints(side: ResolvedSide, variable) -> PlotHints:
    """Static hints refined by the fetched variable; the provider's labels only fill a gap."""
    hints = side.hints or PlotHints()
    if variable is not None:
        hints = merge_hints(hints, _variable_hints(side, variable))
    return hints if hints.component_labels else hints.model_copy(update={"component_labels": side.labels})


def _variable_hints(side: ResolvedSide, variable) -> PlotHints:
    try:
        return side.provider.plot_hints_from_variable(side.node, variable)
    except Exception:
        log.debug("plot_hints_from_variable failed for %s", side.node, exc_info=True)
        return PlotHints()


def _oriented(buffers) -> list:
    """Ascending y, as _specgram_callback draws the base row."""
    from SciQLop.components.plotting.ui.time_sync_panel import _with_y_axis, _y_is_descending
    x, y, z = _with_y_axis(buffers)
    y, z = np.asarray(y), np.asarray(z)
    if _y_is_descending(y):
        return [x, y[..., ::-1].copy(), z[:, ::-1].copy()]
    return [x, y, z]


def _masked(buffers, fill_value: Optional[float]) -> list:
    *axes, values = buffers
    return [*axes, mask_fill(values, fill_value)]


def _fetch(side: ResolvedSide, start: float, stop: float, colormap: bool):
    """(buffers or None when there is no data, hints) of one side over [start, stop]."""
    from SciQLop.components.plotting.ui.time_sync_panel import shift_buffers
    variables = []
    result = side.provider._get_data(side.node, start + side.time_offset, stop + side.time_offset,
                                     on_variable=variables.append, knobs=side.knobs or None)
    result = shift_buffers(result, side.time_offset)
    result = result["data"] if isinstance(result, dict) else result
    hints = _side_hints(side, variables[0] if variables else None)
    if not result or len(result[0]) == 0:
        return None, hints
    fill_value = side.fill_value if side.fill_value is not None else hints.fill_value
    return _masked(_oriented(result) if colormap else list(result), fill_value), hints


def _empty(colormap: bool) -> list:
    return [np.empty(0)] * (3 if colormap else 2)


def _without_values(buffers: list) -> list:
    *axes, values = buffers
    return [*axes, np.full(np.shape(values), np.nan)]


def relation_callback(a: ResolvedSide, b: ResolvedSide, op: Operation, method: str,
                      colormap: bool) -> Callable[[float, float], list]:
    relate = colormap_relation if colormap else line_relation

    def relation(start: float, stop: float) -> list:
        # simplify: each side is fetched twice (ghost + relation); reuse the ghost's buffers when this gets slow.
        (buf_a, hints_a), (buf_b, hints_b) = (_fetch(side, start, stop, colormap) for side in (a, b))
        reason = compatible(hints_a, hints_b, colormap)
        if reason is not None:
            raise ComparisonMismatch(reason)
        if buf_a is None:
            return _empty(colormap)
        if buf_b is None:
            return _without_values(buf_a)
        return relate(buf_a, buf_b, op, method)

    return relation


def _operation(options: dict) -> Operation:
    op = options.get("operation", default_options["operation"])
    if op not in get_args(Operation):
        log.warning("unknown Difference operation %r, using %r", op, default_options["operation"])
        return default_options["operation"]
    return op


def _refusal(specs: tuple[GraphSpec, GraphSpec], resolved: tuple, colormap: bool) -> Optional[str]:
    if specs[0].is_colormap != specs[1].is_colormap:
        return MIXED_REFUSAL
    missing = next((spec.path for spec, side in zip(specs, resolved) if side is None), None)
    if missing is not None:
        return f"{missing} could not be plotted"
    if any(is_remote(spec.path) for spec in specs):
        return REMOTE_REFUSAL
    return compatible(*(_side_hints(side, None) for side in resolved), colormap)


def _scale(log: bool) -> str:
    return "log" if log else "linear"


def _relation_hints(hints: PlotHints, op: Operation, colormap: bool, y_log: bool) -> PlotHints:
    """The base's hints with the value axis named after the relation and linear: a difference or a
    log ratio goes negative, and the hints' scale would otherwise switch the axis back to log.
    A ratio has no unit; a spectrogram's bin axis keeps the base plot's scale."""
    axis = "z" if colormap else "y"
    value = getattr(hints, axis)
    symbol = SYMBOLS[op]
    update = {"label": f"{symbol} {value.label}" if value.label else symbol,
              "unit": value.unit if op == "difference" else None,
              "scale": "linear", "valid_range": None}
    changes = {axis: value.model_copy(update=update), "fill_value": None}
    if colormap:
        changes["y2"] = hints.y2.model_copy(update={"scale": _scale(y_log)})
    return hints.model_copy(update=changes)


def _keep_symmetric(axis) -> None:
    """A diverging scale centred on zero: whatever range the axis gets becomes ±max|range|."""
    from SciQLopPlots import SciQLopPlotRange

    def symmetrize(rng):
        half = max(abs(rng.start()), abs(rng.stop()))
        if half > 0 and not (math.isclose(rng.start(), -half) and math.isclose(rng.stop(), half)):
            axis.set_range(SciQLopPlotRange(-half, half))

    axis.range_changed.connect(symmetrize)
    symmetrize(axis.range())


def _show_refusal(panel, position: int, message: str) -> None:
    from SciQLopPlots import OverlayLevel, OverlayPosition, OverlaySizeMode, PlotType
    from SciQLop.components.plotting.ui.diagnostic_overlay import overlay_of
    plot = panel.create_plot(position, PlotType.TimeSeries)
    overlay_of(plot).show_message(message, OverlayLevel.Error, OverlaySizeMode.FitContent, OverlayPosition.Top)


def _plot_relation(panel, callback, name: str, labels: list[str], colormap: bool, y_log: bool):
    from SciQLopPlots import ColorGradient, GraphType, PlotType
    from SciQLop.components.plotting.ui.time_sync_panel import plot_function
    if not colormap:
        return plot_function(panel, callback, labels=labels, name=name, plot_type=PlotType.TimeSeries)
    plot, graph = plot_function(panel, callback, name=name, graph_type=GraphType.ColorMap, y_log_scale=y_log,
                                z_log_scale=False, plot_type=PlotType.TimeSeries)
    graph.set_gradient(ColorGradient.Coolwarm)
    _keep_symmetric(plot.z_axis())
    return plot, graph


def _add_relation(panel, specs: tuple[GraphSpec, GraphSpec], base_graph, op: Operation, method: str,
                  position: int) -> None:
    from SciQLop.components.plotting.ui.time_sync_panel import _get_or_create_registry
    colormap = any(spec.is_colormap for spec in specs)
    op = COLORMAP_OPERATION if colormap else op
    name = f"{graph_name(base_graph)}: {SYMBOLS[op]}"
    resolved = tuple(resolve_side(spec) for spec in specs)
    reason = _refusal(specs, resolved, colormap)
    if reason is not None:
        _show_refusal(panel, position, f"{name}: {reason}")
        return
    a, b = resolved
    hints = _side_hints(a, None)
    y_log = bool(base_graph.y_axis().log())
    plot, graph = _plot_relation(panel, relation_callback(a, b, op, method, colormap), name,
                                 list(hints.component_labels or [SYMBOLS[op]]), colormap, y_log)
    panel.move_plot(len(panel.plots()) - 1, position)
    _get_or_create_registry(plot).register(graph, _relation_hints(hints, op, colormap, y_log))


def _plot_position(panel, plot) -> int:
    from SciQLop.components.plotting.ui.time_sync_panel import _plot_key
    key = _plot_key(plot)
    return next(i for i, ptr in enumerate(panel.plots()) if _plot_key(ptr.data()) == key)


def build_difference(comparison: Comparison, sides: list[Side], options: dict,
                     time_range: Optional[tuple[float, float]], parent):
    panel, plots = build_inner_panel(comparison, time_range, parent)
    op, method = _operation(options), options.get("method", default_options["method"])
    graphs = base_graphs(plots, comparison.template())
    base, variant = sides
    variant_specs = {spec.key: spec for spec in variant.specs}
    keys = changed_keys(sides)
    added: Counter = Counter()
    for spec in sorted(base.specs, key=lambda s: s.key):
        if spec.key not in keys or spec.key not in graphs or spec.key not in variant_specs:
            continue
        plot, other = plots[spec.plot_index], variant_specs[spec.key]
        if not (spec.is_colormap or other.is_colormap):
            add_ghost(plot, other, graphs[spec.key], variant.label, 0)
        added[spec.plot_index] += 1
        _add_relation(panel, (spec, other), graphs[spec.key], op, method,
                      _plot_position(panel, plot) + added[spec.plot_index])
    return panel


def applies_difference(comparison: Comparison, sides: list[Side]) -> Optional[str]:
    if len(sides) != 2:
        return "Difference needs exactly two sides"
    return None if changed_keys(sides) else "nothing differs between the sides"
