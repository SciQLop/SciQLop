"""The Compare dialog: base panel, what changes and what to compare against, on one page (spec §7)."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout,
                               QRadioButton, QVBoxLayout, QWidget)

from SciQLop.components.comparison.backend.dimensions import COMPARISON_DIMENSIONS
from SciQLop.components.comparison.backend.model import Comparison, Variant, template_at_range
from SciQLop.components.comparison.ui.panel_kind import COMPARISON_PANEL
from SciQLop.components.comparison.ui.pickers import VariantPicker, picker_for
from SciQLop.components.plotting.panel_template import PanelTemplate

Preset = tuple[str, list[Variant]]


def panel_name(panel) -> Optional[str]:
    """A panel given by name, as a time panel, or as its user_api wrapper."""
    if panel is None or isinstance(panel, str):
        return panel or None
    if hasattr(panel, "_get_impl_or_raise"):
        panel = panel._get_impl_or_raise()
    return panel.name


class CompareDialog(QDialog):
    """Opens a Comparison panel, or in edit mode (comparison given) emits `compared` with the edited comparison."""
    compared = Signal(object)

    def __init__(self, main_window, base_panel=None, comparison: Optional[Comparison] = None,
                 preset: Optional[Preset] = None, base_choices: Optional[list[str]] = None,
                 base_range: Optional[tuple[float, float]] = None, parent: Optional[QWidget] = None):
        super().__init__(parent if parent is not None else main_window)
        self.setWindowTitle("Edit comparison" if comparison is not None else "Compare")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._main_window = main_window
        self._comparison = comparison
        self._base_range = base_range
        self._preset = preset or ((comparison.dimension, comparison.variants) if comparison is not None else None)
        self.picker: Optional[VariantPicker] = None
        self.opened = None
        self._build(panel_name(base_panel), base_choices)
        self._rebuild_picker()

    def _build(self, base: Optional[str], base_choices: Optional[list[str]]) -> None:
        self.base_combo = self._base_combo(base, base_choices)
        self.dimension_group = QButtonGroup(self)
        self.dimension_buttons = self._dimension_buttons()
        self.picker_area = QVBoxLayout()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.compare_button = buttons.addButton("Compare", QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(self._compare)
        buttons.rejected.connect(self.reject)
        self.base_combo.currentIndexChanged.connect(lambda _i: self._rebuild_picker())
        self.dimension_group.buttonToggled.connect(lambda _b, checked: checked and self._rebuild_picker())
        form = QFormLayout()
        form.addRow("Base panel", self.base_combo)
        form.addRow("What changes", self._row(self.dimension_buttons.values()))
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addLayout(self.picker_area, 1)
        layout.addWidget(buttons)

    def _base_combo(self, base: Optional[str], base_choices: Optional[list[str]]) -> QComboBox:
        combo = QComboBox()
        if self._comparison is not None:
            combo.addItem(self._comparison.template().name)
            combo.setEnabled(False)
            return combo
        names = base_choices if base_choices is not None else self._main_window.plot_panels()
        combo.addItems(names)
        combo.setPlaceholderText("Choose a panel…")
        combo.setCurrentIndex(names.index(base) if base in names else 0 if len(names) == 1 else -1)
        return combo

    def _dimension_buttons(self) -> dict[str, QRadioButton]:
        wanted = self._preset[0] if self._preset is not None else None
        buttons = {}
        for d in COMPARISON_DIMENSIONS.list():
            button = QRadioButton(d.label)
            self.dimension_group.addButton(button)
            buttons[d.id] = button
        checked = buttons.get(wanted) or next(iter(buttons.values()), None)
        if checked is not None:
            checked.setChecked(True)
        return buttons

    @staticmethod
    def _row(widgets) -> QHBoxLayout:
        row = QHBoxLayout()
        for widget in widgets:
            row.addWidget(widget)
        row.addStretch()
        return row

    def dimension(self) -> Optional[str]:
        return next((id for id, b in self.dimension_buttons.items() if b.isChecked()), None)

    def base_template(self) -> Optional[PanelTemplate]:
        if self._comparison is not None:
            return self._comparison.template()
        panel = self._main_window.plot_panel(self.base_combo.currentText())
        return template_at_range(PanelTemplate.from_panel(panel), self._base_range) if panel is not None else None

    def _rebuild_picker(self) -> None:
        if self.picker is not None:
            self.picker_area.removeWidget(self.picker)
            self.picker.deleteLater()
            self.picker = None
        template, dimension = self.base_template(), self.dimension()
        if template is not None and dimension is not None:
            self.picker = picker_for(dimension, template, self)
            if self._preset is not None and self._preset[0] == dimension:
                self.picker.set_variants(self._preset[1])
            self.picker.changed.connect(self._update_compare)
            self.picker_area.addWidget(self.picker)
        self._update_compare()

    def _refusal(self) -> Optional[str]:
        if self._comparison is None and self.picker is not None and self.base_template() is None:
            return "the base panel is no longer open"
        if self.picker is None:
            return "choose a base panel and what changes"
        problem = self.picker.problem()
        if problem is not None:
            return problem
        return None if self.picker.variants() else "pick at least one variant to compare against"

    def _update_compare(self) -> None:
        refusal = self._refusal()
        self.compare_button.setEnabled(refusal is None)
        self.compare_button.setToolTip(refusal or "")

    def comparison(self) -> Comparison:
        changes = {"dimension": self.dimension(), "variants": self.picker.variants()}
        if self._comparison is not None:
            return self._comparison.model_copy(update=changes)
        return Comparison(base=self.base_template().to_tree(), **changes)

    def _compare(self) -> None:
        if self._refusal() is not None:
            return
        comparison = self.comparison()
        if self._comparison is None:
            self.opened = self._main_window.open_panel(COMPARISON_PANEL, **comparison.model_dump(mode="json"))
        self.compared.emit(comparison)
        self.accept()


def edit_comparison(panel) -> CompareDialog:
    """The dialog in edit mode for a Comparison panel; Compare updates that panel in place.
    An open one is raised instead: a second dialog would overwrite its changes with a stale snapshot."""
    from SciQLop.core.sciqlop_application import sciqlop_app
    for open_dialog in panel.findChildren(CompareDialog):
        if open_dialog.isVisible():
            open_dialog.raise_()
            open_dialog.activateWindow()
            return open_dialog
    dialog = CompareDialog(sciqlop_app().main_window, comparison=panel.comparison, parent=panel)
    dialog.compared.connect(panel.set_comparison)
    dialog.show()
    return dialog
