"""Diagnostic overlay for debug panels — delegates to SciQLopPlots overlay API."""
from __future__ import annotations

from typing import TYPE_CHECKING, List

from PySide6.QtCore import Signal, QObject

if TYPE_CHECKING:
    from SciQLop.user_api.virtual_products.validation import Diagnostic

from SciQLopPlots import OverlayLevel, OverlaySizeMode, OverlayPosition


class _DiagnosticDispatcher(QObject):
    """Thread-safe dispatcher: emit signals from any thread, overlay updates in GUI thread."""
    diagnostics_ready = Signal(list)
    success_ready = Signal(int, str, str, float)
    clear_requested = Signal()


def _format_diagnostics(diagnostics: List[Diagnostic]) -> tuple[str, OverlayLevel]:
    has_error = any(d.level == "error" for d in diagnostics)
    lines = []
    for d in diagnostics:
        prefix = "[X]" if d.level == "error" else "[!]"
        lines.append(f"{prefix} {d.message}")
    text = "\n\n".join(lines)
    level = OverlayLevel.Error if has_error else OverlayLevel.Warning
    return text, level


def _format_success(n_points: int, shape: str, dtype: str, elapsed: float) -> str:
    return f"[ok] {n_points} pts, {shape} {dtype}, {elapsed:.2f}s"


class DiagnosticOverlay:
    """Thin adapter around SciQLopPlots per-plot overlay API.

    Manages overlays on all plots within a panel. Thread-safe via signal dispatch.
    """
    def __init__(self, panel):
        self._panel = panel
        self._dispatcher = _DiagnosticDispatcher()
        self._dispatcher.diagnostics_ready.connect(self._on_diagnostics)
        self._dispatcher.success_ready.connect(self._on_success)
        self._dispatcher.clear_requested.connect(self._on_clear)
        self._visible = False
        self._last_text = ""

    def _plots(self):
        try:
            return self._panel.plots()
        except (RuntimeError, AttributeError):
            return []

    def show_diagnostics(self, diagnostics: List[Diagnostic]):
        """Thread-safe: can be called from any thread."""
        self._dispatcher.diagnostics_ready.emit(diagnostics)

    def show_success(self, n_points: int, shape, dtype: str, elapsed: float):
        """Thread-safe: can be called from any thread."""
        self._dispatcher.success_ready.emit(n_points, str(shape), dtype, elapsed)

    def clear(self):
        """Thread-safe: can be called from any thread."""
        self._dispatcher.clear_requested.emit()

    def _on_diagnostics(self, diagnostics: List[Diagnostic]):
        text, level = _format_diagnostics(diagnostics)
        self._last_text = text
        self._visible = True
        size_mode = OverlaySizeMode.FullWidget if level == OverlayLevel.Error else OverlaySizeMode.FitContent
        for plot in self._plots():
            ov = plot.overlay()
            ov.show_message(text, level, size_mode, OverlayPosition.Top)

    def _on_success(self, n_points: int, shape: str, dtype: str, elapsed: float):
        text = _format_success(n_points, shape, dtype, elapsed)
        self._last_text = text
        self._visible = True
        plots = self._plots()
        if plots:
            ov = plots[0].overlay()
            ov.show_message(text, OverlayLevel.Info, OverlaySizeMode.Compact, OverlayPosition.Top)
            # Clear overlays on other plots
            for plot in plots[1:]:
                plot.overlay().clear_message()

    def _on_clear(self):
        self._last_text = ""
        self._visible = False
        for plot in self._plots():
            plot.overlay().clear_message()

    def isVisible(self):
        return self._visible

    def text(self):
        return self._last_text
