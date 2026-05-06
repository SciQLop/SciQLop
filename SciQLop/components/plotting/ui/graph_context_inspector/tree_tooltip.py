"""Hover tooltip on the inspector tree (PlotsTreeView) for graph rows.

PlotsModel doesn't supply ToolTipRole data — and we wouldn't want it to, since
the tooltip text depends on Python-side context attached after the C++ node is
created. So we install an event filter on the tree's viewport that resolves
the QObject behind the index via ``PlotsModel.object(index)`` and renders a
fresh tooltip from ``graph_tooltip(graph)`` on demand.
"""
from __future__ import annotations

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import QHelpEvent
from PySide6.QtWidgets import QToolTip, QTreeView

from SciQLopPlots import PlotsModel

from SciQLop.core.graph_context import graph_tooltip


class _TreeTooltipFilter(QObject):
    """Event filter installed on a QTreeView viewport — turns ToolTip events
    into per-graph context summaries.
    """

    def __init__(self, tree: QTreeView):
        super().__init__(tree)
        self._tree = tree

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.ToolTip and isinstance(event, QHelpEvent):
            idx = self._tree.indexAt(event.pos())
            if idx.isValid():
                obj_at = PlotsModel.object(idx)
                tip = graph_tooltip(obj_at) if obj_at is not None else ""
                if tip:
                    QToolTip.showText(event.globalPos(), tip, self._tree)
                    return True
                QToolTip.hideText()
        return super().eventFilter(obj, event)


def install_inspector_tree_tooltips(properties_panel) -> None:
    """Install per-graph hover tooltips on a PropertiesPanel's tree view.

    No-op if the panel has no PlotsTreeView child (e.g., during teardown).
    Idempotent — calling it twice keeps a single filter alive.
    """
    from SciQLopPlots import PlotsTreeView
    tree = properties_panel.findChild(PlotsTreeView)
    if tree is None:
        return
    viewport = tree.viewport()
    if getattr(viewport, "_graph_context_tooltip_filter", None) is not None:
        return
    flt = _TreeTooltipFilter(tree)
    viewport._graph_context_tooltip_filter = flt
    viewport.installEventFilter(flt)
