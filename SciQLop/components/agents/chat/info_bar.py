"""Session-info strip shown under the chat input.

Renders whatever the backend reports and nothing more: a backend supplying only
token counts gets one segment, one supplying context limits also gets a meter.
The whole widget hides when there is nothing to say.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..backend import UsageSnapshot
from .formatters import fmt_carbon, fmt_cost, fmt_duration, fmt_tokens, info_segments


class TokenBar(QProgressBar):
    """A slim, textless meter. Height derives from the font's x-height so it
    scales with the UI instead of using a hardcoded pixel size."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setTextVisible(False)
        self.setRange(0, 100)
        self.setFixedHeight(max(4, int(self.fontMetrics().xHeight())))


class SessionInfoBar(QWidget):
    details_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._snapshot: Optional[UsageSnapshot] = None
        self._effort: Optional[str] = None

        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)

        self._label = QLabel("", self)
        self._label.setStyleSheet("color: gray;")
        row.addWidget(self._label)

        self.meter = TokenBar(self)
        self.meter.setMaximumWidth(80)
        row.addWidget(self.meter)

        self.details_button = QToolButton(self)
        self.details_button.setText("ⓘ")
        self.details_button.setAutoRaise(True)
        self.details_button.setToolTip("Show the context breakdown for this session.")
        self.details_button.clicked.connect(self.details_requested)
        row.addWidget(self.details_button)

        row.addStretch(1)
        self._render()

    @property
    def snapshot(self) -> Optional[UsageSnapshot]:
        return self._snapshot

    def text(self) -> str:
        """The joined segment text — the strip's whole textual content."""
        return self._label.text()

    def set_snapshot(self, snapshot: Optional[UsageSnapshot]) -> None:
        self._snapshot = snapshot
        self._render()

    def set_effort(self, effort: Optional[str]) -> None:
        self._effort = effort
        self._render()

    def _render(self) -> None:
        segments = info_segments(self._snapshot, self._effort)
        self._label.setText(" · ".join(segments))

        percent = self._snapshot.context_percent if self._snapshot else None
        self.meter.setVisible(percent is not None)
        if percent is not None:
            self.meter.setValue(int(round(percent)))

        has_breakdown = bool(self._snapshot and self._snapshot.context_categories)
        self.details_button.setVisible(has_breakdown)

        self.setVisible(bool(segments))


class ContextBreakdownPopup(QWidget):
    """Context-window breakdown, opened from the strip's ⓘ button.

    A `Qt.Popup` rather than a dialog so clicking away dismisses it.
    """

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self._snapshot: Optional[UsageSnapshot] = None
        self.category_rows: list[tuple[str, str]] = []

        outer = QVBoxLayout(self)
        self._title = QLabel("", self)
        outer.addWidget(self._title)

        self._grid_host = QWidget(self)
        self._grid = QGridLayout(self._grid_host)
        self._grid.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self._grid_host)

        self._footer = QLabel("", self)
        self._footer.setStyleSheet("color: gray;")
        outer.addWidget(self._footer)

    def footer_text(self) -> str:
        return self._footer.text()

    def set_snapshot(self, snapshot: Optional[UsageSnapshot]) -> None:
        self._snapshot = snapshot
        self._render_title()
        self._render_categories()
        self._footer.setText(self._build_footer())

    def _render_title(self) -> None:
        snapshot = self._snapshot
        if snapshot is None or snapshot.context_max is None:
            self._title.setText("Context")
            return
        used = fmt_tokens(snapshot.context_tokens)
        total = fmt_tokens(snapshot.context_max)
        percent = snapshot.context_percent
        suffix = f", {percent:.0f}%" if percent is not None else ""
        self._title.setText(f"Context ({used} / {total}{suffix})")

    def _render_categories(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

        categories = self._snapshot.context_categories if self._snapshot else ()
        ordered = sorted(categories, key=lambda c: c.tokens, reverse=True)
        largest = max((c.tokens for c in ordered), default=0)

        self.category_rows = [(c.name, fmt_tokens(c.tokens)) for c in ordered]
        for row, category in enumerate(ordered):
            self._grid.addWidget(QLabel(category.name, self._grid_host), row, 0)
            self._grid.addWidget(
                QLabel(fmt_tokens(category.tokens), self._grid_host), row, 1)
            meter = TokenBar(self._grid_host)
            meter.setValue(int(100 * category.tokens / largest) if largest else 0)
            self._grid.addWidget(meter, row, 2)

    def _build_footer(self) -> str:
        snapshot = self._snapshot
        if snapshot is None:
            return ""
        parts: list[str] = []
        if snapshot.num_turns:
            parts.append(
                f"{snapshot.num_turns} turn"
                + ("s" if snapshot.num_turns != 1 else ""))
        duration = fmt_duration(snapshot.duration_api_ms)
        if duration:
            parts.append(f"{duration} api")
        for text in (fmt_cost(snapshot.cost), fmt_carbon(snapshot.carbon)):
            if text:
                parts.append(text)
        return " · ".join(parts)
