"""Finishes a ghost once data arrives: its style needs both graphs' components, and the
compatibility check gets the hints the first fetch refines (units, labels from the data)."""
from __future__ import annotations

from functools import partial

from PySide6.QtCore import QObject, QTimer, Slot

from SciQLop.components.comparison.backend.checks import compatible
from SciQLop.components.comparison.ui.styling import ghost_style
from SciQLop.core.plot_hints import PlotHints, merge_hints


def _merged(registered: PlotHints | None, static: PlotHints | None) -> PlotHints | None:
    if registered is None or static is None:
        return registered or static
    return merge_hints(registered, static)


def _refuse(plot_key: int, ghost_key: int, message: str) -> None:
    from SciQLop.components.comparison.ui.overlay_view import note
    from SciQLop.components.plotting.ui.time_sync_panel import hints_registry_of
    reg = hints_registry_of(plot_key)
    ghost = reg.graph_for_key(ghost_key) if reg is not None else None
    if ghost is not None:
        reg.plot.remove_plottable(ghost)
        note(reg.plot, message)


class GhostWatch(QObject):
    """Owned by the ghost. Holds only C++-pointer keys: a wrapper of its own parent in
    __dict__ is a cycle GC breaks by emptying __dict__, and shiboken does not keep wrapper identity."""

    def __init__(self, plot, ghost, base, index: int, label: str, statics: tuple):
        from SciQLop.components.plotting.ui.time_sync_panel import _graph_key, _plot_key
        super().__init__(ghost)
        self._plot_key, self._ghost_key, self._base_key = _plot_key(plot), _graph_key(ghost), _graph_key(base)
        self._index, self._label, self._statics = index, label, statics
        self._styled = ghost_style(ghost, base, index)
        self._checked = False
        ghost.data_changed[()].connect(self._on_data)
        base.data_changed[()].connect(self._on_data)

    def _graphs(self):
        from SciQLop.components.plotting.ui.time_sync_panel import hints_registry_of
        reg = hints_registry_of(self._plot_key)
        if reg is None:
            return None, None, None
        return reg, reg.graph_for_key(self._ghost_key), reg.graph_for_key(self._base_key)

    @Slot()
    def _on_data(self):
        reg, ghost, base = self._graphs()
        if ghost is None or base is None:
            return
        if not self._styled:
            self._styled = ghost_style(ghost, base, self._index)
        if not self._checked and ghost.components() and base.components():
            self._checked = True
            self._check(reg)
        if self._styled and self._checked:
            ghost.data_changed[()].disconnect(self._on_data)
            base.data_changed[()].disconnect(self._on_data)

    def _check(self, reg) -> None:
        base_static, ghost_static = self._statics
        reason = compatible(_merged(reg.hints_for(self._base_key), base_static),
                            _merged(reg.hints_for(self._ghost_key), ghost_static), False)
        if reason is not None:
            # Deferred: removing the ghost deletes this object, which is still inside its slot.
            QTimer.singleShot(0, reg.plot, partial(_refuse, self._plot_key, self._ghost_key,
                                                   f"{self._label}: not overlaid — {reason}"))
