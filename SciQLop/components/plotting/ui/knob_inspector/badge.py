from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QToolButton

from SciQLop.components.plotting.backend.graph_knobs import GraphKnobState


def _format_value(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def format_summary(values: dict) -> str:
    if not values:
        return ""
    return " | ".join(f"{k}={_format_value(v)}" for k, v in values.items())


class KnobBadge(QFrame):
    clicked = Signal()

    def __init__(self, state: GraphKnobState, parent=None):
        super().__init__(parent)
        self.setObjectName("KnobBadge")
        self._state = state
        self._collapsed = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        self._toggle_btn = QToolButton()
        self._toggle_btn.setText("◐")
        self._toggle_btn.setAutoRaise(True)
        self._toggle_btn.clicked.connect(self.toggle)
        layout.addWidget(self._toggle_btn)

        self._label = QLabel()
        self._label.setObjectName("KnobBadgeText")
        layout.addWidget(self._label)

        self._refresh()
        state.knobs_changed.connect(lambda *_: self._refresh())

    def _refresh(self):
        self._label.setText(format_summary(self._state.values))

    def summary_text(self) -> str:
        return self._label.text()

    def toggle(self):
        self._collapsed = not self._collapsed
        self._label.setVisible(not self._collapsed)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and not self._toggle_btn.geometry().contains(event.pos()):
            self.clicked.emit()
        super().mousePressEvent(event)
