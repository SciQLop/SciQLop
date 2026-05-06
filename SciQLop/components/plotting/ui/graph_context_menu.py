"""Hierarchical 'Copy Python code' submenu for the panel context menu.

  Copy Python code ▶
      Panel "<name>"           — one SciQLop reproducer for the whole panel
      Plot 0 (Bx, By, Bz)      — reproducer for one plot's graphs
      Plot 1 (|B|)
      ───
      Bx ▶                     — per-graph variants from the provider
          Reproduce in SciQLop
          Notebook (matplotlib)
      By ▶
          ...

Aggregate items (Panel/Plot) only appear when there is at least one
source-bound graph to reproduce. Per-graph items only appear when the graph's
provider supplies snippets.
"""
from __future__ import annotations

from PySide6.QtGui import QGuiApplication

from SciQLopPlots import SciQLopGraphInterface

from SciQLop.core.graph_context import context_of, graph_name, provider_for
from SciQLop.components.plotting.ui.graph_context_snippets import (
    ordered_plots, panel_reproducer_snippet, plot_reproducer_snippet,
)


def _copy(text: str) -> None:
    QGuiApplication.clipboard().setText(text)


def _per_graph_variants(graph) -> dict:
    ctx = context_of(graph)
    if ctx is None:
        return {}
    provider = provider_for(ctx)
    if provider is None:
        return {}
    try:
        return provider.python_snippets(ctx, graph=graph) or {}
    except Exception:
        return {}


def _plot_label(plot, plot_index: int) -> str:
    graphs = plot.findChildren(SciQLopGraphInterface)
    names = ", ".join(graph_name(g) for g in graphs) or "empty"
    return f"Plot {plot_index} ({names})"


def add_graph_context_actions(menu, panel) -> None:
    """Append a 'Copy Python code ▶' submenu to ``menu`` for ``panel``.

    No-op if the panel has no graphs eligible for any snippet.
    """
    plots = ordered_plots(panel)

    panel_snippet = panel_reproducer_snippet(panel)
    plot_snippets = [(i, plot_reproducer_snippet(panel, i)) for i, _ in enumerate(plots)]
    plot_snippets = [(i, s) for i, s in plot_snippets if s]

    graph_variants = []
    for plot in plots:
        for g in plot.findChildren(SciQLopGraphInterface):
            variants = _per_graph_variants(g)
            if variants:
                graph_variants.append((g, variants))

    if not (panel_snippet or plot_snippets or graph_variants):
        return

    menu.addSeparator()
    sub = menu.addMenu("Copy Python code")

    if panel_snippet:
        title = panel.windowTitle() or "Panel"
        a = sub.addAction(f'Panel "{title}"')
        a.triggered.connect(lambda _checked=False, s=panel_snippet: _copy(s))

    for i, snippet in plot_snippets:
        a = sub.addAction(_plot_label(plots[i], i))
        a.triggered.connect(lambda _checked=False, s=snippet: _copy(s))

    if graph_variants and (panel_snippet or plot_snippets):
        sub.addSeparator()

    for graph, variants in graph_variants:
        graph_sub = sub.addMenu(graph_name(graph))
        for label, snippet in variants.items():
            if not snippet:
                continue
            a = graph_sub.addAction(label)
            a.triggered.connect(lambda _checked=False, s=snippet: _copy(s))
