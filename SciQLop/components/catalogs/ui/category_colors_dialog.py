from __future__ import annotations

from typing import Callable

from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QColorDialog, QDialog, QDialogButtonBox, QFormLayout, QLabel, QPushButton,
    QScrollArea, QToolButton, QVBoxLayout, QWidget,
)

from SciQLop.components.catalogs.backend.color_palette import _CatalogSwatchIconEngine
from SciQLop.core.ui import Metrics
from SciQLop.core.ui.tooltips import rich_tooltip


def _swatch(color: QColor) -> QIcon:
    opaque = QColor(color)
    opaque.setAlpha(255)
    return QIcon(_CatalogSwatchIconEngine(opaque))


class CategoryColorsDialog(QDialog):
    def __init__(self, categories: list[str], current: dict[str, str],
                 default_color: Callable[[str], QColor], parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Category colors")
        self.setMinimumWidth(Metrics.em(24))
        self.setMaximumHeight(Metrics.em(40))
        self._default_color = default_color
        self._colors: dict[str, QColor | None] = {
            value: QColor(current[value]) if value in current else None for value in categories
        }
        self._buttons: dict[str, QToolButton] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(self._make_rows(categories))
        layout.addWidget(self._make_buttons())

    def _make_rows(self, categories: list[str]) -> QScrollArea:
        rows = QWidget()
        form = QFormLayout(rows)
        for value in categories:
            button = QToolButton()
            button.clicked.connect(lambda _=False, v=value: self._pick(v))
            self._buttons[value] = button
            form.addRow(button, QLabel(value))
            self._refresh(value)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(rows)
        return scroll

    def _make_buttons(self) -> QDialogButtonBox:
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self._reset_button = QPushButton("Reset all")
        self._reset_button.setToolTip(rich_tooltip(
            "Reset all",
            "Clear every custom category color; colors fall back to their defaults."))
        buttons.addButton(self._reset_button, QDialogButtonBox.ButtonRole.ResetRole)
        self._reset_button.clicked.connect(self._reset_all)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        return buttons

    def _current_color(self, value: str) -> QColor:
        return self._colors[value] or self._default_color(value)

    def _refresh(self, value: str) -> None:
        self._buttons[value].setIcon(_swatch(self._current_color(value)))

    def _pick(self, value: str) -> None:
        picked = QColorDialog.getColor(self._current_color(value), self, f"Color for '{value}'")
        if picked.isValid():
            self._colors[value] = picked
            self._refresh(value)

    def _reset_all(self) -> None:
        for value in self._colors:
            self._colors[value] = None
            self._refresh(value)

    @property
    def category_colors(self) -> dict[str, str]:
        return {value: color.name() for value, color in self._colors.items() if color is not None}
