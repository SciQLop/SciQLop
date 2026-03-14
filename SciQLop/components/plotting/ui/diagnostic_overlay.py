from __future__ import annotations

from typing import TYPE_CHECKING, List

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtWidgets import QLabel, QWidget, QVBoxLayout

if TYPE_CHECKING:
    from SciQLop.user_api.virtual_products.validation import Diagnostic


class _DiagnosticDispatcher(QObject):
    """Thread-safe dispatcher: emit signals from any thread, overlay updates in GUI thread."""
    diagnostics_ready = Signal(list)
    success_ready = Signal(int, str, str, float)
    clear_requested = Signal()


class DiagnosticOverlay(QWidget):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._label = QLabel(self)
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        self._label.setTextFormat(Qt.TextFormat.PlainText)
        self._label.setMargin(12)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        self._dispatcher = _DiagnosticDispatcher()
        self._dispatcher.diagnostics_ready.connect(self._on_diagnostics)
        self._dispatcher.success_ready.connect(self._on_success)
        self._dispatcher.clear_requested.connect(self._on_clear)

        self._is_status_bar = False  # True for success (bottom bar), False for error (full overlay)

        if parent:
            parent.installEventFilter(self)

        self.hide()

    def eventFilter(self, obj, event):
        from PySide6.QtCore import QEvent
        if obj is self.parent() and event.type() == QEvent.Type.Resize:
            self._resize_to_parent()
        return False

    def _apply_style(self, bg_color: str, text_color: str):
        self.setStyleSheet(
            f"background-color: {bg_color}; color: {text_color}; font-family: monospace; font-size: 12px;"
        )

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
        has_error = any(d.level == "error" for d in diagnostics)
        lines = []
        for d in diagnostics:
            prefix = "[X]" if d.level == "error" else "[!]"
            lines.append(f"{prefix} {d.message}")

        self._label.setText("\n\n".join(lines))
        if has_error:
            self._apply_style("rgba(180, 40, 40, 200)", "#ffffff")
        else:
            self._apply_style("rgba(180, 140, 20, 200)", "#ffffff")
        self._is_status_bar = False
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._resize_to_parent()
        self.show()
        self.raise_()

    def _on_success(self, n_points: int, shape: str, dtype: str, elapsed: float):
        self._label.setText(f"[ok] {n_points} pts, {shape} {dtype}, {elapsed:.2f}s")
        self._apply_style("rgba(40, 140, 40, 180)", "#ffffff")
        self._is_status_bar = True
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._resize_to_parent()
        self.show()
        self.raise_()

    def _on_clear(self):
        self._label.setText("")
        self.hide()

    def _resize_to_parent(self):
        if not self.parent():
            return
        parent_rect = self.parent().rect()
        if self._is_status_bar:
            bar_height = 24
            self.setGeometry(
                parent_rect.x(),
                parent_rect.bottom() - bar_height,
                parent_rect.width(),
                bar_height,
            )
        else:
            self.setGeometry(parent_rect)
