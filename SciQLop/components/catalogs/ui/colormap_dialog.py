from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QLabel,
    QDoubleSpinBox, QCheckBox, QDialogButtonBox, QWidget,
)
from SciQLop.core.ui import Metrics, fit_combo_to_content
from SciQLop.core.ui.tooltips import rich_tooltip

# jet/turbo/hot dropped: not perceptually uniform, the standard objection to
# "rainbow" colormaps in scientific visualization (misleading apparent
# gradients, poor grayscale/colorblind legibility).
_COLORMAPS = [
    "viridis", "plasma", "inferno", "magma", "cividis",
    "coolwarm", "RdYlBu", "Spectral", "RdBu",
]


def _make_value_row(current_value: float | None) -> tuple[QHBoxLayout, QDoubleSpinBox, QCheckBox]:
    """A vmin/vmax control: a spinbox plus an explicit "Auto" checkbox.

    Not a numeric sentinel: any value a QDoubleSpinBox can hold is a
    legitimate vmin/vmax (physics data can have extreme magnitudes), so
    "auto" can't be encoded as one particular value without risking exactly
    the silent misinterpretation this control replaces a free-text field to
    avoid.
    """
    spin = QDoubleSpinBox()
    spin.setRange(-1e300, 1e300)
    spin.setDecimals(6)
    auto_check = QCheckBox("Auto")
    is_auto = current_value is None
    auto_check.setChecked(is_auto)
    spin.setEnabled(not is_auto)
    if current_value is not None:
        spin.setValue(current_value)
    auto_check.toggled.connect(lambda checked: spin.setEnabled(not checked))

    row = QHBoxLayout()
    row.addWidget(spin)
    row.addWidget(auto_check)
    return row, spin, auto_check


class ColormapDialog(QDialog):
    def __init__(self, current_colormap: str = "viridis",
                 current_vmin: float | None = None,
                 current_vmax: float | None = None,
                 parent: QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("Configure Colormap")
        self.setMinimumWidth(Metrics.em(28))

        layout = QVBoxLayout(self)

        # Colormap picker
        cmap_layout = QHBoxLayout()
        cmap_layout.addWidget(QLabel("Colormap:"))
        self._cmap_combo = QComboBox()
        self._cmap_combo.setToolTip(rich_tooltip(
            "Colormap",
            "Perceptually uniform colormaps for numeric attributes."))
        self._cmap_combo.addItems(_COLORMAPS)
        if current_colormap not in _COLORMAPS:
            # A catalog's persisted colormap may be a name that used to be
            # offered here (e.g. "jet") -- keep it selectable so opening
            # this dialog and accepting without touching the combo can't
            # silently rewrite it to the default.
            self._cmap_combo.addItem(current_colormap)
        self._cmap_combo.setCurrentText(current_colormap)
        fit_combo_to_content(self._cmap_combo)
        cmap_layout.addWidget(self._cmap_combo)
        layout.addLayout(cmap_layout)

        # vmin
        vmin_layout, self._vmin_spin, self._vmin_auto = _make_value_row(current_vmin)
        vmin_layout.insertWidget(0, QLabel("Min value:"))
        self._vmin_spin.setToolTip(rich_tooltip("Min value", "The colormap's lowest value."))
        self._vmin_auto.setToolTip(rich_tooltip(
            "Auto", "Use the smallest and largest values found in the catalog."))
        layout.addLayout(vmin_layout)

        # vmax
        vmax_layout, self._vmax_spin, self._vmax_auto = _make_value_row(current_vmax)
        vmax_layout.insertWidget(0, QLabel("Max value:"))
        self._vmax_spin.setToolTip(rich_tooltip("Max value", "The colormap's highest value."))
        self._vmax_auto.setToolTip(rich_tooltip(
            "Auto", "Use the smallest and largest values found in the catalog."))
        layout.addLayout(vmax_layout)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @property
    def colormap(self) -> str:
        return self._cmap_combo.currentText()

    @property
    def vmin(self) -> float | None:
        return None if self._vmin_auto.isChecked() else self._vmin_spin.value()

    @property
    def vmax(self) -> float | None:
        return None if self._vmax_auto.isChecked() else self._vmax_spin.value()
