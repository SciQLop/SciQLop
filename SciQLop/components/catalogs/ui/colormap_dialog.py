from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QLabel,
    QDoubleSpinBox, QDialogButtonBox, QWidget,
)
from SciQLop.core.ui import Metrics, fit_combo_to_content

# jet/turbo/hot dropped: not perceptually uniform, the standard objection to
# "rainbow" colormaps in scientific visualization (misleading apparent
# gradients, poor grayscale/colorblind legibility).
_COLORMAPS = [
    "viridis", "plasma", "inferno", "magma", "cividis",
    "coolwarm", "RdYlBu", "Spectral", "RdBu",
]

_AUTO_SENTINEL = -1e18


def _make_value_spinbox() -> QDoubleSpinBox:
    """A vmin/vmax spinbox where reaching the minimum means "auto" --
    unlike the free-text field it replaces, invalid input isn't possible:
    there's nothing to mistype."""
    box = QDoubleSpinBox()
    box.setRange(_AUTO_SENTINEL, 1e18)
    box.setDecimals(6)
    box.setSpecialValueText("auto")
    box.setValue(_AUTO_SENTINEL)
    return box


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
        self._cmap_combo.addItems(_COLORMAPS)
        if current_colormap in _COLORMAPS:
            self._cmap_combo.setCurrentText(current_colormap)
        fit_combo_to_content(self._cmap_combo)
        cmap_layout.addWidget(self._cmap_combo)
        layout.addLayout(cmap_layout)

        # vmin
        vmin_layout = QHBoxLayout()
        vmin_layout.addWidget(QLabel("Min value:"))
        self._vmin_spin = _make_value_spinbox()
        if current_vmin is not None:
            self._vmin_spin.setValue(current_vmin)
        vmin_layout.addWidget(self._vmin_spin)
        layout.addLayout(vmin_layout)

        # vmax
        vmax_layout = QHBoxLayout()
        vmax_layout.addWidget(QLabel("Max value:"))
        self._vmax_spin = _make_value_spinbox()
        if current_vmax is not None:
            self._vmax_spin.setValue(current_vmax)
        vmax_layout.addWidget(self._vmax_spin)
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
        value = self._vmin_spin.value()
        return None if value == _AUTO_SENTINEL else value

    @property
    def vmax(self) -> float | None:
        value = self._vmax_spin.value()
        return None if value == _AUTO_SENTINEL else value
