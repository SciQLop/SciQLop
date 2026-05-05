"""Menu helper that adds per-graph 'Copy Python code' actions to a panel-level
context menu.
"""
from typing import Iterable

from PySide6.QtGui import QGuiApplication

from SciQLop.core.graph_context import context_of, provider_for


def add_graph_context_actions(menu, graphs: Iterable) -> None:
    """For each graph that has both a context and a provider that can produce
    a snippet, add a 'Copy Python code: <name>' (or just 'Copy Python code'
    when there is only one graph) action to `menu`.
    """
    eligible = []
    for g in graphs:
        ctx = context_of(g)
        if ctx is None:
            continue
        provider = provider_for(ctx)
        if provider is None:
            continue
        snippet = None
        try:
            snippet = provider.python_snippet(ctx)
        except Exception:
            continue
        if not snippet:
            continue
        eligible.append((g, snippet))
    if not eligible:
        return
    menu.addSeparator()
    if len(eligible) == 1:
        g, snippet = eligible[0]
        act = menu.addAction("Copy Python code")
        act.triggered.connect(
            lambda _checked=False, s=snippet: QGuiApplication.clipboard().setText(s)
        )
        return
    for g, snippet in eligible:
        label = g.name() if hasattr(g, "name") else g.objectName()
        act = menu.addAction(f"Copy Python code: {label}")
        act.triggered.connect(
            lambda _checked=False, s=snippet: QGuiApplication.clipboard().setText(s)
        )
