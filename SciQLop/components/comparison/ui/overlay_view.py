"""Overlay view: the base panel with a faded, dashed ghost of each variant on top."""
from __future__ import annotations

from collections import Counter
from datetime import timedelta
from typing import Optional

from SciQLop.components.comparison.backend.checks import compatible
from SciQLop.components.comparison.backend.model import Comparison, GraphSpec, Key, Side, changed_keys
from SciQLop.components.comparison.ui.inner_panel import build_inner_panel, hints_for_path, resolve_hints
from SciQLop.components.comparison.ui.ghost_watch import GhostWatch
from SciQLop.components.plotting.panel_template import PanelTemplate, _place_on_axis, resolve_product_path
from SciQLop.core.graph_context import graph_name

MANY_VARIANTS = 6
LONGER_TOLERANCE = 1.10


def _tree_path(path: str) -> str:
    return "//".join(resolve_product_path(path))


def note(plot, message: str) -> None:
    """Adds an Info line to the plot's overlay.

    simplify: appends to whatever Info text is shown; a fetch error replacing it later drops these notes.
    """
    from SciQLopPlots import OverlayLevel, OverlayPosition, OverlaySizeMode
    from SciQLop.components.plotting.ui.diagnostic_overlay import overlay_of
    overlay = overlay_of(plot)
    shown = overlay.text() if overlay.level() == OverlayLevel.Info else ""
    if message in shown.split("\n"):
        return
    overlay.show_message(f"{shown}\n{message}" if shown else message, OverlayLevel.Info,
                         OverlaySizeMode.FitContent, OverlayPosition.Top)


def _plot_base_graphs(plot, products) -> dict[int, object]:
    """Product index -> its graph; the n-th product of a path is the n-th graph of that path,
    since a product that failed to plot fails for every copy of its path."""
    from SciQLop.components.plotting.panel_introspection import plot_graphs
    by_path: dict[str, list] = {}
    for graph in plot_graphs(plot):
        by_path.setdefault(graph.property("sqp_product_path") or "", []).append(graph)
    seen: Counter = Counter()
    found = {}
    for j, product in enumerate(products):
        if not product.path:
            continue
        path = _tree_path(product.path)
        graphs = by_path.get(path, [])
        if seen[path] < len(graphs):
            found[j] = graphs[seen[path]]
        seen[path] += 1
    return found


def base_graphs(plots: list, template: PanelTemplate) -> dict[Key, object]:
    return {(i, j): graph
            for i, (plot, model) in enumerate(zip(plots, template.plots)) if plot is not None
            for j, graph in _plot_base_graphs(plot, model.products).items()}


def add_ghost(plot, spec: GraphSpec, base_graph, label: str, index: int):
    from SciQLop.components.plotting.ui.time_sync_panel import plot_product, _graph_from_result
    statics = (hints_for_path(base_graph.property("sqp_product_path") or ""), resolve_hints(spec))
    reason = compatible(*statics, spec.is_colormap)
    if reason is not None:
        note(plot, f"{label}: not overlaid — {reason}")
        return None
    r = plot_product(plot, resolve_product_path(spec.path), time_offset=spec.time_offset,
                     product_inputs=spec.knobs or None)
    if r is None:
        note(plot, f"{label}: {spec.path} could not be plotted")
        return None
    graph = _graph_from_result(r)
    _place_on_axis(plot, graph, spec.y_axis)
    graph.set_name(f"{graph_name(base_graph)} — {label}")
    GhostWatch(plot, graph, base_graph, index, label, statics)
    return graph


def _colormap_keys(sides: list[Side], keys: set[Key]) -> set[Key]:
    return {s.key for side in sides for s in side.specs if s.key in keys and s.is_colormap}


def _add_ghosts(plots: list, graphs: dict, sides: list[Side], keys: set[Key]) -> None:
    for index, side in enumerate(sides[1:]):
        for spec in side.specs:
            if spec.key in keys and spec.key in graphs:
                add_ghost(plots[spec.plot_index], spec, graphs[spec.key], side.label, index)


def _note_colormaps(plots: list, keys: set[Key]) -> None:
    for plot_index in sorted({k[0] for k in keys}):
        if plots[plot_index] is not None:
            note(plots[plot_index], "spectrogram variants are not shown in Overlay — use Difference")


def _summary_notes(sides: list[Side]) -> list[str]:
    base, variants = sides[0], sides[1:]
    notes = []
    if len(variants) > MANY_VARIANTS:
        notes.append("many variants — an Epoch view will summarise them better")
    if base.duration and any((v.duration or 0) > base.duration * LONGER_TOLERANCE for v in variants):
        shown = timedelta(seconds=round(base.duration))
        notes.append(f"some variants are longer than the view; only the first {shown} are shown")
    return notes


def _first_plot(plots: list):
    return next((p for p in plots if p is not None), None)


def build_overlay(comparison: Comparison, sides: list[Side], options: dict,
                  time_range: Optional[tuple[float, float]], parent):
    panel, plots = build_inner_panel(comparison, time_range, parent)
    keys = changed_keys(sides)
    colormaps = _colormap_keys(sides, keys)
    _add_ghosts(plots, base_graphs(plots, comparison.template()), sides, keys - colormaps)
    _note_colormaps(plots, colormaps)
    first = _first_plot(plots)
    for message in _summary_notes(sides) if first is not None else []:
        note(first, message)
    return panel


def applies_overlay(comparison: Comparison, sides: list[Side]) -> Optional[str]:
    return None if changed_keys(sides) else "nothing differs between the sides"
