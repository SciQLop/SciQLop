from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QComboBox, QLabel,
    QLineEdit, QDialogButtonBox, QWidget,
)
from SciQLop.core.ui import Metrics, fit_combo_to_content

_COLORMAPS = [
    "viridis", "plasma", "inferno", "magma", "cividis",
    "coolwarm", "RdYlBu", "Spectral", "RdBu",
    "hot", "jet", "turbo",
]


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
        self._vmin_edit = QLineEdit()
        self._vmin_edit.setPlaceholderText("auto")
        if current_vmin is not None:
            self._vmin_edit.setText(str(current_vmin))
        vmin_layout.addWidget(self._vmin_edit)
        layout.addLayout(vmin_layout)

        # vmax
        vmax_layout = QHBoxLayout()
        vmax_layout.addWidget(QLabel("Max value:"))
        self._vmax_edit = QLineEdit()
        self._vmax_edit.setPlaceholderText("auto")
        if current_vmax is not None:
            self._vmax_edit.setText(str(current_vmax))
        vmax_layout.addWidget(self._vmax_edit)
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
        text = self._vmin_edit.text().strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

    @property
    def vmax(self) -> float | None:
        text = self._vmax_edit.text().strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
