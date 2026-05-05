"""Menu helper that adds per-graph 'Copy Python code' actions to a panel-level
context menu — one action per (graph × snippet variant) returned by the
graph's provider.
"""
from typing import Iterable

from PySide6.QtGui import QGuiApplication

from SciQLop.core.graph_context import context_of, provider_for


def add_graph_context_actions(menu, graphs: Iterable) -> None:
    """For each graph that has a context and whose provider returns at least
    one snippet variant, append 'Copy Python code [variant]' actions to the
    menu (or 'Copy Python code [variant]: <graph>' when more than one graph
    is eligible).
    """
    eligible = []  # list of (graph, variant_label, snippet)
    for g in graphs:
        ctx = context_of(g)
        if ctx is None:
            continue
        provider = provider_for(ctx)
        if provider is None:
            continue
        try:
            variants = provider.python_snippets(ctx, graph=g)
        except Exception:
            continue
        if not variants:
            continue
        for variant_label, snippet in variants.items():
            if snippet:
                eligible.append((g, variant_label, snippet))
    if not eligible:
        return
    menu.addSeparator()
    multi_graph = len({g for g, _, _ in eligible}) > 1
    for g, variant_label, snippet in eligible:
        if multi_graph:
            label = g.name() if hasattr(g, "name") else g.objectName()
            text = f"Copy Python code [{variant_label}]: {label}"
        else:
            text = f"Copy Python code [{variant_label}]"
        act = menu.addAction(text)
        act.triggered.connect(
            lambda _checked=False, s=snippet: QGuiApplication.clipboard().setText(s)
        )
