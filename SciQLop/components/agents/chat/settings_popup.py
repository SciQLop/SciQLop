"""Settings popup for the agent chat dock.

Holds every control that previously crowded the dock header: model, effort,
activity verbosity, allow-writes, export. A `Qt.Popup` widget rather than a
`QMenu` with `QWidgetAction`s — combos inside menus swallow clicks and close the
menu on interaction. Click-away dismissal comes free with the flag.
"""
from __future__ import annotations

from typing import Optional, Sequence

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

_DEFAULT_LABEL = "Default"


class AgentSettingsPopup(QWidget):
    effort_changed = Signal(str)
    export_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)

        outer = QVBoxLayout(self)
        form = QFormLayout()
        outer.addLayout(form)
        self._form = form

        self.model_combo = QComboBox(self)
        self.model_combo.setToolTip("Which model the backend should use.")
        form.addRow("Model", self.model_combo)

        self.effort_combo = QComboBox(self)
        self.effort_combo.setToolTip(
            "How much reasoning effort the model should spend. "
            "Available levels depend on the selected model.")
        self.effort_combo.currentIndexChanged.connect(self._on_effort_index_changed)
        form.addRow("Effort", self.effort_combo)

        self.verbosity_combo = QComboBox(self)
        self.verbosity_combo.addItems(
            ["Activity: minimal", "Activity: + inputs", "Activity: + results"])
        self.verbosity_combo.setToolTip(
            "How much of the agent's tool activity to show in the chat.")
        form.addRow("Activity", self.verbosity_combo)

        self.writes_toggle = QCheckBox("Yolo mode (auto-approve)", self)
        self.writes_toggle.setToolTip(
            "When enabled, the agent can run gated tools — set time range, "
            "create panels, exec Python, edit notebooks, install packages — "
            "without asking for confirmation each time.")
        form.addRow("", self.writes_toggle)

        separator = QFrame(self)
        separator.setFrameShape(QFrame.Shape.HLine)
        outer.addWidget(separator)

        self.export_button = QPushButton("Export transcript ⤓", self)
        self.export_button.setToolTip("Save this transcript as a Markdown file.")
        self.export_button.clicked.connect(self.export_requested)
        outer.addWidget(self.export_button)

        self.set_effort_values((), None)

    def is_effort_row_visible(self) -> bool:
        return self._form.isRowVisible(self.effort_combo)

    def current_effort(self) -> Optional[str]:
        """The selected level, or None when "Default" (no override) is chosen."""
        return self.effort_combo.currentData()

    def set_effort_values(
        self, values: Sequence[str], current: Optional[str]
    ) -> None:
        """Repopulate for the selected model. Empty `values` hides the row.

        A `current` absent from `values` falls back to Default — the persisted
        choice is left alone by the caller so it still applies if the user
        returns to a model that accepts it.
        """
        self.effort_combo.blockSignals(True)
        self.effort_combo.clear()
        self.effort_combo.addItem(_DEFAULT_LABEL, None)
        for value in values:
            self.effort_combo.addItem(value, value)
        if current and current in values:
            self.effort_combo.setCurrentIndex(list(values).index(current) + 1)
        else:
            self.effort_combo.setCurrentIndex(0)
        self.effort_combo.blockSignals(False)
        self._form.setRowVisible(self.effort_combo, bool(values))

    def _on_effort_index_changed(self, _index: int) -> None:
        self.effort_changed.emit(self.effort_combo.currentData() or "")
